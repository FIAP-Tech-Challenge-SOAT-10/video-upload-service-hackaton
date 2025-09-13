import sys
import importlib
import pytest
import boto3
from botocore.exceptions import ClientError, BotoCoreError

# possíveis caminhos onde a função pode estar
CANDIDATES = ["app.services.storage", "app.aws", "app.utils.s3"]


def _load_target_module():
    """Tenta importar um dos módulos candidatos que tenha upload_bytes."""
    last_err = None
    for name in CANDIDATES:
        try:
            if name in sys.modules:
                mod = importlib.reload(sys.modules[name])
            else:
                mod = importlib.import_module(name)
        except Exception as e:
            last_err = e
            continue
        if hasattr(mod, "upload_bytes"):
            return mod
    raise AssertionError(
        f"Não encontrei a função upload_bytes em nenhum destes módulos: {CANDIDATES}. "
        f"Último erro de import: {last_err!r}"
    )


def _import_with_env_and_injected_s3(monkeypatch, dummy_s3, **env):
    """Configura env, injeta client fake no boto3.Session.client e carrega módulo alvo."""
    # ENV antes do import
    monkeypatch.setenv("AWS_ENDPOINT_URL", env.get("AWS_ENDPOINT_URL", "http://localhost:4566"))
    monkeypatch.setenv("AWS_DEFAULT_REGION", env.get("AWS_DEFAULT_REGION", "us-east-1"))
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", env.get("AWS_ACCESS_KEY_ID", "test"))
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", env.get("AWS_SECRET_ACCESS_KEY", "test"))
    monkeypatch.setenv("S3_BUCKET", env.get("S3_BUCKET", "test-bucket"))

    # injeta client fake do S3
    original_client = boto3.session.Session.client

    def fake_client(self, service_name, *args, **kwargs):
        if service_name == "s3":
            return dummy_s3
        return original_client(self, service_name, *args, **kwargs)

    monkeypatch.setattr(boto3.session.Session, "client", fake_client, raising=True)

    # limpa módulos candidatos para reimport com env + injeção
    for name in CANDIDATES:
        sys.modules.pop(name, None)

    return _load_target_module()


class DummyS3OK:
    def __init__(self):
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)


class DummyS3FailClientError:
    def put_object(self, **kwargs):
        raise ClientError({"Error": {"Code": "Boom", "Message": "nope"}}, "PutObject")


class DummyS3FailBotoCore:
    def put_object(self, **kwargs):
        raise BotoCoreError(error_message="network glitch")


def test_upload_bytes_success_custom_content_type(monkeypatch):
    dummy = DummyS3OK()
    awsmod = _import_with_env_and_injected_s3(
        monkeypatch,
        dummy_s3=dummy,
        AWS_ENDPOINT_URL="http://localstack:4566",
        S3_BUCKET="video-service-bucket",
    )

    url = awsmod.upload_bytes("folder/file.txt", b"hello", content_type="text/plain")

    assert url == "http://localstack:4566/video-service-bucket/folder/file.txt"
    assert len(dummy.calls) == 1
    call = dummy.calls[0]
    assert call["Bucket"] == "video-service-bucket"
    assert call["Key"] == "folder/file.txt"
    assert call["Body"] == b"hello"
    assert call["ContentType"] == "text/plain"


def test_upload_bytes_success_default_content_type(monkeypatch):
    dummy = DummyS3OK()
    awsmod = _import_with_env_and_injected_s3(
        monkeypatch,
        dummy_s3=dummy,
        AWS_ENDPOINT_URL="http://localhost:4566",
        S3_BUCKET="my-bucket",
    )

    url = awsmod.upload_bytes("a/b/c.bin", b"\x00\x01")

    assert url == "http://localhost:4566/my-bucket/a/b/c.bin"
    call = dummy.calls[0]
    assert call["ContentType"] == "application/octet-stream"


@pytest.mark.parametrize("dummy_cls", [DummyS3FailClientError, DummyS3FailBotoCore])
def test_upload_bytes_raises_runtimeerror_on_boto_errors(monkeypatch, dummy_cls):
    dummy = dummy_cls()
    awsmod = _import_with_env_and_injected_s3(monkeypatch, dummy_s3=dummy)

    with pytest.raises(RuntimeError) as exc:
        awsmod.upload_bytes("x/y/z", b"data")

    assert "Falha ao salvar no storage:" in str(exc.value)
