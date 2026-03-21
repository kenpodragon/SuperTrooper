"""MCP tool definitions for the fresh_jobs inbox.

These functions are registered on the shared `mcp` instance defined in mcp_server.py.
The orchestrator imports and integrates this module after merge.

Usage in mcp_server.py:
    import mcp_tools_fresh_jobs  # noqa: F401  (side-effect: registers tools)
"""

import json
import db

# `mcp` is injected at import time from mcp_server.py.
# This module must be imported AFTER mcp is defined.
from mcp_server import mcp  # noqa: E402  -- orchestrator resolves this


@mcp.tool()
def get_fresh_jobs(status: str = "new", source_type: str | None = None, limit: int = 20) -> dict:
    """Get fresh jobs from the inbox, optionally filtered.

    Args:
        status: Filter by status (new, reviewed, saved, passed, expired, snoozed). Default: new
        source_type: Filter by source (api_search, plugin_capture, email_parsed, social_scan, rss_feed, manual)
        limit: Max results (default 20)

    Returns:
        dict with count and fresh_jobs list
    """
    clauses, params = [], []

    if status:
        clauses.append("status = %s")
        params.append(status)
    if source_type:
        clauses.append("source_type = %s")
        params.append(source_type)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT id, source_type, source_url, title, company, location,
               salary_range, jd_snippet, auto_score, status, discovered_at, saved_job_id
        FROM fresh_jobs
        {where}
        ORDER BY discovered_at DESC
        LIMIT %s
        """,
        params + [limit],
    )
    return {"count": len(rows), "fresh_jobs": rows}


@mcp.tool()
def triage_job(job_id: int, action: str, notes: str | None = None) -> dict:
    """Triage a fresh job: save to pipeline, pass, or snooze.

    Args:
        job_id: Fresh job ID
        action: save, pass, snooze, or review
        notes: Optional notes about the triage decision (stored if action=save)

    Returns:
        dict with result (if saved, includes saved_job_id)
    """
    valid_actions = {"save", "pass", "snooze", "review"}
    if action not in valid_actions:
        return {"error": f"action must be one of: {', '.join(sorted(valid_actions))}"}

    job = db.query_one("SELECT * FROM fresh_jobs WHERE id = %s", (job_id,))
    if not job:
        return {"error": f"Fresh job {job_id} not found"}

    if action == "save":
        if job.get("saved_job_id"):
            return {"error": "Already saved", "saved_job_id": job["saved_job_id"]}
        saved = db.execute_returning(
            """
            INSERT INTO saved_jobs (title, company, url, location, salary_range, jd_text, notes, source, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'saved')
            RETURNING id, title, company
            """,
            (
                job.get("title"),
                job.get("company"),
                job.get("source_url"),
                job.get("location"),
                job.get("salary_range"),
                job.get("jd_full") or job.get("jd_snippet"),
                notes,
                job.get("source_type"),
            ),
        )
        saved_job_id = saved["id"]
        db.execute(
            "UPDATE fresh_jobs SET status = 'saved', saved_job_id = %s WHERE id = %s",
            (saved_job_id, job_id),
        )
        return {
            "result": "saved",
            "fresh_job_id": job_id,
            "saved_job_id": saved_job_id,
            "title": saved.get("title"),
            "company": saved.get("company"),
        }

    status_map = {"pass": "passed", "snooze": "snoozed", "review": "reviewed"}
    new_status = status_map[action]
    db.execute("UPDATE fresh_jobs SET status = %s WHERE id = %s", (new_status, job_id))
    return {"result": action, "fresh_job_id": job_id, "status": new_status}


@mcp.tool()
def batch_triage(actions: str) -> dict:
    """Batch triage multiple fresh jobs.

    Pass actions as JSON string: [{"id": 1, "action": "save"}, {"id": 2, "action": "pass"}]

    Args:
        actions: JSON string of array with id and action pairs

    Returns:
        dict with results for each job
    """
    try:
        items = json.loads(actions)
    except (json.JSONDecodeError, TypeError) as e:
        return {"error": f"Invalid JSON: {e}"}

    if not isinstance(items, list):
        return {"error": "actions must be a JSON array"}

    valid_actions = {"save", "pass", "snooze", "review"}
    status_map = {"pass": "passed", "snooze": "snoozed", "review": "reviewed"}
    results = []

    for item in items:
        job_id = item.get("id")
        action = item.get("action")

        if not job_id or action not in valid_actions:
            results.append({"id": job_id, "error": f"invalid id or action '{action}'"})
            continue

        job = db.query_one("SELECT * FROM fresh_jobs WHERE id = %s", (job_id,))
        if not job:
            results.append({"id": job_id, "error": "not found"})
            continue

        if action == "save":
            if job.get("saved_job_id"):
                results.append({"id": job_id, "error": "already saved", "saved_job_id": job["saved_job_id"]})
                continue
            saved = db.execute_returning(
                """
                INSERT INTO saved_jobs (title, company, url, location, salary_range, jd_text, source, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'saved')
                RETURNING id
                """,
                (
                    job.get("title"),
                    job.get("company"),
                    job.get("source_url"),
                    job.get("location"),
                    job.get("salary_range"),
                    job.get("jd_full") or job.get("jd_snippet"),
                    job.get("source_type"),
                ),
            )
            saved_job_id = saved["id"]
            db.execute(
                "UPDATE fresh_jobs SET status = 'saved', saved_job_id = %s WHERE id = %s",
                (saved_job_id, job_id),
            )
            results.append({"id": job_id, "action": "save", "saved_job_id": saved_job_id, "status": "saved"})
        else:
            new_status = status_map[action]
            db.execute("UPDATE fresh_jobs SET status = %s WHERE id = %s", (new_status, job_id))
            results.append({"id": job_id, "action": action, "status": new_status})

    saved_count = sum(1 for r in results if r.get("action") == "save")
    passed_count = sum(1 for r in results if r.get("action") == "pass")
    error_count = sum(1 for r in results if "error" in r)

    return {
        "total": len(items),
        "saved": saved_count,
        "passed": passed_count,
        "errors": error_count,
        "results": results,
    }
