import pytest


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch):
    """Defaults previsíveis para os testes unitários."""
    monkeypatch.setenv("BACKEND_ENVIRONMENT", "test")
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    yield
