from __future__ import annotations
from datetime import datetime, timezone
from langchain_core.tools import tool


@tool
def get_current_time() -> str:
    """Retorna a hora atual em UTC no formato ISO-8601."""
    return datetime.now(timezone.utc).isoformat()
