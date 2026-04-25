import pytest
from app.domain.user.user import User
from app.infrastructure.repositories.user_repository import UserRepository


@pytest.mark.asyncio
async def test_add_e_get_by_id(db_session):
    repo = UserRepository(db_session)
    user = User.create(
        name="Maria", email="maria@x.com",
        phone="(21) 99694-9389", credit_score=80, balance=2000,
    ).value
    await repo.add(user)
    await db_session.commit()

    fetched = await repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.email.value == "maria@x.com"
    assert fetched.phone.value == "+5521996949389"


@pytest.mark.asyncio
async def test_get_by_email_normaliza(db_session):
    repo = UserRepository(db_session)
    user = User.create(
        name="X", email="someone@x.com", phone="(21) 99694-9389",
    ).value
    await repo.add(user)
    await db_session.commit()

    fetched = await repo.get_by_email("  SOMEONE@X.COM  ")
    assert fetched is not None
    assert fetched.id == user.id


@pytest.mark.asyncio
async def test_list_active_ordenada_por_created_at_desc(db_session):
    repo = UserRepository(db_session)
    u1 = User.create(name="1", email="a@x.com", phone="(21) 99694-9389").value
    u2 = User.create(name="2", email="b@x.com", phone="(21) 99694-9388").value
    await repo.add(u1)
    await repo.add(u2)
    await db_session.commit()

    out = await repo.list_active()
    assert len(out) == 2


@pytest.mark.asyncio
async def test_update_sincroniza_colunas(db_session):
    repo = UserRepository(db_session)
    user = User.create(
        name="X", email="a@x.com", phone="(21) 99694-9389",
    ).value
    await repo.add(user)
    await db_session.commit()

    user.change_email("new@x.com")
    await repo.update(user)
    await db_session.commit()

    fetched = await repo.get_by_email("new@x.com")
    assert fetched is not None


@pytest.mark.asyncio
async def test_remove(db_session):
    repo = UserRepository(db_session)
    user = User.create(
        name="X", email="a@x.com", phone="(21) 99694-9389",
    ).value
    await repo.add(user)
    await db_session.commit()

    await repo.remove(user)
    await db_session.commit()

    assert await repo.get_by_id(user.id) is None
