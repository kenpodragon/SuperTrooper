"""
section_resolver.py — Resolves section-based recipe references to DB content.

Reference patterns:
  Single:     {"table": "X", "id": 1}          -> dict of all columns
  Single+col: {"table": "X", "id": 1, "column": "name"} -> str
  Multi:      {"table": "X", "ids": [1,2,3]}   -> list[dict]
  Multi+col:  {"table": "X", "ids": [1,2], "column": "name"} -> list[str]
  EXPERIENCE: special compound structure (company -> jobs -> bullets)
"""

import psycopg2
import psycopg2.extras

from utils.db_config import get_db_config


# Whitelist of tables that recipe refs are allowed to query
ALLOWED_TABLES = {
    "resume_header",
    "summary_variants",
    "bullets",
    "career_history",
    "education",
    "certifications",
    "skills",
    "content_sections",
    "references",
    "languages",
}

# Columns returned per table (excludes internal/heavy columns)
TABLE_COLUMNS = {
    "resume_header": [
        "full_name", "credentials", "location", "location_note",
        "email", "phone", "linkedin_url", "website_url", "calendly_url",
    ],
    "career_history": [
        "employer", "title", "start_date", "end_date",
        "location", "industry", "is_current", "is_company_entry", "intro_text",
    ],
    "bullets": ["text", "type", "career_history_id", "display_order"],
    "certifications": ["name", "issuer", "is_active", "sort_order"],
    "education": ["degree", "field", "institution", "location", "type", "sort_order"],
    "skills": ["name", "category", "proficiency", "last_used_year"],
    "summary_variants": ["role_type", "text", "headline", "sort_order"],
    "content_sections": ["section", "subsection", "content", "content_format"],
    "references": ["name", "title", "company", "relationship", "phone", "email"],
    "languages": ["name", "proficiency"],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_table(table: str) -> None:
    """Raise ValueError if table is not in the ALLOWED_TABLES whitelist."""
    if table not in ALLOWED_TABLES:
        raise ValueError(
            f"Table '{table}' is not allowed. Allowed tables: {sorted(ALLOWED_TABLES)}"
        )


def _cols_for(table: str) -> list[str]:
    """Return column list for table, falling back to empty (SELECT id only)."""
    return TABLE_COLUMNS.get(table, [])


def _fetch_row(conn, table: str, row_id: int) -> dict | None:
    """SELECT id + all known columns FROM table WHERE id = row_id."""
    _validate_table(table)
    cols = _cols_for(table)
    col_sql = ", ".join(cols) if cols else ""
    select = f"id, {col_sql}" if col_sql else "id"
    sql = f"SELECT {select} FROM {table} WHERE id = %s"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (row_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def _fetch_rows(conn, table: str, ids: list[int]) -> dict[int, dict]:
    """SELECT id + all known cols FROM table WHERE id IN (...).
    Returns a mapping of id -> row dict."""
    if not ids:
        return {}
    _validate_table(table)
    cols = _cols_for(table)
    col_sql = ", ".join(cols) if cols else ""
    select = f"id, {col_sql}" if col_sql else "id"
    placeholders = ",".join(["%s"] * len(ids))
    sql = f"SELECT {select} FROM {table} WHERE id IN ({placeholders})"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, ids)
        rows = cur.fetchall()
    return {row["id"]: dict(row) for row in rows}


# ---------------------------------------------------------------------------
# Public resolution functions
# ---------------------------------------------------------------------------

def resolve_single_ref(conn, ref: dict):
    """Resolve {table, id, column?}.

    Returns:
      - dict of all columns when no 'column' key
      - str (the column value) when 'column' is specified
      - None if the row is not found
    """
    table = ref["table"]
    row_id = ref["id"]
    column = ref.get("column")

    row = _fetch_row(conn, table, row_id)
    if row is None:
        return None
    if column:
        return row.get(column)
    return row


def resolve_multi_ref(conn, ref: dict) -> list:
    """Resolve {table, ids, column?}.

    Returns list in the same order as ref['ids']:
      - list[dict] when no 'column' key
      - list[str]  when 'column' is specified
    Missing IDs are silently skipped.
    """
    table = ref["table"]
    ids = ref["ids"]
    column = ref.get("column")

    rows_by_id = _fetch_rows(conn, table, ids)

    result = []
    for row_id in ids:
        row = rows_by_id.get(row_id)
        if row is None:
            continue
        if column:
            result.append(row.get(column))
        else:
            result.append(row)
    return result


def _resolve_experience(conn, experience_spec: list) -> list:
    """Resolve the EXPERIENCE compound structure.

    experience_spec is a list of company objects:
    [
      {
        "company_id": 123,            # career_history row with is_company_entry=true
        "jobs": [
          {
            "job_id": 456,            # career_history row (the actual job)
            "bullet_ids": [1, 2, 3]  # optional bullet rows
          }
        ]
      }
    ]

    Returns a list of resolved company dicts, each with nested jobs + bullets.
    """
    resolved = []
    for company_spec in experience_spec:
        company_id = company_spec.get("company_id")
        company_row = _fetch_row(conn, "career_history", company_id) if company_id else None

        jobs_resolved = []
        for job_spec in company_spec.get("jobs", []):
            job_id = job_spec.get("job_id")
            job_row = _fetch_row(conn, "career_history", job_id) if job_id else None

            bullet_ids = job_spec.get("bullet_ids", [])
            if bullet_ids:
                bullets = resolve_multi_ref(conn, {"table": "bullets", "ids": bullet_ids})
            else:
                bullets = []

            job_entry = {
                "job": job_row,
                "bullets": bullets,
            }
            jobs_resolved.append(job_entry)

        resolved.append({
            "company": company_row,
            "jobs": jobs_resolved,
        })
    return resolved


def resolve_section_recipe(conn, recipe: dict) -> dict:
    """Resolve all refs in a full recipe dict.

    Recipe structure (example):
    {
      "HEADER":        {"table": "resume_header", "id": 1},
      "SUMMARY":       {"table": "summary_variants", "id": 5},
      "CERTIFICATIONS":{"table": "certifications", "ids": [1357, 1358]},
      "EXPERIENCE":    [ ... compound structure ... ],
    }

    EXPERIENCE key is handled specially via _resolve_experience.
    All other keys are dispatched to resolve_single_ref or resolve_multi_ref.

    Returns dict with same keys, values replaced by resolved content.
    """
    resolved = {}
    for section_key, ref in recipe.items():
        if section_key == "EXPERIENCE":
            resolved[section_key] = _resolve_experience(conn, ref)
        elif isinstance(ref, dict):
            if "ids" in ref:
                resolved[section_key] = resolve_multi_ref(conn, ref)
            elif "id" in ref:
                resolved[section_key] = resolve_single_ref(conn, ref)
            else:
                # Pass through non-ref dicts unchanged
                resolved[section_key] = ref
        else:
            # Scalar values, lists of non-refs, etc. — pass through
            resolved[section_key] = ref
    return resolved


# ---------------------------------------------------------------------------
# Convenience: open a connection using db_config defaults
# ---------------------------------------------------------------------------

def get_connection():
    """Return a new psycopg2 connection using the standard db_config."""
    cfg = get_db_config()
    return psycopg2.connect(**cfg)
