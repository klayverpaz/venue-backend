from uuid import uuid4
import pytest
from app.use_cases.users.queries.get_user_by_id import (
    GetUserByIdHandler, GetUserByIdQuery,
)
from app.domain.user.user import User
from tests.unit.use_cases.users.fakes.in_memory_user_repository import InMemoryUserRepository


@pytest.mark.asyncio
async def test_retorna_user_existente():
    repo = InMemoryUserRepository()
    u = User.create(name="A", email="a@x.com", phone="(21) 99694-9389").value
    await repo.add(u)

    r = await GetUserByIdHandler(repo).handle(GetUserByIdQuery(user_id=u.id))
    assert r.is_success
    assert r.value.email == "a@x.com"


@pytest.mark.asyncio
async def test_retorna_404_quando_nao_existe():
    repo = InMemoryUserRepository()
    r = await GetUserByIdHandler(repo).handle(GetUserByIdQuery(user_id=uuid4()))
    assert r.is_failure
    assert r.status_code == 404
