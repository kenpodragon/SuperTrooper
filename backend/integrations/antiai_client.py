"""
AntiAI / GhostBusters REST client.

Connects to the GhostBusters API for AI detection and humanization.
Purely optional — all methods return None on connection failure,
callers handle gracefully.
"""

import logging
import requests

log = logging.getLogger(__name__)

# Default timeout: 5s for health, 30s for analysis/rewrite (AI calls can be slow)
HEALTH_TIMEOUT = 5
ANALYSIS_TIMEOUT = 30


def _get_config():
    """Load AntiAI config from settings table."""
    try:
        import db
        row = db.query_one("SELECT integrations FROM settings WHERE id = 1")
        if row and row.get("integrations"):
            integrations = row["integrations"]
            if isinstance(integrations, str):
                import json
                integrations = json.loads(integrations)
            return integrations.get("antiai", {})
    except Exception as e:
        log.warning("Failed to load AntiAI config: %s", e)
    return {}


def _get_api_url() -> str:
    """Get the AntiAI API base URL from config."""
    config = _get_config()
    url = config.get("api_url", "").rstrip("/")
    return url if url else ""


def is_configured() -> bool:
    """Check if AntiAI is configured with a URL."""
    return bool(_get_api_url())


def is_enabled() -> bool:
    """Check if AntiAI is both configured and enabled."""
    config = _get_config()
    return bool(config.get("enabled")) and bool(config.get("api_url"))


def health_check() -> dict:
    """Test AntiAI API connectivity."""
    url = _get_api_url()
    if not url:
        return {
            "status": "not_configured",
            "message": "AntiAI API URL not set. Configure in Settings > Integrations.",
        }

    try:
        resp = requests.get(f"{url}/api/health", timeout=HEALTH_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "status": "connected",
                "message": "GhostBusters API is healthy",
                "api_url": url,
                "details": data,
            }
        else:
            return {
                "status": "error",
                "message": f"Health check returned {resp.status_code}",
                "api_url": url,
            }
    except requests.ConnectionError:
        return {
            "status": "disconnected",
            "message": f"Cannot reach GhostBusters at {url}. Is it running?",
            "api_url": url,
        }
    except requests.Timeout:
        return {"status": "error", "message": "Health check timed out", "api_url": url}
    except Exception as e:
        return {"status": "error", "message": str(e), "api_url": url}


def analyze(text: str, use_ai: bool = None) -> dict | None:
    """
    Scan text for AI-generated patterns.

    Returns dict with overall_score (0-100), sentence_scores, detected_patterns.
    Returns None if AntiAI is unavailable.
    """
    if not is_enabled():
        return None

    url = _get_api_url()
    try:
        payload = {"text": text}
        if use_ai is not None:
            payload["use_ai"] = use_ai

        resp = requests.post(f"{url}/api/analyze", json=payload, timeout=ANALYSIS_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        else:
            log.warning("AntiAI analyze returned %d: %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        log.warning("AntiAI analyze failed: %s", e)
        return None


def rewrite(text: str, voice_profile_id: int = None, use_ai: bool = None) -> dict | None:
    """
    Humanize AI-flagged text.

    Returns dict with rewritten_text, changes_made, before/after scores.
    Returns None if AntiAI is unavailable.
    """
    if not is_enabled():
        return None

    url = _get_api_url()
    try:
        payload = {"text": text}
        if voice_profile_id is not None:
            payload["voice_profile_id"] = voice_profile_id
        if use_ai is not None:
            payload["use_ai"] = use_ai

        resp = requests.post(f"{url}/api/rewrite", json=payload, timeout=ANALYSIS_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        else:
            log.warning("AntiAI rewrite returned %d: %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        log.warning("AntiAI rewrite failed: %s", e)
        return None


def score(text: str) -> dict | None:
    """
    Quick heuristics-only AI detection score.

    Returns dict with overall_score (0-100), no AI calls.
    Returns None if AntiAI is unavailable.
    """
    if not is_enabled():
        return None

    url = _get_api_url()
    try:
        resp = requests.post(f"{url}/api/score", json={"text": text}, timeout=HEALTH_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        log.warning("AntiAI score failed: %s", e)
        return None


def scan_and_humanize(text: str, threshold: int = 50, max_iterations: int = 3) -> dict:
    """
    Full pipeline: scan -> humanize if above threshold -> re-scan.

    Returns dict with:
      - original_score: initial AI detection score
      - final_score: score after humanization (if applied)
      - text: final text (humanized or original)
      - humanized: bool whether humanization was applied
      - iterations: number of humanization passes
    """
    if not is_enabled():
        return {"text": text, "humanized": False, "skipped": True, "reason": "AntiAI not configured"}

    # Initial scan
    initial = analyze(text, use_ai=False)
    if not initial:
        return {"text": text, "humanized": False, "skipped": True, "reason": "Scan failed"}

    original_score = initial.get("overall_score", 0)
    if original_score < threshold:
        return {
            "text": text,
            "humanized": False,
            "original_score": original_score,
            "final_score": original_score,
            "iterations": 0,
        }

    # Humanize loop
    current_text = text
    iterations = 0
    for i in range(max_iterations):
        result = rewrite(current_text)
        if not result or not result.get("rewritten_text"):
            break
        current_text = result["rewritten_text"]
        iterations = i + 1

        # Re-scan
        rescan = analyze(current_text, use_ai=False)
        if rescan and rescan.get("overall_score", 100) < threshold:
            break

    # Final score
    final = analyze(current_text, use_ai=False)
    final_score = final.get("overall_score", original_score) if final else original_score

    return {
        "text": current_text,
        "humanized": True,
        "original_score": original_score,
        "final_score": final_score,
        "iterations": iterations,
    }
