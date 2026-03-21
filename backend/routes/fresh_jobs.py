"""Routes for fresh_jobs (triage inbox)."""

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("fresh_jobs", __name__)

VALID_STATUSES = {"new", "reviewed", "saved", "passed", "expired", "snoozed"}
VALID_ACTIONS = {"save", "pass", "snooze", "review"}


@bp.route("/api/fresh-jobs", methods=["GET"])
def list_fresh_jobs():
    """List fresh jobs with optional filters. Defaults to status=new, newest first."""
    status = request.args.get("status", "new")
    source_type = request.args.get("source_type")
    company = request.args.get("company")
    search = request.args.get("search")
    min_score = request.args.get("min_score")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []

    if status:
        clauses.append("status = %s")
        params.append(status)
    if source_type:
        clauses.append("source_type = %s")
        params.append(source_type)
    if company:
        clauses.append("company ILIKE %s")
        params.append(f"%{company}%")
    if search:
        clauses.append("(title ILIKE %s OR company ILIKE %s OR jd_snippet ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if min_score:
        clauses.append("auto_score >= %s")
        params.append(float(min_score))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT *
        FROM fresh_jobs
        {where}
        ORDER BY discovered_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/fresh-jobs/stats", methods=["GET"])
def fresh_jobs_stats():
    """Return counts by status."""
    rows = db.query(
        """
        SELECT status, COUNT(*) AS count
        FROM fresh_jobs
        GROUP BY status
        """
    )
    stats = {row["status"]: row["count"] for row in rows}
    # Ensure all statuses present
    for s in VALID_STATUSES:
        stats.setdefault(s, 0)
    return jsonify(stats), 200


@bp.route("/api/fresh-jobs/<int:job_id>", methods=["GET"])
def get_fresh_job(job_id):
    """Get a single fresh job by ID."""
    job = db.query_one("SELECT * FROM fresh_jobs WHERE id = %s", (job_id,))
    if not job:
        return jsonify({"error": "Not found"}), 404
    return jsonify(job), 200


@bp.route("/api/fresh-jobs", methods=["POST"])
def create_fresh_job():
    """Create a fresh job record."""
    data = request.get_json(force=True)
    if not data.get("source_type"):
        return jsonify({"error": "source_type is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO fresh_jobs (
            source_type, source_url, title, company, location,
            salary_range, jd_snippet, jd_full, auto_score
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            data["source_type"],
            data.get("source_url"),
            data.get("title"),
            data.get("company"),
            data.get("location"),
            data.get("salary_range"),
            data.get("jd_snippet"),
            data.get("jd_full"),
            data.get("auto_score"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/fresh-jobs/<int:job_id>", methods=["PUT"])
def update_fresh_job(job_id):
    """Update any fields on a fresh job."""
    data = request.get_json(force=True)
    allowed = [
        "source_type", "source_url", "title", "company", "location",
        "salary_range", "jd_snippet", "jd_full", "auto_score", "status",
    ]
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(job_id)
    row = db.execute_returning(
        f"UPDATE fresh_jobs SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/fresh-jobs/<int:job_id>/triage", methods=["PUT"])
def triage_fresh_job(job_id):
    """Triage a fresh job: save, pass, snooze, or review.

    If action='save', creates a saved_job record and links it.
    """
    data = request.get_json(force=True)
    action = data.get("action")
    if not action or action not in VALID_ACTIONS:
        return jsonify({"error": f"action must be one of: {', '.join(sorted(VALID_ACTIONS))}"}), 400

    job = db.query_one("SELECT * FROM fresh_jobs WHERE id = %s", (job_id,))
    if not job:
        return jsonify({"error": "Not found"}), 404

    if action == "save":
        if job.get("saved_job_id"):
            return jsonify({"error": "Already saved", "saved_job_id": job["saved_job_id"]}), 409
        # Insert into saved_jobs
        saved = db.execute_returning(
            """
            INSERT INTO saved_jobs (title, company, url, location, salary_range, jd_text, source, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'saved')
            RETURNING *
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
        row = db.execute_returning(
            "UPDATE fresh_jobs SET status = 'saved', saved_job_id = %s WHERE id = %s RETURNING *",
            (saved_job_id, job_id),
        )
        return jsonify({"fresh_job": row, "saved_job": saved, "saved_job_id": saved_job_id}), 200

    # Map action to status
    status_map = {"pass": "passed", "snooze": "snoozed", "review": "reviewed"}
    new_status = status_map[action]
    row = db.execute_returning(
        "UPDATE fresh_jobs SET status = %s WHERE id = %s RETURNING *",
        (new_status, job_id),
    )
    return jsonify(row), 200


@bp.route("/api/fresh-jobs/batch-triage", methods=["POST"])
def batch_triage_fresh_jobs():
    """Batch triage multiple fresh jobs.

    Body: {"actions": [{"id": 1, "action": "save"}, {"id": 2, "action": "pass"}]}
    """
    data = request.get_json(force=True)
    actions = data.get("actions", [])
    if not actions:
        return jsonify({"error": "actions array is required"}), 400

    results = []
    for item in actions:
        job_id = item.get("id")
        action = item.get("action")
        if not job_id or action not in VALID_ACTIONS:
            results.append({"id": job_id, "error": f"invalid id or action: {action}"})
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
            status_map = {"pass": "passed", "snooze": "snoozed", "review": "reviewed"}
            new_status = status_map[action]
            db.execute("UPDATE fresh_jobs SET status = %s WHERE id = %s", (new_status, job_id))
            results.append({"id": job_id, "action": action, "status": new_status})

    return jsonify({"results": results}), 200
