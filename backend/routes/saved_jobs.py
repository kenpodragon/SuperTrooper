"""Routes for saved_jobs (evaluation queue)."""

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("saved_jobs", __name__)


@bp.route("/api/saved-jobs", methods=["GET"])
def list_saved_jobs():
    """List saved jobs with optional filters."""
    status = request.args.get("status")
    source = request.args.get("source")
    company = request.args.get("company")
    min_fit = request.args.get("min_fit_score")
    url_filter = request.args.get("url")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if status:
        clauses.append("sj.status = %s")
        params.append(status)
    if source:
        clauses.append("sj.source = %s")
        params.append(source)
    if company:
        clauses.append("sj.company ILIKE %s")
        params.append(f"%{company}%")
    if min_fit:
        clauses.append("sj.fit_score >= %s")
        params.append(float(min_fit))
    if url_filter:
        clauses.append("sj.url = %s")
        params.append(url_filter)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT sj.*, c.sector AS co_sector, c.priority AS co_priority
        FROM saved_jobs sj
        LEFT JOIN companies c ON c.id = sj.company_id
        {where}
        ORDER BY sj.fit_score DESC NULLS LAST, sj.created_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/saved-jobs/<int:job_id>", methods=["GET"])
def get_saved_job(job_id):
    """Single saved job with linked gap analyses and referrals."""
    job = db.query_one(
        """
        SELECT sj.*, c.name AS co_name, c.sector AS co_sector,
               c.fit_score AS co_fit_score, c.priority AS co_priority
        FROM saved_jobs sj
        LEFT JOIN companies c ON c.id = sj.company_id
        WHERE sj.id = %s
        """,
        (job_id,),
    )
    if not job:
        return jsonify({"error": "Not found"}), 404

    job["gap_analyses"] = db.query(
        "SELECT id, overall_score, recommendation, created_at FROM gap_analyses WHERE saved_job_id = %s ORDER BY created_at DESC",
        (job_id,),
    )
    return jsonify(job), 200


@bp.route("/api/saved-jobs", methods=["POST"])
def create_saved_job():
    """Save a job for evaluation."""
    data = request.get_json(force=True)
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO saved_jobs (url, title, company, company_id, location,
            salary_range, source, jd_text, jd_url, fit_score, status, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data.get("url"), data["title"], data.get("company"),
            data.get("company_id"), data.get("location"),
            data.get("salary_range"), data.get("source"),
            data.get("jd_text"), data.get("jd_url"),
            data.get("fit_score"), data.get("status", "saved"),
            data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/saved-jobs/<int:job_id>", methods=["PATCH"])
def update_saved_job(job_id):
    """Update a saved job."""
    data = request.get_json(force=True)
    allowed = [
        "url", "title", "company", "company_id", "location", "salary_range",
        "source", "jd_text", "jd_url", "fit_score", "status", "notes",
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
        f"UPDATE saved_jobs SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/saved-jobs/<int:job_id>", methods=["DELETE"])
def delete_saved_job(job_id):
    """Delete a saved job."""
    count = db.execute("DELETE FROM saved_jobs WHERE id = %s", (job_id,))
    if count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": job_id}), 200


@bp.route("/api/saved-jobs/<int:job_id>/apply", methods=["POST"])
def apply_from_saved_job(job_id):
    """Transition a saved job to an application.

    Creates a new application from the saved job data and links them.
    """
    job = db.query_one("SELECT * FROM saved_jobs WHERE id = %s", (job_id,))
    if not job:
        return jsonify({"error": "Saved job not found"}), 404

    data = request.get_json(silent=True) or {}

    app_row = db.execute_returning(
        """
        INSERT INTO applications (company_id, company_name, role, source,
            status, jd_text, jd_url, saved_job_id, notes, last_status_change, date_applied)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW(), CURRENT_DATE)
        RETURNING *
        """,
        (
            job.get("company_id"), job.get("company"),
            job.get("title"), job.get("source"),
            data.get("status", "Applied"),
            job.get("jd_text"), job.get("jd_url"),
            job_id, data.get("notes"),
        ),
    )

    # Update saved job status
    db.execute(
        "UPDATE saved_jobs SET status = 'applied' WHERE id = %s", (job_id,)
    )

    return jsonify(app_row), 201
