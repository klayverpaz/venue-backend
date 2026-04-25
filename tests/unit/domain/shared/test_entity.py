from dataclasses import dataclass
from uuid import uuid4
from app.domain.shared.entity import BaseEntity


@dataclass(slots=True, kw_only=True)
class SampleEntity(BaseEntity):
    name: str


def test_entity_gera_id_e_timestamps_automaticos():
    e = SampleEntity(name="x")
    assert e.id is not None
    assert e.created_at is not None
    assert e.updated_at is not None


def test_entity_equality_por_id():
    id_ = uuid4()
    a = SampleEntity(id=id_, name="A")
    b = SampleEntity(id=id_, name="B")  # nome diferente, mesmo id
    assert a == b
    assert hash(a) == hash(b)


def test_entity_diferentes_com_ids_diferentes():
    a = SampleEntity(name="A")
    b = SampleEntity(name="A")
    assert a != b
