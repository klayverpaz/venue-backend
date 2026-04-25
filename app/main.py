from __future__ import annotations
import logging
from contextlib import asynccontextmanager

import redis.asyncio as redis_lib
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.error_handler import register_exception_handlers
from app.api.middleware import LoggingMiddleware
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.infrastructure.cache.redis_client import build_redis_pool
from app.infrastructure.db.session import dispose_engine, init_engine

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_engine()
    pool = build_redis_pool()
    redis_client = redis_lib.Redis(connection_pool=pool)
    app.state.redis_client = redis_client
    app.state.redis_pool = pool

    # AI module opcional — só carrega se provider != 'none'
    if settings.ai_provider != "none":
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver
        from app.ai.graph import build_chat_graph
        from app.api.v1.ai_chat import router as ai_chat_router

        checkpointer = AsyncRedisSaver(
            redis_client=redis_client,
            ttl={"default_ttl": 7200, "refresh_on_read": True},
        )
        await checkpointer.asetup()
        app.state.chat_graph = build_chat_graph().compile(checkpointer=checkpointer)
        app.include_router(ai_chat_router)
        logger.info("AI module ativado (provider=%s).", settings.ai_provider)
    else:
        logger.info("AI module desativado (BACKEND_AI_PROVIDER=none).")

    logger.info("Startup completo.")
    yield

    await redis_client.aclose()
    await pool.aclose()
    await dispose_engine()
    logger.info("Recursos liberados.")


app = FastAPI(title="Backend Template", version="0.1.0", lifespan=lifespan)
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)

app.include_router(api_router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


def main() -> None:
    s = get_settings()
    uvicorn.run(
        "app.main:app",
        host=s.host, port=s.port,
        reload=s.environment == "development",
        proxy_headers=True, forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
