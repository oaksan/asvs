"""Cryptographic primitives for ASVS Feature 007.

- AES-256-GCM symmetric authenticated encryption/decryption with unique 12-byte nonce
- HKDF-SHA256 key derivation (256-bit / 32-byte deterministic key)
- PBKDF2-HMAC-SHA256 password hashing (600,000 iterations per OWASP 2024)
- Constant-time password verification via hmac.compare_digest
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from typing import Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

DEFAULT_APP_SECRET = "asvs-default-master-key-change-in-production-v1"
HKDF_INFO = b"asvs-ai-secret-storage"
PBKDF2_ITERATIONS = 600000
SALT_SIZE_BYTES = 32


def derive_key(master_secret: str, salt: bytes | None = None) -> bytes:
    """Derive a deterministic 256-bit (32 bytes) symmetric key using HKDF-SHA256."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=HKDF_INFO,
    )
    return hkdf.derive(master_secret.encode("utf-8"))


def get_default_key() -> bytes:
    """Return the derived symmetric key from environment or default master secret."""
    master = os.environ.get("APP_SECRET_KEY", DEFAULT_APP_SECRET)
    return derive_key(master)


def encrypt_secret(plain_text: str, key: bytes | None = None) -> Tuple[bytes, bytes]:
    """Encrypt plaintext string using AES-256-GCM with a unique 12-byte nonce.

    Returns:
        tuple[bytes, bytes]: (ciphertext_with_tag, nonce)
    """
    sym_key = key or get_default_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(sym_key)
    ciphertext = aesgcm.encrypt(nonce, plain_text.encode("utf-8"), None)
    return ciphertext, nonce


def decrypt_secret(ciphertext: bytes, nonce: bytes, key: bytes | None = None) -> str:
    """Decrypt AES-256-GCM ciphertext using nonce and symmetric key.

    Raises:
        cryptography.exceptions.InvalidTag: If ciphertext or nonce is altered.
    """
    sym_key = key or get_default_key()
    aesgcm = AESGCM(sym_key)
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return decrypted_bytes.decode("utf-8")


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 600,000 iterations and 32-byte salt.

    Format: 'pbkdf2:sha256:600000:<salt_hex>:<hash_hex>'
    """
    salt = secrets.token_bytes(SALT_SIZE_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2:sha256:{PBKDF2_ITERATIONS}:{salt.hex()}:{derived.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against PBKDF2 hash using constant-time comparison."""
    try:
        parts = hashed_password.split(":")
        if len(parts) != 5:
            return False
        scheme, algo, iters_str, salt_hex, hash_hex = parts
        if scheme != "pbkdf2" or algo != "sha256":
            return False
        iterations = int(iters_str)
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)
        computed = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(computed, expected_hash)
    except Exception:
        return False

