from uuid import uuid4
import pytest
from app.use_cases.users.commands.update_user_email import (
    UpdateUserEmailCommand, UpdateUserEmailHandler,
)
from app.domain.user.user import User
from tests.unit.use_cases.users.fakes.in_memory_user_repository import InMemoryUserRepository


@pytest.mark.asyncio
async def test_atualiza_email_valido():
    repo = InMemoryUserRepository()
    u = User.create(name="A", email="old@x.com", phone="(21) 99694-9389").value
    await repo.add(u)

    r = await UpdateUserEmailHandler(repo).handle(
        UpdateUserEmailCommand(user_id=u.id, new_email="NEW@x.com")
    )
    assert r.is_success
    assert r.value.email == "new@x.com"


@pytest.mark.asyncio
async def test_404_quando_user_nao_existe():
    repo = InMemoryUserRepository()
    r = await UpdateUserEmailHandler(repo).handle(
        UpdateUserEmailCommand(user_id=uuid4(), new_email="x@x.com")
    )
    assert r.is_failure
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_422_quando_novo_email_invalido():
    repo = InMemoryUserRepository()
    u = User.create(name="A", email="old@x.com", phone="(21) 99694-9389").value
    await repo.add(u)

    r = await UpdateUserEmailHandler(repo).handle(
        UpdateUserEmailCommand(user_id=u.id, new_email="not-an-email")
    )
    assert r.is_failure
    assert r.status_code == 422
