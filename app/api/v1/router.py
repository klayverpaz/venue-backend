"""API router agregador: include cada feature router aqui.

Uso em main.py:
    from app.api.v1.router import api_router
    app.include_router(api_router)

Features que dependem de configuração runtime (ex.: ai_chat depende de
ai_provider) continuam sendo incluídas condicionalmente em main.py
no lifespan, fora deste agregador.
"""
from fastapi import APIRouter

from app.api.v1.users import router as users_router
from app.api.v1.reports import router as reports_router

api_router = APIRouter()
api_router.include_router(users_router)
api_router.include_router(reports_router)
