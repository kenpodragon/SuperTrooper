"""AI provider registry for the SuperTroopers platform."""
import os
import psycopg2
from typing import Optional

from .base import AIProvider
from .claude_provider import ClaudeProvider
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider

PROVIDERS: dict[str, type[AIProvider]] = {
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
}

_DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 5555)),
    "dbname": os.environ.get("DB_NAME", "supertroopers"),
    "user": os.environ.get("DB_USER", "supertroopers"),
    "password": os.environ.get("DB_PASSWORD", "WUHD8fBisb57FS4Q3bdvfuvgnim9fL1c"),
}


def _read_settings() -> tuple[str, bool]:
    """Read ai_provider and ai_enabled from the settings table.
    Returns (provider_name, enabled).
    """
    try:
        conn = psycopg2.connect(**_DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT ai_provider, ai_enabled FROM settings LIMIT 1;")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row is None:
            return ("none", False)
        provider_name, ai_enabled = row
        return (provider_name or "none", bool(ai_enabled))
    except Exception as e:
        # If DB is unavailable, fail gracefully
        return ("none", False)


def get_provider(name: Optional[str] = None) -> Optional[AIProvider]:
    """Return a configured and available AI provider instance, or None.

    If name is None, reads ai_provider and ai_enabled from the settings table.
    Returns None if:
    - ai_enabled is False
    - provider is "none" or unrecognized
    - CLI is not installed / not on PATH
    """
    if name is None:
        name, enabled = _read_settings()
        if not enabled:
            return None

    name = name.lower().strip()
    if name == "none" or name not in PROVIDERS:
        return None

    provider_class = PROVIDERS[name]
    provider = provider_class()

    if not provider.is_available():
        return None

    return provider


def list_providers() -> list[dict]:
    """Return status info for all registered providers."""
    results = []
    for name, provider_class in PROVIDERS.items():
        provider = provider_class()
        health = provider.health_check()
        results.append({
            "name": name,
            "available": health.get("available", False),
            "version": health.get("version"),
            "model": health.get("model"),
        })
    return results
