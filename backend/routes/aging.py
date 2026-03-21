"""Routes for application aging and link monitoring."""

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("aging", __name__)

VALID_LINK_STATUSES = {"unknown", "active", "closed", "error"}


# ---------------------------------------------------------------------------
# GET /api/aging/stale-applications
# ---------------------------------------------------------------------------

@bp.route("/api/aging/stale-applications", methods=["GET"])
def stale_applications():
    """Applications with no status change in X days (default 14).

    Query params:
        days (int): inactivity threshold (default 14)
        status (str): optional filter by application status
    """
    days = int(request.args.get("days", 14))
    status = request.args.get("status")

    clauses = ["a.last_status_change < NOW() - INTERVAL '%s days'"]
    params = [days]

    if status:
        clauses.append("a.status = %s")
        params.append(status)

    where = "WHERE " + " AND ".join(clauses)

    rows = db.query(
        f"""
        SELECT a.id, a.company_name, a.role, a.status, a.date_applied,
               a.last_status_change, a.link_status, a.posting_closed,
               EXTRACT(DAY FROM NOW() - a.last_status_change)::int AS days_stale
        FROM applications a
        {where}
        ORDER BY a.last_status_change ASC
        """,
        params,
    )
    return jsonify({"count": len(rows), "applications": rows}), 200


# ---------------------------------------------------------------------------
# GET /api/aging/stale-saved-jobs
# ---------------------------------------------------------------------------

@bp.route("/api/aging/stale-saved-jobs", methods=["GET"])
def stale_saved_jobs():
    """Saved jobs with no activity in X days (default 30).

    Query params:
        days (int): inactivity threshold (default 30)
    """
    days = int(request.args.get("days", 30))

    rows = db.query(
        """
        SELECT sj.id, sj.title, sj.company, sj.status, sj.fit_score,
               sj.link_status, sj.posting_closed, sj.created_at, sj.updated_at,
               EXTRACT(DAY FROM NOW() - sj.updated_at)::int AS days_stale
        FROM saved_jobs sj
        WHERE sj.updated_at < NOW() - INTERVAL '%s days'
          AND sj.status NOT IN ('applied', 'archived')
        ORDER BY sj.updated_at ASC
        """,
        [days],
    )
    return jsonify({"count": len(rows), "saved_jobs": rows}), 200


# ---------------------------------------------------------------------------
# GET /api/aging/closed-postings
# ---------------------------------------------------------------------------

@bp.route("/api/aging/closed-postings", methods=["GET"])
def closed_postings():
    """All items where posting_closed=true across both tables."""
    saved = db.query(
        """
        SELECT 'saved_job' AS entity_type, id, title AS role, company,
               link_status, posting_closed_at, last_link_check_at
        FROM saved_jobs
        WHERE posting_closed = TRUE
        ORDER BY posting_closed_at DESC NULLS LAST
        """
    )
    apps = db.query(
        """
        SELECT 'application' AS entity_type, id, role, company_name AS company,
               link_status, posting_closed_at, last_link_check_at
        FROM applications
        WHERE posting_closed = TRUE
        ORDER BY posting_closed_at DESC NULLS LAST
        """
    )
    items = saved + apps
    return jsonify({"count": len(items), "items": items}), 200


# ---------------------------------------------------------------------------
# PUT /api/aging/saved-jobs/:id/link-status
# ---------------------------------------------------------------------------

@bp.route("/api/aging/saved-jobs/<int:job_id>/link-status", methods=["PUT"])
def update_saved_job_link_status(job_id):
    """Update link status for a saved job.

    JSON body:
        link_status (str): unknown | active | closed | error
        posting_closed (bool): optional
        posting_closed_at (str ISO8601): optional, set when closing
    """
    data = request.get_json(force=True)
    link_status = data.get("link_status")
    if link_status and link_status not in VALID_LINK_STATUSES:
        return jsonify({"error": f"link_status must be one of {sorted(VALID_LINK_STATUSES)}"}), 400

    sets = ["last_link_check_at = NOW()"]
    params = []

    if link_status:
        sets.append("link_status = %s")
        params.append(link_status)
    if "posting_closed" in data:
        sets.append("posting_closed = %s")
        params.append(bool(data["posting_closed"]))
    if "posting_closed_at" in data:
        sets.append("posting_closed_at = %s")
        params.append(data["posting_closed_at"])

    params.append(job_id)
    row = db.execute_returning(
        f"UPDATE saved_jobs SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# PUT /api/aging/applications/:id/link-status
# ---------------------------------------------------------------------------

@bp.route("/api/aging/applications/<int:app_id>/link-status", methods=["PUT"])
def update_application_link_status(app_id):
    """Update link status for an application.

    JSON body:
        link_status (str): unknown | active | closed | error
        posting_closed (bool): optional
        posting_closed_at (str ISO8601): optional
    """
    data = request.get_json(force=True)
    link_status = data.get("link_status")
    if link_status and link_status not in VALID_LINK_STATUSES:
        return jsonify({"error": f"link_status must be one of {sorted(VALID_LINK_STATUSES)}"}), 400

    sets = ["last_link_check_at = NOW()"]
    params = []

    if link_status:
        sets.append("link_status = %s")
        params.append(link_status)
    if "posting_closed" in data:
        sets.append("posting_closed = %s")
        params.append(bool(data["posting_closed"]))
    if "posting_closed_at" in data:
        sets.append("posting_closed_at = %s")
        params.append(data["posting_closed_at"])

    params.append(app_id)
    row = db.execute_returning(
        f"UPDATE applications SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# GET /api/aging/summary
# ---------------------------------------------------------------------------

@bp.route("/api/aging/summary", methods=["GET"])
def aging_summary():
    """Counts of stale apps, stale saved jobs, closed postings, unknown link status."""
    stale_apps = db.query_one(
        """
        SELECT COUNT(*)::int AS count
        FROM applications
        WHERE last_status_change < NOW() - INTERVAL '14 days'
        """
    )
    stale_jobs = db.query_one(
        """
        SELECT COUNT(*)::int AS count
        FROM saved_jobs
        WHERE updated_at < NOW() - INTERVAL '30 days'
          AND status NOT IN ('applied', 'archived')
        """
    )
    closed = db.query_one(
        """
        SELECT
            (SELECT COUNT(*)::int FROM saved_jobs WHERE posting_closed = TRUE) +
            (SELECT COUNT(*)::int FROM applications WHERE posting_closed = TRUE) AS count
        """
    )
    needs_check = db.query_one(
        """
        SELECT
            (SELECT COUNT(*)::int FROM saved_jobs WHERE link_status = 'unknown') +
            (SELECT COUNT(*)::int FROM applications WHERE link_status = 'unknown') AS count
        """
    )
    return jsonify({
        "stale_applications": stale_apps["count"] if stale_apps else 0,
        "stale_saved_jobs": stale_jobs["count"] if stale_jobs else 0,
        "closed_postings": closed["count"] if closed else 0,
        "needs_link_check": needs_check["count"] if needs_check else 0,
    }), 200
