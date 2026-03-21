"""AI routing: check provider availability, route inference through AI or fall back to Python."""

import logging

logger = logging.getLogger(__name__)


def ai_available() -> bool:
    """Check if any AI provider is configured and healthy."""
    try:
        from ai_providers import get_provider
        provider = get_provider()
        return provider is not None and provider.available
    except Exception:
        return False


def route_inference(task: str, context: dict, python_fallback, ai_handler=None):
    """Route an inference task through AI if available, otherwise Python fallback.

    Args:
        task: Description of the inference task (for logging).
        context: Data needed for the inference (JD text, etc.).
        python_fallback: Callable(context) -> dict for rule-based processing.
        ai_handler: Callable(context) -> dict for AI-enhanced processing (optional).

    Returns:
        Dict result from whichever handler ran, with _analysis_mode metadata.
    """
    used_ai = False

    if ai_handler and ai_available():
        try:
            logger.info(f"AI routing: using AI for '{task}'")
            result = ai_handler(context)
            used_ai = True
        except Exception as e:
            logger.warning(f"AI routing: AI failed for '{task}': {e}, falling back to Python")
            result = python_fallback(context)
    else:
        logger.info(f"AI routing: using Python fallback for '{task}'")
        result = python_fallback(context)

    if isinstance(result, dict):
        result["analysis_mode"] = "ai" if used_ai else "rule_based"

    return result
