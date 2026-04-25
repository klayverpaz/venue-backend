from __future__ import annotations
import redis.asyncio as redis_lib
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from app.core.config import get_settings


def build_redis_pool() -> redis_lib.ConnectionPool:
    s = get_settings()
    kwargs: dict = dict(
        host=s.redis_host,
        port=s.redis_port,
        decode_responses=False,
        socket_keepalive=True,
        health_check_interval=30,
        retry=Retry(NoBackoff(), retries=1),
        retry_on_error=[ConnectionError, TimeoutError, OSError, RuntimeError],
    )
    if s.environment != "development":
        kwargs["connection_class"] = redis_lib.SSLConnection
    if s.redis_username:
        kwargs["username"] = s.redis_username
    if s.redis_password.get_secret_value():
        kwargs["password"] = s.redis_password.get_secret_value()
    return redis_lib.ConnectionPool(**kwargs)
