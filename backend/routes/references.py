"""Routes for reference management — roster, warmth, rotation, prep, effectiveness."""

import json
from datetime import date, timedelta
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("references", __name__)


# ---------------------------------------------------------------------------
# a) GET /api/references — List reference roster
# ---------------------------------------------------------------------------

@bp.route("/api/references", methods=["GET"])
def list_references():
    """List all references with topics, role types, warmth, and usage stats."""
    rows = db.query(
        """
        SELECT id, name, company, title, relationship, email, phone,
               linkedin_url, relationship_strength, last_contact,
               reference_topics, reference_role_types, reference_times_used,
               reference_last_used, reference_effectiveness, is_reference,
               reference_priority, notes, created_at, updated_at
        FROM contacts
        WHERE is_reference = TRUE OR relationship = 'reference'
        ORDER BY reference_priority = 'primary' DESC,
                 relationship_strength = 'strong' DESC,
                 reference_times_used ASC,
                 name
        """
    )
    return jsonify(rows), 200


# ---------------------------------------------------------------------------
# b) POST /api/references/<contact_id>/designate — Mark contact as reference
# ---------------------------------------------------------------------------

@bp.route("/api/references/<int:contact_id>/designate", methods=["POST"])
def designate_reference(contact_id):
    """Mark an existing contact as a reference."""
    data = request.get_json(force=True)

    contact = db.query_one("SELECT id FROM contacts WHERE id = %s", [contact_id])
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    row = db.execute_returning(
        """
        UPDATE contacts
        SET is_reference = TRUE,
            reference_topics = %s,
            reference_role_types = %s,
            reference_priority = %s,
            relationship = CASE WHEN relationship IS NULL THEN 'reference' ELSE relationship END,
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (
            data.get("reference_topics", []),
            data.get("reference_role_types", []),
            data.get("reference_priority", "primary"),
            contact_id,
        ),
    )
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# c) POST /api/references/match-role — Match references to a role type
# ---------------------------------------------------------------------------

@bp.route("/api/references/match-role", methods=["POST"])
def match_role():
    """Match references to a given role type, ranked by fit + warmth + usage."""
    data = request.get_json(force=True)
    role_type = data.get("role_type", "")
    if not role_type:
        return jsonify({"error": "role_type is required"}), 400

    rows = db.query(
        """
        SELECT id, name, company, title, reference_topics, reference_role_types,
               relationship_strength, reference_times_used, reference_last_used,
               reference_priority, last_contact,
               (%s = ANY(reference_role_types)) AS role_match
        FROM contacts
        WHERE is_reference = TRUE OR relationship = 'reference'
        ORDER BY
            (%s = ANY(reference_role_types)) DESC,
            relationship_strength = 'strong' DESC,
            reference_times_used ASC,
            last_contact DESC NULLS LAST
        """,
        [role_type, role_type],
    )
    return jsonify(rows), 200


# ---------------------------------------------------------------------------
# d) GET /api/references/warmth — Check reference warmth
# ---------------------------------------------------------------------------

@bp.route("/api/references/warmth", methods=["GET"])
def check_warmth():
    """Return references with warmth status and days since last contact."""
    rows = db.query(
        """
        SELECT id, name, company, title, relationship_strength, last_contact,
               reference_times_used, reference_last_used, reference_priority,
               CASE
                   WHEN last_contact IS NULL THEN NULL
                   ELSE CURRENT_DATE - last_contact
               END AS days_since_contact
        FROM contacts
        WHERE is_reference = TRUE OR relationship = 'reference'
        ORDER BY last_contact ASC NULLS FIRST
        """
    )

    for row in rows:
        days = row.get("days_since_contact")
        if days is None:
            row["warmth_status"] = "unknown"
            row["needs_checkin"] = True
            row["suggested_touchpoint"] = "Initial outreach — reconnect and confirm willingness"
        elif days > 180:
            row["warmth_status"] = "cold"
            row["needs_checkin"] = True
            row["suggested_touchpoint"] = "Personal catch-up call or coffee — rebuild rapport"
        elif days > 90:
            row["warmth_status"] = "cooling"
            row["needs_checkin"] = True
            row["suggested_touchpoint"] = "Quick email update on your search progress"
        elif days > 30:
            row["warmth_status"] = "warm"
            row["needs_checkin"] = False
            row["suggested_touchpoint"] = "Share an article or congratulate on something"
        else:
            row["warmth_status"] = "hot"
            row["needs_checkin"] = False
            row["suggested_touchpoint"] = None

    return jsonify(rows), 200


# ---------------------------------------------------------------------------
# e) GET /api/references/rotation — Track reference rotation
# ---------------------------------------------------------------------------

@bp.route("/api/references/rotation", methods=["GET"])
def rotation():
    """Track usage history per reference; flag over/under-used."""
    rows = db.query(
        """
        SELECT c.id, c.name, c.company, c.title, c.reference_times_used,
               c.reference_last_used, c.reference_priority,
               COALESCE(
                   json_agg(
                       json_build_object(
                           'application_id', r.application_id,
                           'referral_date', r.referral_date,
                           'status', r.status
                       )
                   ) FILTER (WHERE r.id IS NOT NULL),
                   '[]'::json
               ) AS usage_history
        FROM contacts c
        LEFT JOIN referrals r ON r.contact_id = c.id
        WHERE c.is_reference = TRUE OR c.relationship = 'reference'
        GROUP BY c.id
        ORDER BY c.reference_times_used DESC, c.name
        """
    )

    for row in rows:
        uses = row.get("reference_times_used") or 0
        if uses > 3:
            row["rotation_flag"] = "overused"
        elif uses == 0:
            row["rotation_flag"] = "unused"
        else:
            row["rotation_flag"] = "healthy"

    return jsonify(rows), 200


# ---------------------------------------------------------------------------
# f) POST /api/references/<contact_id>/pre-brief — Generate pre-brief
# ---------------------------------------------------------------------------

@bp.route("/api/references/<int:contact_id>/pre-brief", methods=["POST"])
def pre_brief(contact_id):
    """Generate a pre-brief message for a reference about a specific application."""
    data = request.get_json(force=True)
    application_id = data.get("application_id")
    if not application_id:
        return jsonify({"error": "application_id is required"}), 400

    contact = db.query_one(
        "SELECT id, name, company, title FROM contacts WHERE id = %s", [contact_id]
    )
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    app = db.query_one(
        "SELECT id, company_name, role, status FROM applications WHERE id = %s",
        [application_id],
    )
    if not app:
        return jsonify({"error": "Application not found"}), 404

    header = db.query_one("SELECT full_name, credentials FROM resume_header LIMIT 1")
    candidate_name = header["full_name"] if header else "the candidate"

    # Pull top bullets for context
    bullets = db.query(
        """
        SELECT b.text FROM bullets b
        JOIN career_history ch ON b.career_history_id = ch.id
        ORDER BY ch.start_date DESC
        LIMIT 5
        """
    )
    bullet_text = "\n".join(f"- {b['text']}" for b in bullets) if bullets else ""

    content = (
        f"Hi {contact['name']},\n\n"
        f"I wanted to give you a heads-up that {candidate_name} has applied for "
        f"the {app['role']} position at {app['company_name']}. "
        f"You may receive a call from their team.\n\n"
        f"Here are some key points that would be great to highlight:\n\n"
        f"{bullet_text}\n\n"
        f"Thank you for being a reference... it means a lot.\n\n"
        f"Best regards"
    )

    row = db.execute_returning(
        """
        INSERT INTO generated_materials (application_id, type, content, content_format, status, generated_at)
        VALUES (%s, 'reference_prebrief', %s, 'text', 'draft', NOW())
        RETURNING *
        """,
        [application_id, content],
    )
    return jsonify(row), 201


# ---------------------------------------------------------------------------
# g) POST /api/references/<contact_id>/thank-you — Post-reference thank-you
# ---------------------------------------------------------------------------

@bp.route("/api/references/<int:contact_id>/thank-you", methods=["POST"])
def thank_you(contact_id):
    """Generate a thank-you note for a reference."""
    data = request.get_json(force=True)
    application_id = data.get("application_id")
    outcome = data.get("outcome", "pending")

    contact = db.query_one(
        "SELECT id, name FROM contacts WHERE id = %s", [contact_id]
    )
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    app_context = ""
    if application_id:
        app = db.query_one(
            "SELECT company_name, role FROM applications WHERE id = %s",
            [application_id],
        )
        if app:
            app_context = f" for the {app['role']} role at {app['company_name']}"

    outcome_line = ""
    if outcome == "offer":
        outcome_line = " I'm happy to share that I received an offer!"
    elif outcome == "rejection":
        outcome_line = " Unfortunately this one didn't work out, but your support made a real difference."

    content = (
        f"Hi {contact['name']},\n\n"
        f"Thank you so much for serving as a reference{app_context}.{outcome_line} "
        f"I really appreciate you taking the time to speak on my behalf.\n\n"
        f"I'll keep you posted on how things develop.\n\n"
        f"Best regards"
    )

    row = db.execute_returning(
        """
        INSERT INTO generated_materials (application_id, type, content, content_format, status, generated_at)
        VALUES (%s, 'reference_thankyou', %s, 'text', 'draft', NOW())
        RETURNING *
        """,
        [application_id, content],
    )
    return jsonify(row), 201


# ---------------------------------------------------------------------------
# h) GET /api/references/effectiveness — Track reference effectiveness
# ---------------------------------------------------------------------------

@bp.route("/api/references/effectiveness", methods=["GET"])
def effectiveness():
    """Track reference effectiveness by linking usage to application outcomes."""
    rows = db.query(
        """
        SELECT c.id, c.name, c.company, c.title, c.reference_times_used,
               c.reference_effectiveness,
               COUNT(r.id) AS total_referrals,
               COUNT(CASE WHEN a.status = 'offer' THEN 1 END) AS offers,
               COUNT(CASE WHEN a.status = 'rejected' THEN 1 END) AS rejections,
               COUNT(CASE WHEN a.status NOT IN ('offer', 'rejected') THEN 1 END) AS other
        FROM contacts c
        LEFT JOIN referrals r ON r.contact_id = c.id
        LEFT JOIN applications a ON r.application_id = a.id
        WHERE c.is_reference = TRUE OR c.relationship = 'reference'
        GROUP BY c.id
        ORDER BY COUNT(CASE WHEN a.status = 'offer' THEN 1 END) DESC, c.name
        """
    )

    for row in rows:
        total = row["total_referrals"] or 0
        offers = row["offers"] or 0
        row["success_rate"] = round(offers / total * 100, 1) if total > 0 else None

    return jsonify(rows), 200


# ---------------------------------------------------------------------------
# i) POST /api/references/<contact_id>/log-use — Log reference usage
# ---------------------------------------------------------------------------

@bp.route("/api/references/<int:contact_id>/log-use", methods=["POST"])
def log_use(contact_id):
    """Log that a reference was used for an application."""
    data = request.get_json(force=True)
    application_id = data.get("application_id")
    if not application_id:
        return jsonify({"error": "application_id is required"}), 400

    contact = db.query_one("SELECT id FROM contacts WHERE id = %s", [contact_id])
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    # Update contact usage stats
    db.execute_returning(
        """
        UPDATE contacts
        SET reference_times_used = COALESCE(reference_times_used, 0) + 1,
            reference_last_used = CURRENT_DATE,
            updated_at = NOW()
        WHERE id = %s
        RETURNING id
        """,
        [contact_id],
    )

    # Create referral record if not exists
    existing = db.query_one(
        "SELECT id FROM referrals WHERE contact_id = %s AND application_id = %s",
        [contact_id, application_id],
    )
    if not existing:
        db.execute_returning(
            """
            INSERT INTO referrals (contact_id, application_id, referral_date, status)
            VALUES (%s, %s, CURRENT_DATE, 'submitted')
            RETURNING *
            """,
            [contact_id, application_id],
        )

    return jsonify({"status": "logged", "contact_id": contact_id, "application_id": application_id}), 200


# ---------------------------------------------------------------------------
# j) POST /api/references/batch-checkin — Batch check-in outreach
# ---------------------------------------------------------------------------

@bp.route("/api/references/batch-checkin", methods=["POST"])
def batch_checkin():
    """Generate personalized check-in drafts for references needing warmth."""
    threshold_days = int(request.args.get("threshold_days", 90))

    header = db.query_one("SELECT full_name FROM resume_header LIMIT 1")
    sender_name = header["full_name"] if header else "me"

    stale = db.query(
        """
        SELECT id, name, company, title, last_contact,
               CASE WHEN last_contact IS NOT NULL
                    THEN CURRENT_DATE - last_contact
                    ELSE NULL END AS days_since
        FROM contacts
        WHERE (is_reference = TRUE OR relationship = 'reference')
          AND (last_contact IS NULL OR last_contact < CURRENT_DATE - %s)
        ORDER BY last_contact ASC NULLS FIRST
        """,
        [threshold_days],
    )

    if not stale:
        return jsonify({"message": "All references are warm", "drafts": []}), 200

    drafts = []
    for ref in stale:
        company_note = f" at {ref['company']}" if ref.get("company") else ""
        days_note = f" (last contact: {ref['days_since']} days ago)" if ref.get("days_since") else " (no prior contact on record)"

        body = (
            f"Hi {ref['name']},\n\n"
            f"Hope things are going well{company_note}. I wanted to check in and "
            f"share a quick update on my job search. "
            f"I really value your support as a reference{days_note}.\n\n"
            f"Would love to catch up briefly when you have a moment.\n\n"
            f"Best,\n{sender_name}"
        )

        msg = db.execute_returning(
            """
            INSERT INTO outreach_messages (contact_id, channel, direction, subject, body, sent_at, created_at)
            VALUES (%s, 'email', 'outbound', %s, %s, NULL, NOW())
            RETURNING *
            """,
            [
                ref["id"],
                f"Checking in — {sender_name}",
                body,
            ],
        )
        drafts.append(msg)

    return jsonify({"message": f"Generated {len(drafts)} check-in drafts", "drafts": drafts}), 201
