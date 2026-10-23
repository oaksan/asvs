from __future__ import annotations

import os
import threading
from typing import Any


class AISecretStore:
    """Thread-safe in-memory singleton for volatile AI credentials.

    Strict Write-Only policy: The API key is stored only in volatile memory
    and is never exposed in REST responses, string representations (__str__, __repr__),
    database rows, audit logs, or reports.
    Supports both Google Gemini and Azure OpenAI (Inference Service).
    """

    _instance: AISecretStore | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._lock_state = threading.Lock()
        env_key = os.environ.get("AI_MODEL_API_KEY", "").strip() or None
        env_model = os.environ.get("AI_MODEL_NAME", "gemini-2.0-flash").strip() or None
        self._api_key: str | None = env_key
        self._model_name: str | None = env_model if env_key else None
        self._provider: str = os.environ.get("AI_PROVIDER", "gemini").strip() or "gemini"
        self._resource_name: str | None = os.environ.get("AZURE_OPENAI_RESOURCE", "").strip() or None
        self._deployment_id: str | None = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "").strip() or None
        self._api_version: str = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01").strip() or "2024-06-01"

    @classmethod
    def get_instance(cls) -> AISecretStore:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for hermetic tests)."""
        with cls._lock:
            cls._instance = None

    def set_credentials(
        self,
        model_name: str,
        api_key: str,
        provider: str = "gemini",
        resource_name: str | None = None,
        deployment_id: str | None = None,
        api_version: str = "2024-06-01",
    ) -> None:
        """Sets the AI model and API key in memory."""
        cleaned_model = model_name.strip() if model_name else ""
        cleaned_key = api_key.strip() if api_key else ""
        if not cleaned_model or not cleaned_key:
            raise ValueError("model_name and api_key must not be empty.")

        with self._lock_state:
            self._model_name = cleaned_model
            self._api_key = cleaned_key
            self._provider = provider.strip() or "gemini"
            self._resource_name = resource_name.strip() if resource_name else None
            self._deployment_id = deployment_id.strip() if deployment_id else cleaned_model
            self._api_version = api_version.strip() if api_version else "2024-06-01"

    def clear_credentials(self) -> None:
        """Clears volatile credentials from memory."""
        with self._lock_state:
            self._api_key = None
            self._model_name = None
            self._resource_name = None
            self._deployment_id = None

    def is_configured(self) -> bool:
        """Returns True if model and key are set."""
        with self._lock_state:
            return bool(self._api_key and self._model_name)

    def get_model_name(self) -> str | None:
        with self._lock_state:
            return self._model_name

    def get_provider(self) -> str:
        with self._lock_state:
            return self._provider

    def get_resource_name(self) -> str | None:
        with self._lock_state:
            return self._resource_name

    def get_deployment_id(self) -> str | None:
        with self._lock_state:
            return self._deployment_id

    def get_api_version(self) -> str:
        with self._lock_state:
            return self._api_version

    def get_masked_status(self) -> dict[str, Any]:
        """Returns masked status without leaking the actual API key."""
        with self._lock_state:
            configured = bool(self._api_key and self._model_name)
            return {
                "configured": configured,
                "model_name": self._model_name if configured else None,
                "key_masked": "••••••••" if configured else None,
                "provider": self._provider,
                "resource_name": self._resource_name if configured else None,
                "deployment_id": self._deployment_id if configured else None,
                "api_version": self._api_version,
            }

    get_status = get_masked_status

    def get_api_key_internal(self) -> str | None:
        """Protected method: returns raw key strictly for internal HTTP ACI client."""
        with self._lock_state:
            return self._api_key

    get_api_key = get_api_key_internal

    def __repr__(self) -> str:
        with self._lock_state:
            return (
                f"<AISecretStore configured={bool(self._api_key and self._model_name)} "
                f"provider={self._provider} model={self._model_name}>"
            )

    def __str__(self) -> str:
        return self.__repr__()
