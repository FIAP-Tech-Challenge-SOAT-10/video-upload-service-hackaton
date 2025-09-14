import uuid
import app.utils.id_gen as id_gen
from app.utils.id_gen import new_id


def test_new_id_format_is_uuid4():
    value = new_id()
    # deve ser uma string parseável como UUID e com versão 4
    u = uuid.UUID(value)
    assert isinstance(value, str)
    assert u.version == 4


def test_new_id_uniqueness_small_sample():
    values = [new_id() for _ in range(20)]
    assert len(values) == len(set(values))  # sem duplicados na amostra


def test_new_id_delegates_to_uuid4(monkeypatch):
    # força retorno determinístico para garantir que usamos uuid.uuid4() + str()
    fixed = uuid.UUID("00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(id_gen.uuid, "uuid4", lambda: fixed, raising=True)

    assert new_id() == str(fixed)
