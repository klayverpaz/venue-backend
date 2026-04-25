from __future__ import annotations
import logging
from langchain_core.tools import tool

from app.use_cases.users.queries.get_user_by_email import (
    GetUserByEmailHandler, GetUserByEmailQuery,
)
from app.core.context import db_session
from app.infrastructure.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


@tool
async def get_user_by_email(email: str) -> str:
    """Busca um usuário pelo email. Retorna nome, telefone, score de crédito e saldo."""
    session = db_session.get()
    if session is None:
        logger.error("get_user_by_email chamada sem sessão de DB na ContextVar")
        return "Erro interno: contexto de banco não disponível."

    handler = GetUserByEmailHandler(UserRepository(session))
    result = await handler.handle(GetUserByEmailQuery(email=email))

    if result.is_failure:
        return result.error

    u = result.value
    return (
        f"Nome: {u.name}\n"
        f"Email: {u.email}\n"
        f"Telefone: {u.phone_display}\n"
        f"Score de crédito: {u.credit_score:.1f}%\n"
        f"Saldo: R$ {u.balance:.2f}"
    )
