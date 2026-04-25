import pytest
from app.core.config import get_settings


def test_settings_carrega_env_com_prefix_backend(monkeypatch):
    monkeypatch.setenv("BACKEND_ENVIRONMENT", "test")
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_HOST", "127.0.0.1")
    monkeypatch.setenv("BACKEND_PORT", "9000")
    get_settings.cache_clear()
    s = get_settings()
    assert s.environment == "test"
    assert str(s.database_url) == "sqlite+aiosqlite:///:memory:"
    assert s.host == "127.0.0.1"
    assert s.port == 9000


def test_settings_exige_database_url(monkeypatch, tmp_path):
    monkeypatch.delenv("BACKEND_DATABASE_URL", raising=False)
    # Aponta env_file para um caminho inexistente para evitar que o .env local
    # forneça DATABASE_URL e mascare a validação obrigatória do campo.
    from app.core.config import Settings
    original = Settings.model_config["env_file"]
    Settings.model_config["env_file"] = tmp_path / "nonexistent.env"
    get_settings.cache_clear()
    try:
        with pytest.raises(Exception):
            get_settings()
    finally:
        Settings.model_config["env_file"] = original
        get_settings.cache_clear()
