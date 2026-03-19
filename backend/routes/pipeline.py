"""Routes for applications, interviews, companies."""

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("pipeline", __name__)


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

@bp.route("/api/companies", methods=["GET"])
def list_companies():
    """List/filter/search companies."""
    q = request.args.get("q")
    priority = request.args.get("priority")
    sector = request.args.get("sector")
    min_fit = request.args.get("min_fit_score")
    size = request.args.get("size")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if q:
        clauses.append("name ILIKE %s")
        params.append(f"%{q}%")
    if priority:
        clauses.append("priority = %s")
        params.append(priority)
    if sector:
        clauses.append("sector ILIKE %s")
        params.append(f"%{sector}%")
    if min_fit:
        clauses.append("fit_score >= %s")
        params.append(int(min_fit))
    if size:
        clauses.append("size = %s")
        params.append(size)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT id, name, sector, hq_location, size, stage, fit_score, priority,
               target_role, resume_variant, key_differentiator, melbourne_relevant,
               comp_range, notes, created_at, updated_at
        FROM companies
        {where}
        ORDER BY fit_score DESC NULLS LAST, name
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/companies/<int:company_id>", methods=["GET"])
def get_company(company_id):
    """Single company with applications and contacts."""
    company = db.query_one("SELECT * FROM companies WHERE id = %s", (company_id,))
    if not company:
        return jsonify({"error": "Not found"}), 404

    company["applications"] = db.query(
        """
        SELECT id, role, date_applied, source, status, resume_version, notes,
               last_status_change, created_at
        FROM applications
        WHERE company_id = %s
        ORDER BY date_applied DESC NULLS LAST
        """,
        (company_id,),
    )
    company["contacts"] = db.query(
        """
        SELECT id, name, title, relationship, email, phone, linkedin_url,
               relationship_strength, last_contact, notes
        FROM contacts
        WHERE company ILIKE %s
        ORDER BY relationship_strength, name
        """,
        (f"%{company['name']}%",),
    )
    return jsonify(company), 200


@bp.route("/api/companies", methods=["POST"])
def create_company():
    """Add a new company."""
    data = request.get_json(force=True)
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO companies (name, sector, hq_location, size, stage, fit_score,
            priority, target_role, resume_variant, key_differentiator,
            melbourne_relevant, comp_range, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data["name"], data.get("sector"), data.get("hq_location"),
            data.get("size"), data.get("stage"), data.get("fit_score"),
            data.get("priority"), data.get("target_role"), data.get("resume_variant"),
            data.get("key_differentiator"), data.get("melbourne_relevant"),
            data.get("comp_range"), data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/companies/<int:company_id>", methods=["PATCH"])
def update_company(company_id):
    """Update company fields."""
    data = request.get_json(force=True)
    allowed = [
        "name", "sector", "hq_location", "size", "stage", "fit_score",
        "priority", "target_role", "resume_variant", "key_differentiator",
        "melbourne_relevant", "comp_range", "notes",
    ]
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(company_id)
    row = db.execute_returning(
        f"UPDATE companies SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

@bp.route("/api/applications", methods=["GET"])
def list_applications():
    """List/filter/search applications."""
    status = request.args.get("status")
    source = request.args.get("source")
    company = request.args.get("company")
    company_id = request.args.get("company_id")
    after = request.args.get("after")
    before = request.args.get("before")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if status:
        clauses.append("a.status = %s")
        params.append(status)
    if source:
        clauses.append("a.source = %s")
        params.append(source)
    if company:
        clauses.append("a.company_name ILIKE %s")
        params.append(f"%{company}%")
    if company_id:
        clauses.append("a.company_id = %s")
        params.append(int(company_id))
    if after:
        clauses.append("a.date_applied >= %s")
        params.append(after)
    if before:
        clauses.append("a.date_applied <= %s")
        params.append(before)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT a.id, a.company_id, a.company_name, a.role, a.date_applied,
               a.source, a.status, a.resume_version, a.jd_url,
               a.contact_name, a.contact_email, a.notes,
               a.last_status_change, a.created_at, a.updated_at
        FROM applications a
        {where}
        ORDER BY a.date_applied DESC NULLS LAST
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/applications/<int:app_id>", methods=["GET"])
def get_application(app_id):
    """Single application with interviews, emails, company."""
    app = db.query_one(
        """
        SELECT a.*, c.name AS co_name, c.sector AS co_sector,
               c.fit_score AS co_fit_score, c.priority AS co_priority
        FROM applications a
        LEFT JOIN companies c ON c.id = a.company_id
        WHERE a.id = %s
        """,
        (app_id,),
    )
    if not app:
        return jsonify({"error": "Not found"}), 404

    app["interviews"] = db.query(
        "SELECT * FROM interviews WHERE application_id = %s ORDER BY date DESC NULLS LAST",
        (app_id,),
    )
    app["emails"] = db.query(
        "SELECT id, date, from_name, subject, snippet, category FROM emails WHERE application_id = %s ORDER BY date DESC",
        (app_id,),
    )
    return jsonify(app), 200


@bp.route("/api/applications", methods=["POST"])
def create_application():
    """Add a new application."""
    data = request.get_json(force=True)
    row = db.execute_returning(
        """
        INSERT INTO applications (company_id, company_name, role, date_applied,
            source, status, resume_version, cover_letter_path, jd_text, jd_url,
            contact_name, contact_email, notes, last_status_change)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW())
        RETURNING *
        """,
        (
            data.get("company_id"), data.get("company_name"), data.get("role"),
            data.get("date_applied"), data.get("source"),
            data.get("status", "Applied"), data.get("resume_version"),
            data.get("cover_letter_path"), data.get("jd_text"), data.get("jd_url"),
            data.get("contact_name"), data.get("contact_email"), data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/applications/<int:app_id>", methods=["PATCH"])
def update_application(app_id):
    """Update application status, notes, etc."""
    data = request.get_json(force=True)
    allowed = [
        "status", "notes", "resume_version", "cover_letter_path",
        "jd_text", "jd_url", "contact_name", "contact_email", "source",
    ]
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            params.append(data[key])
    if "status" in data:
        sets.append("last_status_change = NOW()")
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(app_id)
    row = db.execute_returning(
        f"UPDATE applications SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Interviews
# ---------------------------------------------------------------------------

@bp.route("/api/interviews", methods=["GET"])
def list_interviews():
    """List interviews with optional filters."""
    app_id = request.args.get("application_id")
    interview_type = request.args.get("type")
    outcome = request.args.get("outcome")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if app_id:
        clauses.append("i.application_id = %s")
        params.append(int(app_id))
    if interview_type:
        clauses.append("i.type = %s")
        params.append(interview_type)
    if outcome:
        clauses.append("i.outcome = %s")
        params.append(outcome)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT i.*, a.company_name, a.role
        FROM interviews i
        LEFT JOIN applications a ON a.id = i.application_id
        {where}
        ORDER BY i.date DESC NULLS LAST
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/interviews", methods=["POST"])
def create_interview():
    """Add an interview."""
    data = request.get_json(force=True)
    row = db.execute_returning(
        """
        INSERT INTO interviews (application_id, date, type, interviewers,
            calendar_event_id, outcome, feedback, thank_you_sent, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data.get("application_id"), data.get("date"), data.get("type"),
            data.get("interviewers"), data.get("calendar_event_id"),
            data.get("outcome", "pending"), data.get("feedback"),
            data.get("thank_you_sent", False), data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/interviews/<int:interview_id>", methods=["PATCH"])
def update_interview(interview_id):
    """Update interview outcome, notes, etc."""
    data = request.get_json(force=True)
    allowed = ["outcome", "feedback", "thank_you_sent", "notes", "date", "type"]
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(interview_id)
    row = db.execute_returning(
        f"UPDATE interviews SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200
