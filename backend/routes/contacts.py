"""Routes for contacts, outreach messages, referrals."""

import csv
import io
import re

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


# ---------------------------------------------------------------------------
# Contact Auto-Discovery
# ---------------------------------------------------------------------------

@bp.route("/api/contacts/auto-discover", methods=["POST"])
def auto_discover_contacts():
    """Given a company name, search DB for mentions of people at that company.

    Searches emails, interview notes, application notes, and outreach messages
    for any references to people at the specified company and suggests them
    as potential contacts.

    Body JSON: {"company": str}
    """
    data = request.get_json(force=True)
    company = data.get("company")
    if not company:
        return jsonify({"error": "company is required"}), 400

    pattern = f"%{company}%"
    suggestions = []

    # 1. Check existing contacts at this company
    existing = db.query(
        """
        SELECT id, name, company, title, email, linkedin_url, relationship_stage
        FROM contacts
        WHERE company ILIKE %s AND merged_into_id IS NULL
        ORDER BY last_touchpoint_at DESC NULLS LAST
        """,
        (pattern,),
    )

    # 2. Search emails for mentions of this company
    email_mentions = db.query(
        """
        SELECT DISTINCT ON (sender_email)
            sender_name, sender_email, subject,
            'email' AS source, sent_at
        FROM emails
        WHERE (subject ILIKE %s OR body ILIKE %s OR sender_name ILIKE %s)
          AND sender_email NOT ILIKE '%%noreply%%'
          AND sender_email NOT ILIKE '%%no-reply%%'
        ORDER BY sender_email, sent_at DESC
        LIMIT 20
        """,
        (pattern, pattern, pattern),
    )

    # 3. Search application notes for contact names
    app_mentions = db.query(
        """
        SELECT DISTINCT company_name, contact_name, contact_email, role,
               'application' AS source
        FROM applications
        WHERE company_name ILIKE %s
          AND contact_name IS NOT NULL
          AND contact_name != ''
        ORDER BY company_name
        LIMIT 20
        """,
        (pattern,),
    )

    # 4. Search outreach messages for this company
    outreach_mentions = db.query(
        """
        SELECT DISTINCT c.name, c.email, c.company, c.title,
               'outreach' AS source
        FROM outreach_messages om
        JOIN contacts c ON c.id = om.contact_id
        WHERE c.company ILIKE %s AND c.merged_into_id IS NULL
        ORDER BY c.name
        LIMIT 20
        """,
        (pattern,),
    )

    # 5. Search interview notes
    interview_mentions = db.query(
        """
        SELECT DISTINCT a.contact_name, a.contact_email, a.company_name,
               i.interviewer_name, i.interviewer_title,
               'interview' AS source
        FROM interviews i
        JOIN applications a ON a.id = i.application_id
        WHERE a.company_name ILIKE %s
          AND (i.interviewer_name IS NOT NULL AND i.interviewer_name != '')
        ORDER BY i.interviewer_name
        LIMIT 20
        """,
        (pattern,),
    )

    # Deduplicate by email where possible
    seen_emails = set()
    for c in existing:
        if c.get("email"):
            seen_emails.add(c["email"].lower())

    # Build suggestions from email mentions
    for em in email_mentions:
        email = em.get("sender_email", "")
        if email.lower() not in seen_emails:
            seen_emails.add(email.lower())
            suggestions.append({
                "name": em.get("sender_name") or email.split("@")[0],
                "email": email,
                "company": company,
                "source": "email",
                "context": f"Found in email: {em.get('subject', '')}",
            })

    # Build suggestions from application contacts
    for am in app_mentions:
        email = am.get("contact_email", "")
        name = am.get("contact_name", "")
        key = email.lower() if email else name.lower()
        if key and key not in seen_emails:
            seen_emails.add(key)
            suggestions.append({
                "name": name,
                "email": email,
                "company": company,
                "source": "application",
                "context": f"Contact for role: {am.get('role', '')}",
            })

    # Build suggestions from interview mentions
    for im in interview_mentions:
        name = im.get("interviewer_name", "")
        email = im.get("contact_email", "")
        key = email.lower() if email else name.lower()
        if key and key not in seen_emails:
            seen_emails.add(key)
            suggestions.append({
                "name": name,
                "email": email,
                "company": company,
                "title": im.get("interviewer_title"),
                "source": "interview",
                "context": f"Interviewer at {im.get('company_name', company)}",
            })

    return jsonify({
        "company": company,
        "existing_contacts": existing,
        "suggestions": suggestions,
        "existing_count": len(existing),
        "suggestion_count": len(suggestions),
    }), 200


# ---------------------------------------------------------------------------
# Contact Import from CSV
# ---------------------------------------------------------------------------

@bp.route("/api/contacts/import/csv", methods=["POST"])
def import_contacts_csv():
    """Import contacts from CSV text. Expects columns: name, email, company, title, source.

    Body JSON: {"csv_text": str, "skip_duplicates": bool (default true)}
    """
    data = request.get_json(force=True)
    csv_text = data.get("csv_text")
    if not csv_text:
        return jsonify({"error": "csv_text is required"}), 400

    skip_duplicates = data.get("skip_duplicates", True)

    reader = csv.DictReader(io.StringIO(csv_text))
    imported = []
    skipped = []
    errors = []

    for i, row in enumerate(reader):
        name = (row.get("name") or row.get("Name") or "").strip()
        if not name:
            errors.append({"row": i + 1, "error": "Missing name"})
            continue

        email = (row.get("email") or row.get("Email") or "").strip()
        company = (row.get("company") or row.get("Company") or "").strip()
        title = (row.get("title") or row.get("Title") or "").strip()
        source = (row.get("source") or row.get("Source") or "csv_import").strip()

        # Check for duplicate by email
        if skip_duplicates and email:
            existing = db.query_one(
                "SELECT id FROM contacts WHERE email ILIKE %s AND merged_into_id IS NULL",
                (email,),
            )
            if existing:
                skipped.append({"name": name, "email": email, "reason": "duplicate email"})
                continue

        contact = db.execute_returning(
            """
            INSERT INTO contacts (name, email, company, title, source)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, name, email, company, title, source
            """,
            (name, email or None, company or None, title or None, source),
        )
        imported.append(contact)

    return jsonify({
        "imported": imported,
        "imported_count": len(imported),
        "skipped": skipped,
        "skipped_count": len(skipped),
        "errors": errors,
        "error_count": len(errors),
    }), 201


# ---------------------------------------------------------------------------
# Contact Import from LinkedIn Messages
# ---------------------------------------------------------------------------

@bp.route("/api/contacts/import/linkedin-messages", methods=["POST"])
def import_linkedin_messages():
    """Parse LinkedIn message export CSV text, extract contact info + conversation context.

    LinkedIn exports typically have columns: From, To, Date, Subject, Content.

    Body JSON: {"csv_text": str, "skip_duplicates": bool (default true)}
    """
    data = request.get_json(force=True)
    csv_text = data.get("csv_text")
    if not csv_text:
        return jsonify({"error": "csv_text is required"}), 400

    skip_duplicates = data.get("skip_duplicates", True)

    reader = csv.DictReader(io.StringIO(csv_text))
    contacts_map = {}  # name -> {info}

    for row in reader:
        # LinkedIn exports use various column names
        from_name = (
            row.get("From") or row.get("FROM") or row.get("Sender") or ""
        ).strip()
        content = (
            row.get("Content") or row.get("CONTENT") or row.get("Body") or row.get("Message") or ""
        ).strip()
        date_str = (
            row.get("Date") or row.get("DATE") or row.get("Sent") or ""
        ).strip()
        subject = (
            row.get("Subject") or row.get("SUBJECT") or ""
        ).strip()

        if not from_name:
            continue

        if from_name not in contacts_map:
            contacts_map[from_name] = {
                "name": from_name,
                "source": "linkedin_messages",
                "message_count": 0,
                "last_message_date": date_str,
                "conversation_snippets": [],
            }

        contacts_map[from_name]["message_count"] += 1
        if date_str > contacts_map[from_name].get("last_message_date", ""):
            contacts_map[from_name]["last_message_date"] = date_str
        if content and len(contacts_map[from_name]["conversation_snippets"]) < 3:
            snippet = content[:200] + ("..." if len(content) > 200 else "")
            contacts_map[from_name]["conversation_snippets"].append(snippet)

    imported = []
    skipped = []

    for name, info in contacts_map.items():
        # Check for duplicate by name
        if skip_duplicates:
            existing = db.query_one(
                "SELECT id FROM contacts WHERE name ILIKE %s AND merged_into_id IS NULL",
                (name,),
            )
            if existing:
                skipped.append({"name": name, "reason": "duplicate name"})
                continue

        notes = f"LinkedIn messages ({info['message_count']} messages)"
        if info["conversation_snippets"]:
            notes += "\n\nRecent messages:\n" + "\n---\n".join(info["conversation_snippets"])

        contact = db.execute_returning(
            """
            INSERT INTO contacts (name, source, notes, linkedin_url)
            VALUES (%s, %s, %s, %s)
            RETURNING id, name, source, notes
            """,
            (name, "linkedin_messages", notes, None),
        )
        imported.append({
            **contact,
            "message_count": info["message_count"],
            "last_message_date": info.get("last_message_date"),
        })

    return jsonify({
        "imported": imported,
        "imported_count": len(imported),
        "skipped": skipped,
        "skipped_count": len(skipped),
        "unique_contacts_found": len(contacts_map),
    }), 201


# ---------------------------------------------------------------------------
# Duplicate Detection
# ---------------------------------------------------------------------------

@bp.route("/api/contacts/duplicates", methods=["GET"])
def find_duplicates():
    """Find potential duplicate contacts by name/email similarity.

    Uses exact email match and trigram-like name matching.
    Query params:
        threshold (float, default 0.8): name similarity threshold (0-1)
    """
    threshold = float(request.args.get("threshold", 0.8))

    # 1. Exact email duplicates
    email_dupes = db.query(
        """
        SELECT email, array_agg(id ORDER BY id) AS ids, array_agg(name ORDER BY id) AS names,
               COUNT(*) AS cnt
        FROM contacts
        WHERE email IS NOT NULL AND email != '' AND merged_into_id IS NULL
        GROUP BY LOWER(email)
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        LIMIT 50
        """
    )

    # 2. Name-based potential duplicates (same first+last name)
    name_dupes = db.query(
        """
        SELECT LOWER(TRIM(name)) AS norm_name,
               array_agg(id ORDER BY id) AS ids,
               array_agg(name ORDER BY id) AS names,
               array_agg(company ORDER BY id) AS companies,
               COUNT(*) AS cnt
        FROM contacts
        WHERE name IS NOT NULL AND name != '' AND merged_into_id IS NULL
        GROUP BY LOWER(TRIM(name))
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        LIMIT 50
        """
    )

    return jsonify({
        "email_duplicates": email_dupes or [],
        "name_duplicates": name_dupes or [],
        "email_duplicate_groups": len(email_dupes or []),
        "name_duplicate_groups": len(name_dupes or []),
    }), 200


# ---------------------------------------------------------------------------
# Contacts by Company
# ---------------------------------------------------------------------------

@bp.route("/api/contacts/by-company/<company>", methods=["GET"])
def contacts_by_company(company):
    """All contacts at a specific company with relationship details."""
    rows = db.query(
        """
        SELECT c.id, c.name, c.title, c.email, c.phone, c.linkedin_url,
               c.relationship, c.relationship_strength, c.relationship_stage,
               c.health_score, c.last_contact, c.last_touchpoint_at, c.notes,
               (SELECT COUNT(*) FROM touchpoints t WHERE t.contact_id = c.id) AS touchpoint_count,
               (SELECT COUNT(*) FROM outreach_messages om WHERE om.contact_id = c.id) AS outreach_count
        FROM contacts c
        WHERE c.company ILIKE %s AND c.merged_into_id IS NULL
        ORDER BY c.relationship_strength ASC NULLS LAST, c.health_score DESC NULLS LAST
        """,
        (f"%{company}%",),
    )
    return jsonify({
        "company": company,
        "contacts": rows or [],
        "count": len(rows or []),
    }), 200


# ---------------------------------------------------------------------------
# Referral Map
# ---------------------------------------------------------------------------

@bp.route("/api/contacts/referral-map", methods=["GET"])
def referral_map():
    """Map of who referred whom, showing referral chains."""
    rows = db.query(
        """
        SELECT r.id, r.referral_date, r.status,
               r.contact_id, c.name AS referrer_name, c.company AS referrer_company,
               r.application_id, a.company_name AS referred_company, a.role AS referred_role,
               r.saved_job_id, r.notes
        FROM referrals r
        JOIN contacts c ON c.id = r.contact_id
        LEFT JOIN applications a ON a.id = r.application_id
        ORDER BY r.referral_date DESC NULLS LAST, r.created_at DESC
        """
    )

    # Group by referrer
    by_referrer = {}
    for r in (rows or []):
        rid = r["contact_id"]
        if rid not in by_referrer:
            by_referrer[rid] = {
                "referrer_id": rid,
                "referrer_name": r["referrer_name"],
                "referrer_company": r["referrer_company"],
                "referrals": [],
            }
        by_referrer[rid]["referrals"].append({
            "referral_id": r["id"],
            "company": r.get("referred_company"),
            "role": r.get("referred_role"),
            "status": r["status"],
            "date": r["referral_date"],
            "notes": r.get("notes"),
        })

    return jsonify({
        "referral_map": list(by_referrer.values()),
        "total_referrals": len(rows or []),
        "total_referrers": len(by_referrer),
    }), 200
