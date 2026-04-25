import pytest
from app.use_cases.users.queries.list_active_users import (
    ListActiveUsersHandler, ListActiveUsersQuery,
)
from app.domain.user.user import User
from tests.unit.use_cases.users.fakes.in_memory_user_repository import InMemoryUserRepository


@pytest.mark.asyncio
async def test_lista_todos_ate_limit():
    repo = InMemoryUserRepository()
    for i in range(3):
        u = User.create(
            name=f"U{i}", email=f"u{i}@x.com",
            phone="(21) 99694-9389",
        ).value
        await repo.add(u)

    r = await ListActiveUsersHandler(repo).handle(ListActiveUsersQuery())
    assert r.is_success
    assert len(r.value) == 3


@pytest.mark.asyncio
async def test_aplica_limit_e_offset():
    repo = InMemoryUserRepository()
    for i in range(5):
        u = User.create(
            name=f"U{i}", email=f"u{i}@x.com",
            phone="(21) 99694-9389",
        ).value
        await repo.add(u)

    r = await ListActiveUsersHandler(repo).handle(
        ListActiveUsersQuery(limit=2, offset=1)
    )
    assert r.is_success
    assert len(r.value) == 2
