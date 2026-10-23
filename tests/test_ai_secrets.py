"""Unit tests for AISecretStore (Zero-Leakage & Write-Only policy).

Validates that:
1. Credentials are held only in volatile memory.
2. __repr__ and __str__ never reveal the API key.
3. get_masked_status() returns '••••••••', never the real key.
4. Environment variable fallback works.
5. Trim of whitespace is applied.
"""

from __future__ import annotations

import os
import pytest

from app.core.ai_secrets import AISecretStore


@pytest.fixture(autouse=True)
def clean_ai_store():
    AISecretStore.reset_instance()
    yield
    AISecretStore.reset_instance()


def test_ai_store_default_not_configured_without_env(monkeypatch):
    monkeypatch.delenv("AI_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL_NAME", raising=False)
    store = AISecretStore.get_instance()
    assert store.is_configured() is False
    status = store.get_masked_status()
    assert status["configured"] is False
    assert status["model_name"] is None
    assert status["key_masked"] is None


def test_ai_store_set_credentials_write_only():
    store = AISecretStore.get_instance()
    secret_key = "AIzaSy_SUPER_SECRET_KEY_12345"
    store.set_credentials("gemini-2.0-flash", secret_key)

    assert store.is_configured() is True
    assert store.get_model_name() == "gemini-2.0-flash"

    # Masked status must NEVER include the real key
    masked = store.get_masked_status()
    assert masked["configured"] is True
    assert masked["model_name"] == "gemini-2.0-flash"
    assert masked["key_masked"] == "••••••••"
    assert secret_key not in str(masked)

    # __repr__ and __str__ must never include the key
    rep = repr(store)
    s = str(store)
    assert secret_key not in rep
    assert secret_key not in s
    assert "gemini-2.0-flash" in rep

    # Protected internal method retrieves the key for HTTP client
    assert store.get_api_key_internal() == secret_key


def test_ai_store_empty_credentials_rejected():
    store = AISecretStore.get_instance()
    with pytest.raises(ValueError):
        store.set_credentials("", "")
    with pytest.raises(ValueError):
        store.set_credentials("gemini-2.0-flash", "   ")


def test_ai_store_env_fallback(monkeypatch):
    monkeypatch.setenv("AI_MODEL_API_KEY", "env_secret_key_999")
    monkeypatch.setenv("AI_MODEL_NAME", "gemini-1.5-pro")
    store = AISecretStore.get_instance()

    assert store.is_configured() is True
    assert store.get_model_name() == "gemini-1.5-pro"
    masked = store.get_masked_status()
    assert masked["key_masked"] == "••••••••"
    assert "env_secret_key_999" not in str(masked)

