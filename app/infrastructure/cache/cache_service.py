from __future__ import annotations
import json
from typing import Any
import redis.asyncio as redis_lib
from app.domain.shared.result import Result


class CacheService:
    def __init__(self, client: redis_lib.Redis) -> None:
        self._c = client

    async def get(self, key: str) -> Result[Any | None]:
        try:
            raw = await self._c.get(key)
            return Result.success(json.loads(raw) if raw else None)
        except Exception as e:
            return Result.from_exception(e, prefix="CacheService.get")

    async def set(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> Result[None]:
        try:
            await self._c.set(key, json.dumps(value), ex=ttl_seconds)
            return Result.success(None)
        except Exception as e:
            return Result.from_exception(e, prefix="CacheService.set")

    async def delete(self, key: str) -> Result[None]:
        try:
            await self._c.delete(key)
            return Result.success(None)
        except Exception as e:
            return Result.from_exception(e, prefix="CacheService.delete")
