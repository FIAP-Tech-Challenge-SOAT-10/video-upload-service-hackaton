import pytest
import importlib

import app.utils.s3 as s3mod


# ---------- Dummies ----------

class DummyS3OK:
    def __init__(self):
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)  # registra chamada e segue


class Boom(Exception):
    pass


class DummyS3Fail:
    def put_object(self, **kwargs):
        raise Boom("falhou no put_object")


class DummyCounter:
    def __init__(self):
        self.records = []

    def labels(self, **kwargs):
        # retorna self para permitir .inc() em sequência
        self._last_labels = kwargs
        return self

    def inc(self, n=1):
        # guarda o status do último labels + valor do incremento
        self.records.append(("inc", dict(self._last_labels), n))


# ---------- build_s3_key ----------

def test_build_s3_key_without_vid_calls_new_id(monkeypatch):
    # força new_id determinístico
    monkeypatch.setattr(s3mod, "new_id", lambda: "vid42", raising=True)

    vid, key = s3mod.build_s3_key("arquivo.mp4")

    assert vid == "vid42"
    assert key == "videos/vid42/arquivo.mp4"


def test_build_s3_key_with_vid_does_not_call_new_id(monkeypatch):
    # se new_id for chamado, o teste falha
    def _should_not_be_called():
        raise AssertionError("new_id NÃO deveria ser chamado quando vid é passado")
    monkeypatch.setattr(s3mod, "new_id", _should_not_be_called, raising=True)

    vid, key = s3mod.build_s3_key("input.mov", vid="abc-123")

    assert vid == "abc-123"
    assert key == "videos/abc-123/input.mov"


# ---------- put_object ----------

def test_put_object_success_calls_s3_and_increments_metric(monkeypatch):
    dummy_s3 = DummyS3OK()
    counter = DummyCounter()

    monkeypatch.setattr(s3mod, "s3", dummy_s3, raising=True)
    monkeypatch.setattr(s3mod, "S3_OPS", counter, raising=True)

    s3mod.put_object(
        bucket="my-bucket",
        key="videos/vid/file.bin",
        file_bytes=b"\x00\x01",
        content_type="application/octet-stream",
    )

    # s3 recebeu os parâmetros esperados
    assert len(dummy_s3.calls) == 1
    call = dummy_s3.calls[0]
    assert call["Bucket"] == "my-bucket"
    assert call["Key"] == "videos/vid/file.bin"
    assert call["Body"] == b"\x00\x01"
    assert call["ContentType"] == "application/octet-stream"

    # métrica incrementada com status ok
    assert ("inc", {"op": "put", "status": "ok"}, 1) in counter.records


def test_put_object_failure_increments_error_and_reraises(monkeypatch):
    dummy_s3 = DummyS3Fail()
    counter = DummyCounter()

    monkeypatch.setattr(s3mod, "s3", dummy_s3, raising=True)
    monkeypatch.setattr(s3mod, "S3_OPS", counter, raising=True)

    with pytest.raises(Boom):
        s3mod.put_object(
            bucket="b",
            key="k",
            file_bytes=b"data",
            content_type="text/plain",
        )

    # métrica incrementada com status error
    assert ("inc", {"op": "put", "status": "error"}, 1) in counter.records
