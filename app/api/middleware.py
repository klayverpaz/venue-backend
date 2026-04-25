from __future__ import annotations
import logging
import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.context import correlation_id

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-Id") or uuid.uuid4().hex
        correlation_id.set(cid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            ms = (time.perf_counter() - start) * 1000
            logger.info(
                "%s %s -> %d (%.1fms)",
                request.method, request.url.path, response.status_code, ms,
            )
            response.headers["X-Correlation-Id"] = cid
            return response
        except Exception:
            ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "%s %s -> ERROR (%.1fms)",
                request.method, request.url.path, ms,
            )
            raise
