import pytest
from app.use_cases.users.commands.create_user import CreateUserCommand, CreateUserHandler
from tests.unit.use_cases.users.fakes.in_memory_user_repository import InMemoryUserRepository


@pytest.mark.asyncio
async def test_cria_user_valido():
    repo = InMemoryUserRepository()
    h = CreateUserHandler(repo)
    r = await h.handle(CreateUserCommand(
        name="João", email="joao@x.com", phone="(21) 99694-9389",
        credit_score=80, balance=500,
    ))
    assert r.is_success
    assert r.status_code == 201
    assert r.value.email == "joao@x.com"


@pytest.mark.asyncio
async def test_rejeita_email_duplicado():
    repo = InMemoryUserRepository()
    h = CreateUserHandler(repo)
    await h.handle(CreateUserCommand(
        name="A", email="dup@x.com", phone="(21) 99694-9389",
    ))
    r = await h.handle(CreateUserCommand(
        name="B", email="dup@x.com", phone="(21) 99694-9388",
    ))
    assert r.is_failure
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_rejeita_vo_invalido_422():
    repo = InMemoryUserRepository()
    h = CreateUserHandler(repo)
    r = await h.handle(CreateUserCommand(
        name="X", email="nao-eh-email", phone="xxx",
    ))
    assert r.is_failure
    assert r.status_code == 422
