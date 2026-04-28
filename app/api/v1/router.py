"""API router agregador: include cada feature router aqui.

Uso em main.py:
    from app.api.v1.router import api_router
    app.include_router(api_router)
"""
from fastapi import APIRouter

from app.api.v1.admin_resource_types.routes import router as admin_resource_types_router
from app.api.v1.admin_subscriptions.routes import router as admin_subscriptions_router
from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.auth import router as auth_router
from app.api.v1.catalog.routes import router as catalog_router
from app.api.v1.me_bookings.routes import router as me_bookings_router
from app.api.v1.me_subscription.routes import router as me_subscription_router
from app.api.v1.me_notifications.routes import router as me_notifications_router
from app.api.v1.me_resources.routes import router as me_resources_router
from app.api.v1.public_resources.routes import router as public_resources_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(admin_users_router)
api_router.include_router(admin_resource_types_router)
api_router.include_router(admin_subscriptions_router)
api_router.include_router(catalog_router)
api_router.include_router(me_bookings_router)
api_router.include_router(me_subscription_router)
api_router.include_router(me_resources_router)
api_router.include_router(me_notifications_router)
api_router.include_router(public_resources_router)
