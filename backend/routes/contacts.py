"""Routes for contacts, outreach messages, referrals."""

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("contacts", __name__)


@bp.route("/api/contacts", methods=["GET"])
def list_contacts():
    """List/filter/search contacts."""
    company = request.args.get("company")
    relationship = request.args.get("relationship")
    strength = request.args.get("strength")
    q = request.args.get("q")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if company:
        clauses.append("company ILIKE %s")
        params.append(f"%{company}%")
    if relationship:
        clauses.append("relationship = %s")
        params.append(relationship)
    if strength:
        clauses.append("relationship_strength = %s")
        params.append(strength)
    if q:
        clauses.append("(name ILIKE %s OR title ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT id, name, company, title, relationship, email, phone,
               linkedin_url, relationship_strength, last_contact, source,
               notes, created_at, updated_at
        FROM contacts
        {where}
        ORDER BY last_contact DESC NULLS LAST, name
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/contacts", methods=["POST"])
def create_contact():
    """Add a new contact."""
    data = request.get_json(force=True)
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO contacts (name, company, company_id, title, relationship, email, phone,
            linkedin_url, relationship_strength, last_contact, source, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data["name"], data.get("company"), data.get("company_id"),
            data.get("title"), data.get("relationship"),
            data.get("email"), data.get("phone"),
            data.get("linkedin_url"), data.get("relationship_strength"),
            data.get("last_contact"), data.get("source", "manual"),
            data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/contacts/<int:contact_id>", methods=["PATCH"])
def update_contact(contact_id):
    """Update contact fields."""
    data = request.get_json(force=True)
    allowed = [
        "name", "company", "company_id", "title", "relationship", "email", "phone",
        "linkedin_url", "relationship_strength", "last_contact", "source", "notes",
    ]
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(contact_id)
    row = db.execute_returning(
        f"UPDATE contacts SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/contacts/<int:contact_id>", methods=["DELETE"])
def delete_contact(contact_id):
    """Delete a contact."""
    count = db.execute("DELETE FROM contacts WHERE id = %s", (contact_id,))
    if count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": contact_id}), 200


# ---------------------------------------------------------------------------
# Outreach Messages
# ---------------------------------------------------------------------------

@bp.route("/api/outreach", methods=["GET"])
def list_outreach():
    """List outreach messages with filters."""
    contact_id = request.args.get("contact_id")
    application_id = request.args.get("application_id")
    channel = request.args.get("channel")
    direction = request.args.get("direction")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if contact_id:
        clauses.append("o.contact_id = %s")
        params.append(int(contact_id))
    if application_id:
        clauses.append("o.application_id = %s")
        params.append(int(application_id))
    if channel:
        clauses.append("o.channel = %s")
        params.append(channel)
    if direction:
        clauses.append("o.direction = %s")
        params.append(direction)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT o.*, ct.name AS contact_name, a.company_name, a.role
        FROM outreach_messages o
        LEFT JOIN contacts ct ON ct.id = o.contact_id
        LEFT JOIN applications a ON a.id = o.application_id
        {where}
        ORDER BY o.sent_at DESC NULLS LAST, o.created_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/outreach", methods=["POST"])
def create_outreach():
    """Log an outreach message."""
    data = request.get_json(force=True)
    if not data.get("channel") or not data.get("direction"):
        return jsonify({"error": "channel and direction are required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO outreach_messages (contact_id, application_id, interview_id,
            channel, direction, subject, body, sent_at, response_received, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data.get("contact_id"), data.get("application_id"),
            data.get("interview_id"), data["channel"], data["direction"],
            data.get("subject"), data.get("body"), data.get("sent_at"),
            data.get("response_received", False), data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/outreach/<int:msg_id>", methods=["PATCH"])
def update_outreach(msg_id):
    """Update an outreach message."""
    data = request.get_json(force=True)
    allowed = [
        "contact_id", "application_id", "interview_id", "channel", "direction",
        "subject", "body", "sent_at", "response_received", "notes",
    ]
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(msg_id)
    row = db.execute_returning(
        f"UPDATE outreach_messages SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/outreach/<int:msg_id>", methods=["DELETE"])
def delete_outreach(msg_id):
    """Delete an outreach message."""
    count = db.execute("DELETE FROM outreach_messages WHERE id = %s", (msg_id,))
    if count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": msg_id}), 200


# ---------------------------------------------------------------------------
# Referrals
# ---------------------------------------------------------------------------

@bp.route("/api/referrals", methods=["GET"])
def list_referrals():
    """List referrals with optional filters."""
    contact_id = request.args.get("contact_id")
    application_id = request.args.get("application_id")
    status = request.args.get("status")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if contact_id:
        clauses.append("r.contact_id = %s")
        params.append(int(contact_id))
    if application_id:
        clauses.append("r.application_id = %s")
        params.append(int(application_id))
    if status:
        clauses.append("r.status = %s")
        params.append(status)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT r.*, ct.name AS contact_name, ct.company AS contact_company,
               a.company_name, a.role, sj.title AS job_title
        FROM referrals r
        LEFT JOIN contacts ct ON ct.id = r.contact_id
        LEFT JOIN applications a ON a.id = r.application_id
        LEFT JOIN saved_jobs sj ON sj.id = r.saved_job_id
        {where}
        ORDER BY r.referral_date DESC NULLS LAST, r.created_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/referrals", methods=["POST"])
def create_referral():
    """Log a referral."""
    data = request.get_json(force=True)
    if not data.get("contact_id"):
        return jsonify({"error": "contact_id is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO referrals (contact_id, application_id, saved_job_id,
            referral_date, status, notes)
        VALUES (%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data["contact_id"], data.get("application_id"),
            data.get("saved_job_id"), data.get("referral_date"),
            data.get("status", "pending"), data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/referrals/<int:ref_id>", methods=["PATCH"])
def update_referral(ref_id):
    """Update a referral."""
    data = request.get_json(force=True)
    allowed = ["application_id", "saved_job_id", "referral_date", "status", "notes"]
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(ref_id)
    row = db.execute_returning(
        f"UPDATE referrals SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/referrals/<int:ref_id>", methods=["DELETE"])
def delete_referral(ref_id):
    """Delete a referral."""
    count = db.execute("DELETE FROM referrals WHERE id = %s", (ref_id,))
    if count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": ref_id}), 200


# ---------------------------------------------------------------------------
# Contact Enrichment
# ---------------------------------------------------------------------------

@bp.route("/api/contacts/<int:contact_id>/enrich", methods=["POST"])
def enrich_contact(contact_id):
    """Add enrichment data (current_title, current_company, linkedin_url, notes)."""
    contact = db.query_one("SELECT id FROM contacts WHERE id = %s", (contact_id,))
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    data = request.get_json(force=True)
    enrichable = ["title", "company", "linkedin_url", "notes", "email", "phone"]
    sets, params = [], []

    for key in enrichable:
        # Accept both "current_title" and "title" style keys
        val = data.get(key) or data.get(f"current_{key}")
        if val is not None:
            sets.append(f"{key} = %s")
            params.append(val)

    if not sets:
        return jsonify({"error": "No enrichment fields provided"}), 400

    sets.append("enriched_at = NOW()")
    if data.get("source"):
        sets.append("enrichment_source = %s")
        params.append(data["source"])

    sets.append("updated_at = NOW()")
    params.append(contact_id)

    row = db.execute_returning(
        f"UPDATE contacts SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    return jsonify(row), 200


@bp.route("/api/contacts/stale", methods=["GET"])
def stale_contacts():
    """Contacts with no touchpoint in > 90 days (or never touched)."""
    days = int(request.args.get("days", 90))
    limit = int(request.args.get("limit", 50))

    rows = db.query(
        """
        SELECT c.id, c.name, c.company, c.title, c.relationship_stage,
               c.health_score, c.last_touchpoint_at, c.last_contact, c.email,
               EXTRACT(EPOCH FROM (NOW() - c.last_touchpoint_at)) / 86400 AS days_since_touchpoint
        FROM contacts c
        WHERE c.merged_into_id IS NULL
          AND (c.last_touchpoint_at < NOW() - INTERVAL '%s days'
               OR c.last_touchpoint_at IS NULL)
        ORDER BY c.last_touchpoint_at ASC NULLS FIRST
        LIMIT %s
        """,
        (days, limit),
    )
    return jsonify({"stale_contacts": rows, "count": len(rows), "threshold_days": days}), 200


@bp.route("/api/contacts/<int:contact_id>/merge", methods=["POST"])
def merge_contacts(contact_id):
    """Merge duplicate contacts: keep primary (contact_id), merge touchpoints/notes from secondary.

    Body JSON: {"merge_from_id": int}
    """
    data = request.get_json(force=True)
    merge_from_id = data.get("merge_from_id")
    if not merge_from_id:
        return jsonify({"error": "merge_from_id is required"}), 400

    primary = db.query_one("SELECT * FROM contacts WHERE id = %s", (contact_id,))
    if not primary:
        return jsonify({"error": "Primary contact not found"}), 404

    secondary = db.query_one("SELECT * FROM contacts WHERE id = %s", (merge_from_id,))
    if not secondary:
        return jsonify({"error": "Secondary contact not found"}), 404

    # Move touchpoints from secondary to primary
    db.execute(
        "UPDATE touchpoints SET contact_id = %s WHERE contact_id = %s",
        (contact_id, merge_from_id),
    )

    # Move networking_tasks from secondary to primary
    db.execute(
        "UPDATE networking_tasks SET contact_id = %s WHERE contact_id = %s",
        (contact_id, merge_from_id),
    )

    # Move crm_tasks from secondary to primary
    db.execute(
        "UPDATE crm_tasks SET contact_id = %s WHERE contact_id = %s",
        (contact_id, merge_from_id),
    )

    # Move outreach messages from secondary to primary
    db.execute(
        "UPDATE outreach_messages SET contact_id = %s WHERE contact_id = %s",
        (contact_id, merge_from_id),
    )

    # Merge notes
    if secondary.get("notes"):
        merged_notes = (primary.get("notes") or "") + "\n\n--- Merged from " + (secondary.get("name") or str(merge_from_id)) + " ---\n" + secondary["notes"]
        db.execute(
            "UPDATE contacts SET notes = %s, updated_at = NOW() WHERE id = %s",
            (merged_notes, contact_id),
        )

    # Mark secondary as merged (soft delete)
    db.execute(
        "UPDATE contacts SET merged_into_id = %s, updated_at = NOW() WHERE id = %s",
        (contact_id, merge_from_id),
    )

    # Count merged records
    tp_count = db.query_one(
        "SELECT COUNT(*) AS cnt FROM touchpoints WHERE contact_id = %s", (contact_id,)
    )

    return jsonify({
        "primary_id": contact_id,
        "merged_from_id": merge_from_id,
        "total_touchpoints": tp_count["cnt"] if tp_count else 0,
        "status": "merged",
    }), 200


# ---------------------------------------------------------------------------
# Outreach Follow-up Reminders
# ---------------------------------------------------------------------------

@bp.route("/api/outreach/pending-followups", methods=["GET"])
def pending_followups():
    """Return outreach messages with a follow_up_date on or before today and no response received.

    Query params:
        limit (int, default 50): max results
        as_of (date str YYYY-MM-DD, default today): cutoff date
    """
    limit = int(request.args.get("limit", 50))
    as_of = request.args.get("as_of", "CURRENT_DATE")
    # Validate as_of to prevent injection -- only allow YYYY-MM-DD or the literal default
    import re
    if as_of != "CURRENT_DATE" and not re.match(r"^\d{4}-\d{2}-\d{2}$", as_of):
        return jsonify({"error": "as_of must be YYYY-MM-DD"}), 400

    date_expr = "CURRENT_DATE" if as_of == "CURRENT_DATE" else "%s"
    date_params = [] if as_of == "CURRENT_DATE" else [as_of]

    sql = f"""
        SELECT
            om.id,
            om.channel,
            om.message_type,
            om.subject,
            om.sent_at,
            om.follow_up_date,
            om.status,
            om.response_received,
            om.contact_id,
            c.name   AS contact_name,
            c.company AS contact_company,
            om.application_id,
            EXTRACT(EPOCH FROM (NOW() - om.sent_at)) / 86400 AS days_since_sent
        FROM outreach_messages om
        LEFT JOIN contacts c ON c.id = om.contact_id
        WHERE om.follow_up_date <= {date_expr}
          AND (om.response_received IS NULL OR om.response_received = FALSE)
          AND om.status != 'archived'
        ORDER BY om.follow_up_date ASC, om.sent_at ASC
        LIMIT %s
    """
    params = date_params + [limit]
    rows = db.query(sql, params)
    return jsonify({"pending_followups": rows, "count": len(rows)}), 200
