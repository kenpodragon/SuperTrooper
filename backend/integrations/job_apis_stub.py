"""Stubs for job APIs that require API keys. Swap in real keys via env vars."""

import os


def fetch_usajobs(keyword: str = None, location: str = None) -> dict:
    """USAJobs API — requires USAJOBS_API_KEY and USAJOBS_USER_AGENT env vars.
    Register at: https://developer.usajobs.gov/apirequest/
    """
    key = os.environ.get("USAJOBS_API_KEY")
    user_agent = os.environ.get("USAJOBS_USER_AGENT")
    if not key or not user_agent:
        return {
            "error": "API key required",
            "source": "usajobs",
            "setup_instructions": (
                "1. Register at https://developer.usajobs.gov/apirequest/\n"
                "2. Set USAJOBS_API_KEY=<your_key> in backend/.env\n"
                "3. Set USAJOBS_USER_AGENT=<your_email> in backend/.env"
            ),
        }
    # Real implementation: GET https://data.usajobs.gov/api/search
    # Headers: Authorization-Key, User-Agent
    # Params: Keyword, LocationName, ResultsPerPage
    return {"error": "Not implemented — add real fetch logic after setting API key", "source": "usajobs"}


def fetch_adzuna(keyword: str = None, location: str = None, page: int = 1) -> dict:
    """Adzuna API — requires ADZUNA_APP_ID and ADZUNA_APP_KEY env vars.
    Register at: https://developer.adzuna.com/
    """
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return {
            "error": "API key required",
            "source": "adzuna",
            "setup_instructions": (
                "1. Register at https://developer.adzuna.com/\n"
                "2. Set ADZUNA_APP_ID=<your_id> in backend/.env\n"
                "3. Set ADZUNA_APP_KEY=<your_key> in backend/.env"
            ),
        }
    # Real implementation: GET https://api.adzuna.com/v1/api/jobs/us/search/{page}
    # Params: app_id, app_key, what, where, results_per_page
    return {"error": "Not implemented — add real fetch logic after setting API key", "source": "adzuna"}


def fetch_jooble(keyword: str = None, location: str = None) -> dict:
    """Jooble API — requires JOOBLE_API_KEY env var.
    Register at: https://jooble.org/api/about
    """
    key = os.environ.get("JOOBLE_API_KEY")
    if not key:
        return {
            "error": "API key required",
            "source": "jooble",
            "setup_instructions": (
                "1. Register at https://jooble.org/api/about\n"
                "2. Set JOOBLE_API_KEY=<your_key> in backend/.env"
            ),
        }
    # Real implementation: POST https://jooble.org/api/{key}
    # Body: { "keywords": keyword, "location": location }
    return {"error": "Not implemented — add real fetch logic after setting API key", "source": "jooble"}


STUB_REGISTRY = {
    "usajobs": fetch_usajobs,
    "adzuna": fetch_adzuna,
    "jooble": fetch_jooble,
}
