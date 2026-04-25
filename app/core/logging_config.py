from __future__ import annotations
import logging
import os
import sys
from app.core.context import correlation_id


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get()
        return True


def setup_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(correlation_id)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    handler.addFilter(CorrelationIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
