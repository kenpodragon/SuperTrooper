"""Resume parser dispatcher.

Uses AI provider if given, falls back to rule-based parser on any failure.
"""

from typing import Any, Optional


def parse_resume(text: str, provider: Optional[Any] = None) -> dict[str, Any]:
    """Parse resume text. Uses AI if provider given, falls back to rule-based.

    Args:
        text: Full resume plain text.
        provider: Optional AI provider with parse_resume(text) -> dict method.
                  If None or if AI parsing raises, falls back to rule-based.

    Returns:
        dict with career_history, bullets, skills, education, confidence.
    """
    if provider:
        try:
            from .ai_enhanced import parse_resume_ai
            return parse_resume_ai(text, provider)
        except Exception:
            pass  # Fall back to rule-based

    from .rule_based import parse_resume_text
    return parse_resume_text(text)
