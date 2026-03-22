"""Routes for applications, interviews, companies, status history, materials, follow-ups."""

import json
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
    """Update application status, notes, etc. Auto-logs status changes."""
    data = request.get_json(force=True)
    allowed = [
        "status", "notes", "resume_version", "cover_letter_path",
        "jd_text", "jd_url", "contact_name", "contact_email", "source",
        "saved_job_id", "gap_analysis_id",
    ]

    # Capture old status before update for history logging
    old_status = None
    if "status" in data:
        old_row = db.query_one("SELECT status FROM applications WHERE id = %s", (app_id,))
        if old_row:
            old_status = old_row["status"]

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

    # Auto-log status change
    if "status" in data and old_status != data["status"]:
        db.execute(
            """
            INSERT INTO application_status_history (application_id, old_status, new_status, notes)
            VALUES (%s, %s, %s, %s)
            """,
            (app_id, old_status, data["status"], data.get("status_notes")),
        )

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


# ---------------------------------------------------------------------------
# Application Status History
# ---------------------------------------------------------------------------

@bp.route("/api/applications/<int:app_id>/status-history", methods=["GET"])
def get_status_history(app_id):
    """Get status change history for an application."""
    rows = db.query(
        "SELECT * FROM application_status_history WHERE application_id = %s ORDER BY changed_at DESC",
        (app_id,),
    )
    return jsonify(rows), 200


# ---------------------------------------------------------------------------
# Generated Materials
# ---------------------------------------------------------------------------

@bp.route("/api/applications/<int:app_id>/materials", methods=["GET"])
def list_materials(app_id):
    """List generated materials for an application."""
    rows = db.query(
        """
        SELECT gm.*, rr.name AS recipe_name
        FROM generated_materials gm
        LEFT JOIN resume_recipes rr ON rr.id = gm.recipe_id
        WHERE gm.application_id = %s
        ORDER BY gm.generated_at DESC
        """,
        (app_id,),
    )
    return jsonify(rows), 200


@bp.route("/api/materials", methods=["POST"])
def create_material():
    """Log a generated material."""
    data = request.get_json(force=True)
    if not data.get("type"):
        return jsonify({"error": "type is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO generated_materials (application_id, type, recipe_id,
            file_path, version_label, notes)
        VALUES (%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data.get("application_id"), data["type"], data.get("recipe_id"),
            data.get("file_path"), data.get("version_label"), data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/materials/<int:mat_id>", methods=["DELETE"])
def delete_material(mat_id):
    """Delete a generated material record."""
    count = db.execute("DELETE FROM generated_materials WHERE id = %s", (mat_id,))
    if count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": mat_id}), 200


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------

@bp.route("/api/applications/<int:app_id>/follow-ups", methods=["GET"])
def list_follow_ups(app_id):
    """List follow-ups for an application."""
    rows = db.query(
        "SELECT * FROM follow_ups WHERE application_id = %s ORDER BY attempt_number",
        (app_id,),
    )
    return jsonify(rows), 200


@bp.route("/api/follow-ups", methods=["POST"])
def create_follow_up():
    """Log a follow-up attempt."""
    data = request.get_json(force=True)
    if not data.get("application_id"):
        return jsonify({"error": "application_id is required"}), 400

    # Auto-increment attempt number
    last = db.query_one(
        "SELECT MAX(attempt_number) AS max_num FROM follow_ups WHERE application_id = %s",
        (data["application_id"],),
    )
    next_num = (last["max_num"] or 0) + 1 if last else 1

    row = db.execute_returning(
        """
        INSERT INTO follow_ups (application_id, attempt_number, date_sent,
            method, response_received, notes)
        VALUES (%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data["application_id"], data.get("attempt_number", next_num),
            data.get("date_sent"), data.get("method"),
            data.get("response_received", False), data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/follow-ups/<int:fu_id>", methods=["PATCH"])
def update_follow_up(fu_id):
    """Update a follow-up (e.g., mark response received)."""
    data = request.get_json(force=True)
    allowed = ["date_sent", "method", "response_received", "notes"]
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(fu_id)
    row = db.execute_returning(
        f"UPDATE follow_ups SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Auto-Ghosted Detection
# ---------------------------------------------------------------------------

@bp.route("/api/pipeline/detect-ghosted", methods=["POST"])
def detect_ghosted():
    """Scan applications for ghost signals.

    Rules:
      - Applied > 14 days ago, no response → 'likely ghosted'
      - Post-interview > 7 days, no response → 'ghosted post-interview'

    JSON body (optional):
        applied_days (int): threshold for applied-no-response (default 14)
        interview_days (int): threshold for post-interview silence (default 7)
        auto_flag (bool): if true, update status to 'Ghosted' (default false)
    """
    data = request.get_json(silent=True) or {}
    applied_days = data.get("applied_days", 14)
    interview_days = data.get("interview_days", 7)
    auto_flag = data.get("auto_flag", False)

    flagged = []

    # 1. Applied > N days, still in 'Applied' status, no follow-up response
    applied_stale = db.query(
        """
        SELECT a.id, a.company_name, a.role, a.status, a.date_applied,
               a.last_status_change,
               EXTRACT(DAY FROM NOW() - COALESCE(a.last_status_change, a.date_applied::timestamp))::int AS days_waiting,
               (SELECT COUNT(*) FROM follow_ups f WHERE f.application_id = a.id AND f.response_received = TRUE) AS responses,
               (SELECT COUNT(*) FROM interviews i WHERE i.application_id = a.id) AS interview_count
        FROM applications a
        WHERE a.status = 'Applied'
          AND COALESCE(a.last_status_change, a.date_applied::timestamp) < NOW() - INTERVAL '%s days'
        ORDER BY days_waiting DESC
        """,
        (applied_days,),
    )
    for app in (applied_stale or []):
        if app["responses"] == 0 and app["interview_count"] == 0:
            flagged.append({
                **app,
                "ghost_type": "likely_ghosted",
                "reason": f"Applied {app['days_waiting']} days ago with no response or interview",
                "recommended_action": "Send final follow-up or mark as ghosted",
            })

    # 2. Post-interview > N days, outcome still 'pending'
    post_interview_stale = db.query(
        """
        SELECT a.id AS application_id, a.company_name, a.role, a.status,
               i.id AS interview_id, i.date AS interview_date, i.type AS interview_type,
               EXTRACT(DAY FROM NOW() - i.date)::int AS days_since_interview
        FROM interviews i
        JOIN applications a ON a.id = i.application_id
        WHERE i.outcome = 'pending'
          AND i.date < NOW() - INTERVAL '%s days'
          AND a.status NOT IN ('Rejected', 'Ghosted', 'Withdrawn', 'Accepted', 'Rescinded')
        ORDER BY days_since_interview DESC
        """,
        (interview_days,),
    )
    for item in (post_interview_stale or []):
        flagged.append({
            "id": item["application_id"],
            "company_name": item["company_name"],
            "role": item["role"],
            "status": item["status"],
            "interview_id": item["interview_id"],
            "interview_date": item["interview_date"],
            "interview_type": item["interview_type"],
            "days_since_interview": item["days_since_interview"],
            "ghost_type": "ghosted_post_interview",
            "reason": f"Interview was {item['days_since_interview']} days ago with no outcome update",
            "recommended_action": "Send thank-you/follow-up or mark as ghosted",
        })

    # Auto-flag if requested
    updated_ids = []
    if auto_flag and flagged:
        for item in flagged:
            app_id = item["id"]
            if app_id not in updated_ids:
                old_status = item.get("status", "Applied")
                db.execute(
                    "UPDATE applications SET status = 'Ghosted', last_status_change = NOW() WHERE id = %s",
                    (app_id,),
                )
                db.execute(
                    """
                    INSERT INTO application_status_history (application_id, old_status, new_status, notes)
                    VALUES (%s, %s, 'Ghosted', %s)
                    """,
                    (app_id, old_status, f"Auto-flagged: {item['reason']}"),
                )
                updated_ids.append(app_id)

    return jsonify({
        "flagged_count": len(flagged),
        "auto_flagged": len(updated_ids),
        "thresholds": {"applied_days": applied_days, "interview_days": interview_days},
        "flagged": flagged,
    }), 200


# ---------------------------------------------------------------------------
# GET /api/pipeline/by-source — Applications grouped by source
# ---------------------------------------------------------------------------

@bp.route("/api/pipeline/by-source", methods=["GET"])
def applications_by_source():
    """Applications grouped by source (Indeed, LinkedIn, Referral, etc.)."""
    rows = db.query(
        """
        SELECT COALESCE(source, 'Unknown') AS source,
               COUNT(*) AS total,
               SUM(CASE WHEN status = 'Applied' THEN 1 ELSE 0 END) AS applied,
               SUM(CASE WHEN status IN ('Phone Screen','Interview','Technical','Final') THEN 1 ELSE 0 END) AS interviewing,
               SUM(CASE WHEN status = 'Offer' THEN 1 ELSE 0 END) AS offers,
               SUM(CASE WHEN status = 'Accepted' THEN 1 ELSE 0 END) AS accepted,
               SUM(CASE WHEN status = 'Rejected' THEN 1 ELSE 0 END) AS rejected,
               SUM(CASE WHEN status = 'Ghosted' THEN 1 ELSE 0 END) AS ghosted
        FROM applications
        GROUP BY COALESCE(source, 'Unknown')
        ORDER BY total DESC
        """
    )
    return jsonify({"sources": rows, "count": len(rows)}), 200


# ---------------------------------------------------------------------------
# GET /api/pipeline/source-conversion — Conversion rates by source
# ---------------------------------------------------------------------------

@bp.route("/api/pipeline/source-conversion", methods=["GET"])
def source_conversion():
    """Conversion rates by source: apply -> interview -> offer."""
    rows = db.query(
        """
        SELECT
            COALESCE(a.source, 'Unknown') AS source,
            COUNT(*) AS total_applied,
            SUM(CASE WHEN EXISTS (
                SELECT 1 FROM interviews i WHERE i.application_id = a.id
            ) THEN 1 ELSE 0 END) AS got_interview,
            SUM(CASE WHEN a.status = 'Offer' OR a.status = 'Accepted' THEN 1 ELSE 0 END) AS got_offer,
            ROUND(
                CASE WHEN COUNT(*) > 0
                THEN SUM(CASE WHEN EXISTS (
                    SELECT 1 FROM interviews i WHERE i.application_id = a.id
                ) THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100
                ELSE 0 END, 1
            ) AS apply_to_interview_pct,
            ROUND(
                CASE WHEN SUM(CASE WHEN EXISTS (
                    SELECT 1 FROM interviews i WHERE i.application_id = a.id
                ) THEN 1 ELSE 0 END) > 0
                THEN SUM(CASE WHEN a.status IN ('Offer','Accepted') THEN 1 ELSE 0 END)::numeric /
                     SUM(CASE WHEN EXISTS (
                        SELECT 1 FROM interviews i WHERE i.application_id = a.id
                     ) THEN 1 ELSE 0 END) * 100
                ELSE 0 END, 1
            ) AS interview_to_offer_pct,
            ROUND(
                CASE WHEN COUNT(*) > 0
                THEN SUM(CASE WHEN a.status IN ('Offer','Accepted') THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100
                ELSE 0 END, 1
            ) AS apply_to_offer_pct
        FROM applications a
        GROUP BY COALESCE(a.source, 'Unknown')
        ORDER BY total_applied DESC
        """
    )
    return jsonify({"conversion_rates": rows, "count": len(rows)}), 200


@bp.route("/api/applications/stale", methods=["GET"])
def stale_applications():
    """Find applications with no activity for N days."""
    days = int(request.args.get("days", 14))
    rows = db.query(
        """
        SELECT a.id, a.company_name, a.role, a.status, a.last_status_change,
               a.date_applied,
               EXTRACT(DAY FROM NOW() - COALESCE(a.last_status_change, a.date_applied::timestamp)) AS days_stale,
               (SELECT COUNT(*) FROM follow_ups f WHERE f.application_id = a.id) AS follow_up_count
        FROM applications a
        WHERE a.status NOT IN ('Rejected', 'Ghosted', 'Withdrawn', 'Accepted', 'Rescinded')
          AND COALESCE(a.last_status_change, a.date_applied::timestamp) < NOW() - INTERVAL '%s days'
        ORDER BY days_stale DESC
        """,
        (days,),
    )
    return jsonify(rows), 200
