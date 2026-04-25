from __future__ import annotations
import logging
from typing import TypeVar
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from app.domain.shared.result import Result

T = TypeVar("T")
logger = logging.getLogger(__name__)


def unwrap(result: Result[T]) -> T:
    if result.is_success:
        return result.value  # type: ignore[return-value]
    raise HTTPException(
        status_code=result.status_code or 500,
        detail=result.error or "Erro interno.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def on_unhandled(request: Request, exc: Exception):
        logger.exception(
            "Unhandled error on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={"detail": f"{exc.__class__.__name__}: internal error."},
        )
