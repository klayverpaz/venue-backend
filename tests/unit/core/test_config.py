import pytest
from pydantic import ValidationError
from app.core.config import get_settings, Settings


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


def test_settings_jwt_defaults(monkeypatch):
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_JWT_SECRET_KEY", "abc")
    get_settings.cache_clear()
    s = get_settings()
    assert s.jwt_secret_key.get_secret_value() == "abc"
    assert s.jwt_algorithm == "HS256"
    assert s.jwt_access_token_expires_minutes == 30
    assert s.jwt_refresh_token_expires_days == 7


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


def test_trial_duration_days_default_is_3(monkeypatch):
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.delenv("BACKEND_TRIAL_DURATION_DAYS", raising=False)
    get_settings.cache_clear()
    s = Settings()
    assert s.trial_duration_days == 3


def test_trial_duration_days_env_override(monkeypatch):
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_TRIAL_DURATION_DAYS", "7")
    get_settings.cache_clear()
    s = Settings()
    assert s.trial_duration_days == 7


def test_trial_duration_days_must_be_positive(monkeypatch):
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_TRIAL_DURATION_DAYS", "0")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        Settings()
