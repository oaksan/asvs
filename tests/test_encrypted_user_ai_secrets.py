"""Automated tests for Encrypted-at-Rest AI Secrets and Multi-User Isolation (Feature 007).

Spec Reference: specs/007-auth-rbac-and-encrypted-user-ai-config/spec.md
Research: specs/007-auth-rbac-and-encrypted-user-ai-config/research.md
Tasks: T003
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.ai_secrets import AISecretStore
from app.main import app
from app.models import User, UserAIConfig
from tests.conftest import create_test_user


# ==============================================================================
# 1. Testes Unitários de Criptografia (`app/core/crypto.py`)
# ==============================================================================


def test_crypto_derive_key_deterministic_and_256_bits():
    """Derives deterministic 256-bit (32 bytes) symmetric key via HKDF-SHA256."""
    from app.core.crypto import derive_key

    key1 = derive_key("test-master-secret-key-1")
    key2 = derive_key("test-master-secret-key-1")
    key3 = derive_key("different-master-secret-key-2")

    assert isinstance(key1, bytes)
    assert len(key1) == 32, "A chave derivada deve ter exatamente 256 bits (32 bytes)."
    assert key1 == key2, "Derivações da mesma chave mestra devem ser determinísticas."
    assert key1 != key3, "Chaves mestras diferentes devem produzir chaves derivadas distintas."


def test_crypto_aes_256_gcm_encrypt_decrypt_roundtrip():
    """AES-256-GCM correctly encrypts plaintext and decrypts with authentication tag."""
    from app.core.crypto import decrypt_secret, encrypt_secret

    plaintext = "AIzaSy_SUPER_CONFIDENTIAL_GEMINI_API_KEY_456"
    ciphertext, nonce = encrypt_secret(plaintext)

    assert isinstance(ciphertext, bytes)
    assert isinstance(nonce, bytes)
    assert len(nonce) == 12, "O nonce AES-GCM deve possuir 12 bytes aleatórios."
    assert plaintext.encode() not in ciphertext, "O ciphertext não pode conter o plaintext em claro."

    decrypted = decrypt_secret(ciphertext, nonce)
    assert decrypted == plaintext, "A decifragem com nonce e tag válidos deve restaurar exatamente o plaintext original."


def test_crypto_aes_256_gcm_unique_nonce_per_encryption():
    """Consecutive encryptions of identical plaintext produce distinct nonces and ciphertexts."""
    from app.core.crypto import encrypt_secret

    plaintext = "identical-secret-key"
    c1, n1 = encrypt_secret(plaintext)
    c2, n2 = encrypt_secret(plaintext)

    assert n1 != n2, "Cada operação de cifra DEVE gerar um nonce aleatório exclusivo."
    assert c1 != c2, "Ciphertexts devem ser distintos devido ao nonce único."


def test_crypto_aes_256_gcm_tampered_ciphertext_fails():
    """Tampering with a single byte in ciphertext or auth tag raises cryptographic error."""
    from app.core.crypto import decrypt_secret, encrypt_secret

    plaintext = "unaltered-secret-key"
    ciphertext, nonce = encrypt_secret(plaintext)

    tampered_bytes = bytearray(ciphertext)
    tampered_bytes[0] ^= 0xFF
    tampered_ciphertext = bytes(tampered_bytes)

    with pytest.raises(Exception):
        decrypt_secret(tampered_ciphertext, nonce)


def test_crypto_aes_256_gcm_tampered_nonce_fails():
    """Tampering with nonce causes decryption to fail."""
    from app.core.crypto import decrypt_secret, encrypt_secret

    plaintext = "unaltered-secret-key"
    ciphertext, nonce = encrypt_secret(plaintext)

    tampered_nonce = bytearray(nonce)
    tampered_nonce[0] ^= 0xAA

    with pytest.raises(Exception):
        decrypt_secret(ciphertext, bytes(tampered_nonce))


def test_crypto_password_hash_pbkdf2_format_and_verification():
    """Password hashing follows pbkdf2:sha256:600000:<salt_hex>:<hash_hex> with constant-time verification."""
    from app.core.crypto import hash_password, verify_password

    password = "MyUserStrongPassword123!"
    pw_hash = hash_password(password)

    assert isinstance(pw_hash, str)
    parts = pw_hash.split(":")
    assert len(parts) == 5
    assert parts[0] == "pbkdf2"
    assert parts[1] == "sha256"
    assert int(parts[2]) >= 600000, "Mínimo 600.000 iterações per OWASP Cheat Sheet 2024."
    assert len(bytes.fromhex(parts[3])) == 32, "Salt deve possuir 32 bytes de alta entropia."

    assert verify_password(password, pw_hash) is True
    assert verify_password("WrongPassword123!", pw_hash) is False


def test_crypto_password_hash_generates_unique_salts():
    """Hashing same password twice yields distinct salts and hashes."""
    from app.core.crypto import hash_password

    h1 = hash_password("same_pass")
    h2 = hash_password("same_pass")
    assert h1 != h2, "Salts individuais aleatórios devem evitar hashes duplicados."


# ==============================================================================
# 2. Persistência Criptografada em Repouso no SQLite (Zero-Leakage)
# ==============================================================================


def test_ai_config_persists_ciphertext_in_sqlite_zero_leakage(
    unauth_client: TestClient, db_session: Session
):
    """US3 Scenarios 1 & 2 / FR-013 / SC-004: POST /api/ai/config persists AES-256-GCM ciphertext without raw keys."""
    raw_key = "AIzaSy_CONFIDENTIAL_USER_API_KEY_9999"
    user = create_test_user(db_session, "analyst_crypto", "PassCrypto123!", role="user")

    login_resp = unauth_client.post(
        "/api/auth/login",
        json={"username": "analyst_crypto", "password": "PassCrypto123!"},
    )
    assert login_resp.status_code == 200

    cfg_payload = {
        "provider": "gemini",
        "model_name": "gemini-2.0-flash",
        "api_key": raw_key,
    }
    cfg_resp = unauth_client.post("/api/ai/config", json=cfg_payload)
    assert cfg_resp.status_code == 200
    assert cfg_resp.json()["configured"] is True
    assert cfg_resp.json()["key_masked"] == "••••••••"
    assert raw_key not in str(cfg_resp.json())

    db_session.expire_all()
    user_cfg = db_session.exec(
        select(UserAIConfig).where(UserAIConfig.user_id == user.id)
    ).first()

    assert user_cfg is not None
    assert user_cfg.provider == "gemini"
    assert user_cfg.model_name == "gemini-2.0-flash"
    assert user_cfg.key_masked == "••••••••"
    assert isinstance(user_cfg.encrypted_api_key, bytes)
    assert isinstance(user_cfg.nonce, bytes)
    assert len(user_cfg.nonce) == 12

    assert raw_key.encode() not in user_cfg.encrypted_api_key
    assert not hasattr(user_cfg, "api_key")


def test_ai_config_azure_settings_persistence(
    unauth_client: TestClient, db_session: Session
):
    """US3 / FR-013: Azure OpenAI service_settings persists encrypted without raw key leakage."""
    azure_key = "azure-super-secret-key-7777"
    user = create_test_user(db_session, "analyst_azure", "PassAzure123!", role="user")

    unauth_client.post(
        "/api/auth/login",
        json={"username": "analyst_azure", "password": "PassAzure123!"},
    )

    payload = {
        "service": "azureopenai",
        "service_settings": {
            "resource_name": "corp-openai-res",
            "deployment_id": "asvs-gpt4o",
            "api_version": "2024-06-01",
            "api_key": azure_key,
        },
    }
    resp = unauth_client.post("/api/ai/config", json=payload)
    assert resp.status_code == 200

    user_cfg = db_session.exec(
        select(UserAIConfig).where(UserAIConfig.user_id == user.id)
    ).first()
    assert user_cfg is not None
    assert user_cfg.provider == "azureopenai"
    assert user_cfg.resource_name == "corp-openai-res"
    assert user_cfg.deployment_id == "asvs-gpt4o"
    assert azure_key.encode() not in user_cfg.encrypted_api_key


# ==============================================================================
# 3. Decifragem Automática no Login e Isolamento de Sessão
# ==============================================================================


def test_login_automatically_decrypts_saved_ai_config_into_session(
    unauth_client: TestClient, db_session: Session
):
    """US3 Scenario 3 / FR-015 / SC-005: User with previously saved AI credentials logs in; session decrypts key automatically."""
    raw_key = "AIzaSy_SAVED_BEFORE_LOGIN_KEY_123"
    user = create_test_user(db_session, "user_with_saved_ai", "SecretPass123!", role="user")

    unauth_client.post(
        "/api/auth/login",
        json={"username": "user_with_saved_ai", "password": "SecretPass123!"},
    )
    unauth_client.post(
        "/api/ai/config",
        json={"provider": "gemini", "model_name": "gemini-2.0-flash", "api_key": raw_key},
    )
    unauth_client.post("/api/auth/logout")

    new_client = TestClient(app)
    login_resp = new_client.post(
        "/api/auth/login",
        json={"username": "user_with_saved_ai", "password": "SecretPass123!"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert login_data["ai_configured"] is True
    assert login_data["ai_model_name"] == "gemini-2.0-flash"

    st_resp = new_client.get("/api/ai/status")
    assert st_resp.status_code == 200
    st_data = st_resp.json()
    assert st_data["configured"] is True
    assert st_data["model_name"] == "gemini-2.0-flash"
    assert st_data["key_masked"] == "••••••••"


def test_user_without_ai_config_login_returns_ai_configured_false(
    unauth_client: TestClient, db_session: Session
):
    """US3: User without saved AI config gets ai_configured=False on login."""
    create_test_user(db_session, "user_no_ai", "PassNoAI123!", role="user")

    login_resp = unauth_client.post(
        "/api/auth/login",
        json={"username": "user_no_ai", "password": "PassNoAI123!"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["ai_configured"] is False

    st_resp = unauth_client.get("/api/ai/status")
    assert st_resp.status_code == 200
    assert st_resp.json()["configured"] is False


# ==============================================================================
# 4. Chat Playground Utilizando Credenciais da Sessão
# ==============================================================================


@pytest.mark.asyncio
async def test_chat_test_uses_authenticated_user_session_credentials(
    unauth_client: TestClient, db_session: Session
):
    """US3 / FR-015: POST /api/ai/chat-test consumes in-memory credentials from the active user session."""
    user = create_test_user(db_session, "user_chat", "ChatPass123!", role="user")

    unauth_client.post(
        "/api/auth/login",
        json={"username": "user_chat", "password": "ChatPass123!"},
    )
    unauth_client.post(
        "/api/ai/config",
        json={"provider": "gemini", "model_name": "gemini-2.0-flash", "api_key": "valid-chat-key"},
    )

    mock_chat_response = {
        "ok": True,
        "response_text": "Análise estática concluída com sucesso.",
        "latency_ms": 42,
        "model_used": "gemini-2.0-flash",
        "provider": "gemini",
    }

    with patch("app.aci.ai_aci.chat_with_ai", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = mock_chat_response

        resp = unauth_client.post(
            "/api/ai/chat-test",
            json={"message": "Qual é a recomendação para o requisito V1.2.1?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["response_text"] == "Análise estática concluída com sucesso."
        assert mock_ai.called


# ==============================================================================
# 5. Expurgo Seguro no Logout
# ==============================================================================


def test_logout_purges_in_memory_decrypted_secrets(
    unauth_client: TestClient, db_session: Session
):
    """US3 Scenario 5 / FR-017: POST /api/auth/logout invalidates session and purges volatile secrets."""
    create_test_user(db_session, "user_logout_test", "LogoutPass123!", role="user")

    unauth_client.post(
        "/api/auth/login",
        json={"username": "user_logout_test", "password": "LogoutPass123!"},
    )
    unauth_client.post(
        "/api/ai/config",
        json={"provider": "gemini", "model_name": "gemini-2.0-flash", "api_key": "secret-to-purge"},
    )

    logout_resp = unauth_client.post("/api/auth/logout")
    assert logout_resp.status_code == 200

    st_resp = unauth_client.get("/api/ai/status")
    assert st_resp.status_code == 401

