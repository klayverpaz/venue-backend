import pytest
from app.use_cases.users.queries.get_user_by_email import (
    GetUserByEmailHandler, GetUserByEmailQuery,
)
from app.domain.user.user import User
from tests.unit.use_cases.users.fakes.in_memory_user_repository import InMemoryUserRepository


@pytest.mark.asyncio
async def test_retorna_user_por_email_normalizado():
    repo = InMemoryUserRepository()
    u = User.create(name="A", email="Found@x.COM", phone="(21) 99694-9389").value
    await repo.add(u)

    r = await GetUserByEmailHandler(repo).handle(
        GetUserByEmailQuery(email="  FOUND@X.com  ")
    )
    assert r.is_success
    assert r.value.email == "found@x.com"


@pytest.mark.asyncio
async def test_404_quando_nao_existe():
    repo = InMemoryUserRepository()
    r = await GetUserByEmailHandler(repo).handle(
        GetUserByEmailQuery(email="ghost@x.com")
    )
    assert r.is_failure
    assert r.status_code == 404
