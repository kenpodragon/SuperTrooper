"""Resume parser dispatcher.

Uses AI provider if given, falls back to rule-based parser on any failure.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


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
            result = parse_resume_ai(text, provider)
            logger.info("AI parser succeeded: %d career entries, %d skills",
                        len(result.get("career_history", [])),
                        len(result.get("skills", [])))
            return result
        except Exception as e:
            logger.warning("AI parser failed, falling back to rule-based: %s", e)

    from .rule_based import parse_resume_text
    return parse_resume_text(text)
