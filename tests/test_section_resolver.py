"""
Integration tests for utils/section_resolver.py

These tests hit the real supertroopers DB (localhost:5555).
Each test queries the DB first to get live IDs, then uses those IDs.
Tests skip gracefully if the required data doesn't exist.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import psycopg2
import psycopg2.extras

from utils.section_resolver import (
    resolve_single_ref,
    resolve_multi_ref,
    resolve_section_recipe,
    ALLOWED_TABLES,
    _validate_table,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db_conn():
    conn = psycopg2.connect(
        host="localhost",
        port=5555,
        dbname="supertroopers",
        user="supertroopers",
        password="WUHD8fBisb57FS4Q3bdvfuvgnim9fL1c",
    )
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def fetch_ids(conn, table: str, limit: int = 3, where: str = "") -> list[int]:
    """Fetch up to `limit` IDs from table."""
    sql = f"SELECT id FROM {table} {where} ORDER BY id LIMIT {limit}"
    with conn.cursor() as cur:
        cur.execute(sql)
        return [row[0] for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_validate_table_allowed():
    """All tables in ALLOWED_TABLES pass validation without raising."""
    for t in ALLOWED_TABLES:
        _validate_table(t)  # should not raise


def test_validate_table_blocked():
    """Unknown tables raise ValueError."""
    with pytest.raises(ValueError, match="not allowed"):
        _validate_table("pg_shadow")


def test_resolve_single_ref_resume_header(db_conn):
    """Single ref returns a dict containing full_name and email."""
    ids = fetch_ids(db_conn, "resume_header")
    if not ids:
        pytest.skip("No rows in resume_header")

    result = resolve_single_ref(db_conn, {"table": "resume_header", "id": ids[0]})

    assert isinstance(result, dict), "Expected dict"
    assert "full_name" in result, "full_name missing from result"
    assert "email" in result, "email missing from result"
    assert result["full_name"], "full_name should not be empty"


def test_resolve_single_ref_with_column(db_conn):
    """Single ref + column returns just that string value."""
    ids = fetch_ids(db_conn, "resume_header")
    if not ids:
        pytest.skip("No rows in resume_header")

    result = resolve_single_ref(
        db_conn, {"table": "resume_header", "id": ids[0], "column": "full_name"}
    )

    assert isinstance(result, str), f"Expected str, got {type(result)}"
    assert len(result) > 0, "full_name should not be empty"


def test_resolve_single_ref_missing_id(db_conn):
    """Single ref for a non-existent ID returns None."""
    result = resolve_single_ref(db_conn, {"table": "resume_header", "id": 999999999})
    assert result is None


def test_resolve_multi_ref_certifications(db_conn):
    """Multi ref returns list of dicts in ids order."""
    ids = fetch_ids(db_conn, "certifications", limit=3)
    if len(ids) < 2:
        pytest.skip("Need at least 2 certifications rows")

    # Reverse order to verify result respects ids order, not DB order
    ids_reversed = list(reversed(ids))
    result = resolve_multi_ref(db_conn, {"table": "certifications", "ids": ids_reversed})

    assert isinstance(result, list), "Expected list"
    assert len(result) == len(ids_reversed)
    assert all(isinstance(r, dict) for r in result), "Each item should be a dict"
    assert all("name" in r for r in result), "Each cert should have 'name'"
    # Verify order preserved
    assert [r["id"] for r in result] == ids_reversed, "Result order should match ids order"


def test_resolve_multi_ref_bullets(db_conn):
    """Multi ref for bullets returns text for each."""
    ids = fetch_ids(db_conn, "bullets", limit=3)
    if not ids:
        pytest.skip("No rows in bullets")

    result = resolve_multi_ref(db_conn, {"table": "bullets", "ids": ids, "column": "text"})

    assert isinstance(result, list)
    assert len(result) == len(ids)
    assert all(isinstance(t, str) for t in result), "Each bullet text should be a str"


def test_resolve_multi_ref_preserves_order(db_conn):
    """Verify multi ref preserves the exact ids order, not DB insertion order."""
    ids = fetch_ids(db_conn, "certifications", limit=4)
    if len(ids) < 3:
        pytest.skip("Need at least 3 certifications rows")

    # Shuffle: put middle id first
    shuffled = [ids[1], ids[0], ids[2]] if len(ids) >= 3 else ids
    result = resolve_multi_ref(db_conn, {"table": "certifications", "ids": shuffled})

    assert [r["id"] for r in result] == shuffled


def test_resolve_section_recipe_singular(db_conn):
    """HEADER section resolves to a dict."""
    ids = fetch_ids(db_conn, "resume_header")
    if not ids:
        pytest.skip("No rows in resume_header")

    recipe = {"HEADER": {"table": "resume_header", "id": ids[0]}}
    result = resolve_section_recipe(db_conn, recipe)

    assert "HEADER" in result
    assert isinstance(result["HEADER"], dict)
    assert "full_name" in result["HEADER"]


def test_resolve_section_recipe_repeating(db_conn):
    """CERTIFICATIONS section resolves to a list."""
    ids = fetch_ids(db_conn, "certifications", limit=3)
    if not ids:
        pytest.skip("No rows in certifications")

    recipe = {"CERTIFICATIONS": {"table": "certifications", "ids": ids}}
    result = resolve_section_recipe(db_conn, recipe)

    assert "CERTIFICATIONS" in result
    assert isinstance(result["CERTIFICATIONS"], list)
    assert len(result["CERTIFICATIONS"]) == len(ids)


def test_resolve_experience_compound(db_conn):
    """EXPERIENCE resolves compound company -> jobs -> bullets structure."""
    # Find a company entry
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT id, employer FROM career_history WHERE is_company_entry = true LIMIT 1"
        )
        company_row = cur.fetchone()

    if not company_row:
        pytest.skip("No company entries (is_company_entry=true) in career_history")

    company_id, employer = company_row

    # Find jobs under this company (same employer, not company entry)
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM career_history WHERE employer = %s AND is_company_entry = false LIMIT 2",
            (employer,),
        )
        job_ids = [r[0] for r in cur.fetchall()]

    if not job_ids:
        pytest.skip(f"No non-entry jobs found for employer '{employer}'")

    # Find bullets for first job
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM bullets WHERE career_history_id = %s LIMIT 3",
            (job_ids[0],),
        )
        bullet_ids = [r[0] for r in cur.fetchall()]

    experience_spec = [
        {
            "company_id": company_id,
            "jobs": [
                {
                    "job_id": job_ids[0],
                    "bullet_ids": bullet_ids,
                }
            ],
        }
    ]

    recipe = {"EXPERIENCE": experience_spec}
    result = resolve_section_recipe(db_conn, recipe)

    assert "EXPERIENCE" in result
    exp = result["EXPERIENCE"]
    assert isinstance(exp, list)
    assert len(exp) == 1

    company_entry = exp[0]
    assert "company" in company_entry
    assert "jobs" in company_entry
    assert company_entry["company"]["id"] == company_id

    jobs_result = company_entry["jobs"]
    assert len(jobs_result) == 1
    job_entry = jobs_result[0]
    assert "job" in job_entry
    assert "bullets" in job_entry
    assert job_entry["job"]["id"] == job_ids[0]

    if bullet_ids:
        assert len(job_entry["bullets"]) == len(bullet_ids)
        assert all("text" in b for b in job_entry["bullets"])


def test_resolve_section_recipe_passthrough(db_conn):
    """Non-ref values in recipe are passed through unchanged."""
    recipe = {
        "METADATA": {"format": "v2", "generated_by": "test"},
        "TITLE": "Senior Engineer Resume",
    }
    result = resolve_section_recipe(db_conn, recipe)

    assert result["METADATA"] == {"format": "v2", "generated_by": "test"}
    assert result["TITLE"] == "Senior Engineer Resume"
