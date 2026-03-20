"""AI-enhanced resume parser wrapper.

Wraps an AI provider's parse_resume() call, validates the returned schema,
and ensures required keys are present with correct types.
"""

from typing import Any, Protocol


class ResumeParserProvider(Protocol):
    """Minimal interface expected from an AI provider."""

    def parse_resume(self, text: str) -> dict[str, Any]:
        ...


_REQUIRED_LIST_KEYS = ("career_history", "bullets", "skills")


def _validate_result(result: Any) -> dict[str, Any]:
    """Ensure required keys exist and are lists. Add defaults for missing keys."""
    if not isinstance(result, dict):
        raise ValueError(f"AI provider returned {type(result).__name__}, expected dict")

    for key in _REQUIRED_LIST_KEYS:
        if key not in result:
            result[key] = []
        elif not isinstance(result[key], list):
            raise ValueError(f"Expected list for key '{key}', got {type(result[key]).__name__}")

    if "confidence" not in result:
        result["confidence"] = 0.9  # AI parsers assumed high-confidence by default

    if "education" not in result:
        result["education"] = []

    return result


def parse_resume_ai(text: str, provider: ResumeParserProvider) -> dict[str, Any]:
    """Parse resume text using an AI provider, with schema validation.

    Args:
        text: Full resume plain text.
        provider: Object with a parse_resume(text) -> dict method.

    Returns:
        Validated dict with career_history, bullets, skills, education, confidence.

    Raises:
        ValueError: If provider returns an invalid schema.
        Any exception from provider.parse_resume() propagates to caller.
    """
    result = provider.parse_resume(text)
    return _validate_result(result)
