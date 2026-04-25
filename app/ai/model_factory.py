from __future__ import annotations
from functools import lru_cache
from langchain_core.language_models import BaseChatModel
from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_chat_model() -> BaseChatModel:
    s = get_settings()
    common = dict(temperature=s.ai_temperature, streaming=True)
    provider = s.ai_provider.lower()
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=s.ai_model_name,
            api_key=s.ai_api_key.get_secret_value(),
            **common,
        )
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=s.ai_model_name,
            api_key=s.ai_api_key.get_secret_value(),
            **common,
        )
    raise ValueError(f"AI provider não suportado: {s.ai_provider}")
