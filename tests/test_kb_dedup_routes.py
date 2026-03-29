"""Integration tests for KB dedup API routes.

These tests hit the live Flask server at localhost:8055.
Ensure `docker compose up -d` is running before executing.

Run:
    cd code && python -m pytest tests/test_kb_dedup_routes.py -v
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

BASE_URL = "http://localhost:8055"

# ---------------------------------------------------------------------------
# Fixture — uses requests (same pattern as existing tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def api():
    import requests
    session = requests.Session()
    session.base_url = BASE_URL
    return session


def post(api, path, body):
    import requests
    return requests.post(f"{BASE_URL}{path}", json=body)


# ---------------------------------------------------------------------------
# POST /api/kb/dedup/scan
# ---------------------------------------------------------------------------

def test_scan_skills_returns_dedup_groups(api):
    """Scan skills — should return auto_merge, needs_review, junk keys."""
    resp = post(api, "/api/kb/dedup/scan", {"entity_type": "skills"})
    assert resp.status_code == 200
    data = resp.json()
    assert "auto_merge" in data
    assert "needs_review" in data
    assert "junk" in data


def test_scan_invalid_entity_returns_400(api):
    """Scan with unknown entity_type — should return 400."""
    resp = post(api, "/api/kb/dedup/scan", {"entity_type": "nonexistent_table"})
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data


def test_scan_missing_entity_returns_400(api):
    """Scan with no entity_type at all — should return 400."""
    resp = post(api, "/api/kb/dedup/scan", {})
    assert resp.status_code == 400


def test_scan_career_history_returns_employer_or_auto_merge(api):
    """Scan career_history — should return employer_merge and/or auto_merge."""
    resp = post(api, "/api/kb/dedup/scan", {"entity_type": "career_history"})
    assert resp.status_code == 200
    data = resp.json()
    # career_history returns employer_merge + role_merge (not auto_merge)
    has_career_keys = "employer_merge" in data or "auto_merge" in data
    assert has_career_keys, f"Unexpected keys: {list(data.keys())}"


@pytest.mark.slow
def test_scan_bullets_returns_standard_keys(api):
    """Scan bullets — standard dedup keys.

    NOTE: Marked slow — group_bullets runs O(n²) similarity on 800+ records
    and can take 2+ minutes. Run with: pytest -m slow
    """
    resp = post(api, "/api/kb/dedup/scan", {"entity_type": "bullets"})
    assert resp.status_code == 200
    data = resp.json()
    assert "auto_merge" in data or "needs_review" in data


def test_scan_education_returns_standard_keys(api):
    """Scan education — standard dedup keys."""
    resp = post(api, "/api/kb/dedup/scan", {"entity_type": "education"})
    assert resp.status_code == 200
    data = resp.json()
    assert "auto_merge" in data


def test_scan_summaries_returns_mixed_content(api):
    """Scan summaries — should also return mixed_content and role_type_suggestions."""
    resp = post(api, "/api/kb/dedup/scan", {"entity_type": "summaries"})
    assert resp.status_code == 200
    data = resp.json()
    assert "mixed_content" in data
    assert "role_type_suggestions" in data


# ---------------------------------------------------------------------------
# POST /api/kb/dedup/apply
# ---------------------------------------------------------------------------

def test_apply_invalid_entity_returns_400(api):
    """Apply with invalid entity_type — should return 400."""
    resp = post(api, "/api/kb/dedup/apply", {"entity_type": "bad_table"})
    assert resp.status_code == 400


def test_apply_empty_operations_returns_zeros(api):
    """Apply with no merges/deletes/reclassifications — returns zeroed response."""
    resp = post(api, "/api/kb/dedup/apply", {
        "entity_type": "skills",
        "merges": [],
        "deletes": [],
        "reclassifications": [],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["merged"] == 0
    assert data["deleted"] == 0
    assert data["reclassified"] == 0
    assert "errors" in data


# ---------------------------------------------------------------------------
# POST /api/kb/dedup/employer-rename
# ---------------------------------------------------------------------------

def test_employer_rename_missing_fields_returns_400(api):
    """employer-rename without required fields — should return 400."""
    resp = post(api, "/api/kb/dedup/employer-rename", {})
    assert resp.status_code == 400


def test_employer_rename_missing_canonical_name_returns_400(api):
    """employer-rename without canonical_name — should return 400."""
    resp = post(api, "/api/kb/dedup/employer-rename", {
        "career_history_ids": [1, 2],
    })
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/kb/dedup/summaries/suggest-role-types
# ---------------------------------------------------------------------------

def test_suggest_role_types_returns_suggestions(api):
    """AI suggest role types — should return suggestions key."""
    resp = post(api, "/api/kb/dedup/summaries/suggest-role-types", {})
    assert resp.status_code == 200
    data = resp.json()
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)


# ---------------------------------------------------------------------------
# POST /api/kb/dedup/summaries/role-types
# ---------------------------------------------------------------------------

def test_rename_role_types_missing_body_returns_400(api):
    """role-types rename with empty body — should return 400."""
    resp = post(api, "/api/kb/dedup/summaries/role-types", {})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/kb/dedup/summaries/split
# ---------------------------------------------------------------------------

def test_split_missing_splits_returns_400(api):
    """Split with empty body — should return 400."""
    resp = post(api, "/api/kb/dedup/summaries/split", {})
    assert resp.status_code == 400


def test_split_empty_list_returns_400(api):
    """Split with empty splits list — should return 400."""
    resp = post(api, "/api/kb/dedup/summaries/split", {"splits": []})
    assert resp.status_code == 400
