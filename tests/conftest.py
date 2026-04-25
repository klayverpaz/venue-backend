import pytest


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch):
    """Defaults previsíveis para os testes unitários."""
    monkeypatch.setenv("BACKEND_ENVIRONMENT", "test")
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_JWT_SECRET_KEY", "test-jwt-secret-fixed-for-determinism")
    monkeypatch.setenv("BACKEND_JWT_ACCESS_TOKEN_EXPIRES_MINUTES", "30")
    monkeypatch.setenv("BACKEND_JWT_REFRESH_TOKEN_EXPIRES_DAYS", "7")
    monkeypatch.setenv("BACKEND_ARGON2_TIME_COST", "1")
    monkeypatch.setenv("BACKEND_ARGON2_MEMORY_COST_KIB", "8")
    monkeypatch.setenv("BACKEND_ARGON2_PARALLELISM", "1")
    yield
