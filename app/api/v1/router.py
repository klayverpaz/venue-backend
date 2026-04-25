"""API router agregador: include cada feature router aqui.

Uso em main.py:
    from app.api.v1.router import api_router
    app.include_router(api_router)
"""
from fastapi import APIRouter

from app.api.v1.admin_resource_types.routes import router as admin_resource_types_router
from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.auth import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(admin_users_router)
api_router.include_router(admin_resource_types_router)
