"""Routes for Application Materials Generation (cover letters, thank-yous, outreach)."""

import json
import logging
from flask import Blueprint, request, jsonify
import db
from ai_providers.router import route_inference

logger = logging.getLogger(__name__)

bp = Blueprint("materials", __name__)


# ---------------------------------------------------------------------------
# Generated Materials (cover letters, thank-yous)
# ---------------------------------------------------------------------------

@bp.route("/api/materials", methods=["GET"])
def list_materials():
    """List generated materials with optional filters.

    Query params:
        material_type: cover_letter, thank_you, outreach, linkedin_post, resume_variant
        application_id: filter by application
        status: draft, reviewed, sent, archived
        limit: max results (default 50)
        offset: pagination offset (default 0)
    """
    material_type = request.args.get("material_type")
    application_id = request.args.get("application_id")
    status = request.args.get("status")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []

    if material_type:
        clauses.append("type = %s")
        params.append(material_type)
    if application_id:
        clauses.append("application_id = %s")
        params.append(int(application_id))
    if status:
        clauses.append("status = %s")
        params.append(status)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT *
        FROM generated_materials
        {where}
        ORDER BY generated_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/materials/<int:material_id>", methods=["GET"])
def get_material(material_id):
    """Get a single generated material by ID."""
    row = db.query_one(
        "SELECT * FROM generated_materials WHERE id = %s",
        (material_id,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/materials/cover-letter", methods=["POST"])
def generate_cover_letter():
    """Generate a cover letter.

    Body (JSON):
        application_id: optional application ID (pulls gap analysis)
        saved_job_id: optional saved job ID
        company_name: optional company name override
        role_title: optional role title override
    """
    data = request.get_json(force=True)
    application_id = data.get("application_id")
    saved_job_id = data.get("saved_job_id")
    company_name = data.get("company_name")
    role_title = data.get("role_title")

    if not application_id and not saved_job_id:
        return jsonify({"error": "application_id or saved_job_id is required"}), 400

    generation_context = {}

    # Look up application and gap analysis if application_id provided
    if application_id:
        app = db.query_one(
            "SELECT * FROM applications WHERE id = %s",
            (application_id,),
        )
        if app:
            company_name = company_name or app.get("company_name")
            role_title = role_title or app.get("role")
            saved_job_id = saved_job_id or app.get("saved_job_id")
            generation_context["application_id"] = application_id

        # Pull gap analysis
        gap = db.query_one(
            "SELECT * FROM gap_analyses WHERE application_id = %s ORDER BY created_at DESC LIMIT 1",
            (application_id,),
        )
        if gap:
            generation_context["gap_analysis_id"] = gap["id"]

    # Look up saved job for additional context
    if saved_job_id:
        job = db.query_one(
            "SELECT * FROM saved_jobs WHERE id = %s",
            (saved_job_id,),
        )
        if job:
            company_name = company_name or job.get("company")
            role_title = role_title or job.get("title")
            generation_context["saved_job_id"] = saved_job_id

    # Look up company dossier if company available
    if company_name:
        dossier = db.query_one(
            "SELECT * FROM companies WHERE name ILIKE %s LIMIT 1",
            (company_name,),
        )
        if dossier:
            generation_context["company_id"] = dossier["id"]

    # Pull candidate name from resume_header
    header = db.query_one("SELECT full_name FROM resume_header ORDER BY id LIMIT 1")
    candidate_name = header["full_name"] if header else "Candidate"
    generation_context["candidate_profile"] = True

    # Pull top career bullets
    bullets = db.query(
        "SELECT text FROM bullets ORDER BY id DESC LIMIT 5"
    )
    top_bullets = [b["text"] for b in bullets] if bullets else []
    generation_context["bullet_count"] = len(top_bullets)

    # Generate placeholder cover letter with real data references
    bullet_text = "\n".join(f"- {b}" for b in top_bullets[:3]) if top_bullets else "- [Key achievement from career history]"
    content = (
        f"Dear Hiring Manager,\n\n"
        f"I am writing to express my interest in the {role_title or '[Role]'} position "
        f"at {company_name or '[Company]'}.\n\n"
        f"{candidate_name} brings the following key achievements:\n{bullet_text}\n\n"
        f"[AI will expand with gap analysis alignment, company-specific value proposition, "
        f"and voice-checked closing paragraph.]\n\n"
        f"Sincerely,\n{candidate_name}"
    )

    row = db.execute_returning(
        """
        INSERT INTO generated_materials
            (type, application_id, saved_job_id, company_name, role_title,
             content, content_format, voice_check_passed, generation_context, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            "cover_letter",
            application_id,
            saved_job_id,
            company_name,
            role_title,
            content,
            "text",
            False,
            json.dumps(generation_context),
            "draft",
        ),
    )
    return jsonify(row), 201


@bp.route("/api/materials/thank-you", methods=["POST"])
def generate_thank_you():
    """Generate a post-interview thank-you note.

    Body (JSON):
        application_id (required): application ID
        interviewer_name: optional interviewer name
        interview_notes: optional notes from the interview
        debrief_notes: optional debrief notes
    """
    data = request.get_json(force=True)
    application_id = data.get("application_id")
    if not application_id:
        return jsonify({"error": "application_id is required"}), 400

    interviewer_name = data.get("interviewer_name", "the team")
    interview_notes = data.get("interview_notes")
    debrief_notes = data.get("debrief_notes")

    generation_context = {"application_id": application_id}

    # Look up application
    app = db.query_one(
        "SELECT * FROM applications WHERE id = %s",
        (application_id,),
    )
    company_name = app.get("company_name") if app else None
    role_title = app.get("role") if app else None

    # Pull debrief data if available (join through interviews table)
    debrief = db.query_one(
        """SELECT d.* FROM interview_debriefs d
           JOIN interviews i ON d.interview_id = i.id
           WHERE i.application_id = %s
           ORDER BY d.created_at DESC LIMIT 1""",
        (application_id,),
    )
    if debrief:
        generation_context["debrief_id"] = debrief["id"]
        debrief_notes = debrief_notes or (debrief.get("notes") if debrief else None)

    if interview_notes:
        generation_context["interview_notes_provided"] = True
    if debrief_notes:
        generation_context["debrief_notes_provided"] = True

    # Pull candidate name from resume_header
    header = db.query_one("SELECT full_name FROM resume_header ORDER BY id LIMIT 1")
    candidate_name = header["full_name"] if header else "Candidate"

    # Generate under-200-word thank-you
    notes_ref = ""
    if interview_notes:
        notes_ref = f" Our discussion about {interview_notes[:80]}... was particularly engaging."
    elif debrief_notes:
        notes_ref = f" I especially valued our conversation about {debrief_notes[:80]}..."

    content = (
        f"Hi {interviewer_name},\n\n"
        f"Thank you for taking the time to meet with me about the "
        f"{role_title or '[Role]'} position at {company_name or '[Company]'}."
        f"{notes_ref}\n\n"
        f"[AI will personalize with specific discussion points, reiterate fit, "
        f"and close with next-step enthusiasm.]\n\n"
        f"Best regards,\n{candidate_name}"
    )

    row = db.execute_returning(
        """
        INSERT INTO generated_materials
            (type, application_id, company_name, role_title,
             content, content_format, voice_check_passed, generation_context, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            "thank_you",
            application_id,
            company_name,
            role_title,
            content,
            "text",
            False,
            json.dumps(generation_context),
            "draft",
        ),
    )
    return jsonify(row), 201


@bp.route("/api/materials/<int:material_id>", methods=["PUT", "PATCH"])
def update_material(material_id):
    """Update a generated material.

    Body (JSON): any subset of updatable fields.
        content, status, voice_check_passed, voice_violations, file_path, content_format
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    allowed = ["content", "status", "voice_check_passed", "voice_violations",
               "file_path", "content_format"]
    sets, params = [], []
    for field in allowed:
        if field in data:
            val = data[field]
            if field == "voice_violations" and val is not None:
                val = json.dumps(val)
            sets.append(f"{field} = %s")
            params.append(val)

    # Always bump updated_at
    sets.append("updated_at = NOW()")

    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(material_id)
    row = db.execute_returning(
        f"""
        UPDATE generated_materials
        SET {', '.join(sets)}
        WHERE id = %s
        RETURNING *
        """,
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/materials/<int:material_id>", methods=["DELETE"])
def delete_material(material_id):
    """Soft-delete a material by setting status to archived."""
    row = db.execute_returning(
        """
        UPDATE generated_materials
        SET status = 'archived', updated_at = NOW()
        WHERE id = %s
        RETURNING id, status
        """,
        (material_id,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Outreach Messages
# ---------------------------------------------------------------------------

@bp.route("/api/materials/outreach", methods=["GET"])
def list_materials_outreach():
    """List outreach messages with optional filters (materials view).

    Query params:
        contact_id: filter by contact
        message_type: cold_outreach, warm_intro_request, follow_up, thank_you, networking, recruiter
        status: draft, sent, replied, no_response, bounced
        channel: email, linkedin, phone
        limit: max results (default 50)
        offset: pagination offset (default 0)
    """
    contact_id = request.args.get("contact_id")
    message_type = request.args.get("message_type")
    status = request.args.get("status")
    channel = request.args.get("channel")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []

    if contact_id:
        clauses.append("contact_id = %s")
        params.append(int(contact_id))
    if message_type:
        clauses.append("message_type = %s")
        params.append(message_type)
    if status:
        clauses.append("status = %s")
        params.append(status)
    if channel:
        clauses.append("channel = %s")
        params.append(channel)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT *
        FROM outreach_messages
        {where}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/materials/outreach/<int:message_id>", methods=["GET"])
def get_materials_outreach(message_id):
    """Get a single outreach message by ID."""
    row = db.query_one(
        "SELECT * FROM outreach_messages WHERE id = %s",
        (message_id,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/outreach/personalized", methods=["POST"])
def generate_personalized_outreach():
    """Generate personalized outreach for a contact.

    Body (JSON):
        contact_id (required): contact to reach out to
        application_id: optional application for context
        message_type: networking, cold_outreach, follow_up, recruiter (default: networking)
        channel: email, linkedin, phone (default: email)
    """
    data = request.get_json(force=True)
    contact_id = data.get("contact_id")
    if not contact_id:
        return jsonify({"error": "contact_id is required"}), 400

    application_id = data.get("application_id")
    message_type = data.get("message_type", "networking")
    channel = data.get("channel", "email")

    personalization_context = {}

    # Look up contact
    contact = db.query_one(
        "SELECT * FROM contacts WHERE id = %s",
        (contact_id,),
    )
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    contact_name = contact.get("name") or contact.get("full_name") or "there"
    contact_company = contact.get("company")
    contact_title = contact.get("title")
    personalization_context["contact_name"] = contact_name
    if contact_company:
        personalization_context["contact_company"] = contact_company
    if contact_title:
        personalization_context["contact_title"] = contact_title

    # Look up company if contact has one
    company_info = None
    if contact_company:
        company_info = db.query_one(
            "SELECT * FROM companies WHERE name ILIKE %s LIMIT 1",
            (contact_company,),
        )
        if company_info:
            personalization_context["company_id"] = company_info["id"]

    # Pull candidate name from resume_header
    header = db.query_one("SELECT full_name FROM resume_header ORDER BY id LIMIT 1")
    candidate_name = header["full_name"] if header else "Candidate"

    # Application context
    role_context = ""
    if application_id:
        app = db.query_one(
            "SELECT * FROM applications WHERE id = %s",
            (application_id,),
        )
        if app:
            role_context = f" regarding the {app.get('role', 'open')} role"
            personalization_context["application_id"] = application_id

    # Generate subject and body
    subject = f"Connecting{role_context}" if channel == "email" else None
    company_ref = f" at {contact_company}" if contact_company else ""
    title_ref = f" ({contact_title})" if contact_title else ""

    body = (
        f"Hi {contact_name},\n\n"
        f"I hope this message finds you well{title_ref}{company_ref}. "
        f"My name is {candidate_name}{role_context}.\n\n"
        f"[AI will personalize with shared connections, mutual interests, "
        f"specific value proposition, and clear ask.]\n\n"
        f"Best,\n{candidate_name}"
    )

    row = db.execute_returning(
        """
        INSERT INTO outreach_messages
            (contact_id, application_id, message_type, channel, direction, subject, body,
             personalization_context, voice_check_passed, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            contact_id,
            application_id,
            message_type,
            channel,
            "outbound",
            subject,
            body,
            json.dumps(personalization_context),
            False,
            "draft",
        ),
    )
    return jsonify(row), 201


@bp.route("/api/outreach/cold", methods=["POST"])
def generate_cold_outreach():
    """Generate cold outreach to a hiring manager.

    Body (JSON):
        company_name (required): target company
        role_title (required): target role
        contact_id: optional contact ID if known
    """
    data = request.get_json(force=True)
    company_name = data.get("company_name")
    role_title = data.get("role_title")
    if not company_name or not role_title:
        return jsonify({"error": "company_name and role_title are required"}), 400

    contact_id = data.get("contact_id")
    personalization_context = {
        "company_name": company_name,
        "role_title": role_title,
        "outreach_type": "cold_to_hiring_manager",
    }

    # Look up company dossier
    dossier = db.query_one(
        "SELECT * FROM companies WHERE name ILIKE %s LIMIT 1",
        (company_name,),
    )
    if dossier:
        personalization_context["company_id"] = dossier["id"]

    # Pull candidate name from resume_header
    header = db.query_one("SELECT full_name FROM resume_header ORDER BY id LIMIT 1")
    candidate_name = header["full_name"] if header else "Candidate"

    # Contact name if provided
    contact_name = "Hiring Manager"
    if contact_id:
        contact = db.query_one(
            "SELECT * FROM contacts WHERE id = %s",
            (contact_id,),
        )
        if contact:
            contact_name = contact.get("name") or contact.get("full_name") or "Hiring Manager"
            personalization_context["contact_id"] = contact_id

    subject = f"Interest in {role_title} at {company_name}"
    body = (
        f"Dear {contact_name},\n\n"
        f"I came across the {role_title} opportunity at {company_name} and "
        f"wanted to reach out directly.\n\n"
        f"[AI will add specific company research, relevant achievements, "
        f"and a concise value proposition tied to the role.]\n\n"
        f"Best regards,\n{candidate_name}"
    )

    row = db.execute_returning(
        """
        INSERT INTO outreach_messages
            (contact_id, message_type, channel, direction, subject, body,
             personalization_context, voice_check_passed, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            contact_id,
            "cold_outreach",
            "email",
            "outbound",
            subject,
            body,
            json.dumps(personalization_context),
            False,
            "draft",
        ),
    )
    return jsonify(row), 201


@bp.route("/api/outreach/warm-intro", methods=["POST"])
def generate_warm_intro():
    """Generate a warm intro request.

    Body (JSON):
        contact_id (required): the person you're asking for the intro
        target_company (required): the company you want an intro to
    """
    data = request.get_json(force=True)
    contact_id = data.get("contact_id")
    target_company = data.get("target_company")
    if not contact_id or not target_company:
        return jsonify({"error": "contact_id and target_company are required"}), 400

    personalization_context = {
        "target_company": target_company,
        "outreach_type": "warm_intro_request",
    }

    # Look up contact
    contact = db.query_one(
        "SELECT * FROM contacts WHERE id = %s",
        (contact_id,),
    )
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    contact_name = contact.get("name") or contact.get("full_name") or "there"
    personalization_context["contact_name"] = contact_name
    personalization_context["contact_company"] = contact.get("company")

    # Pull candidate name from resume_header
    header = db.query_one("SELECT full_name FROM resume_header ORDER BY id LIMIT 1")
    candidate_name = header["full_name"] if header else "Candidate"

    subject = f"Quick favor - intro to someone at {target_company}?"
    body = (
        f"Hi {contact_name},\n\n"
        f"Hope you're doing well. I'm exploring opportunities at {target_company} "
        f"and was wondering if you might know anyone there who'd be open to a quick chat.\n\n"
        f"[AI will add shared history context, specific ask, "
        f"and make it easy to say yes or no.]\n\n"
        f"Thanks either way,\n{candidate_name}"
    )

    row = db.execute_returning(
        """
        INSERT INTO outreach_messages
            (contact_id, message_type, channel, direction, subject, body,
             personalization_context, voice_check_passed, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            contact_id,
            "warm_intro_request",
            "email",
            "outbound",
            subject,
            body,
            json.dumps(personalization_context),
            False,
            "draft",
        ),
    )
    return jsonify(row), 201


@bp.route("/api/outreach/batch", methods=["POST"])
def batch_outreach():
    """Batch generate outreach for multiple contacts.

    Body (JSON):
        contact_ids (required): array of contact IDs
        message_type: networking, cold_outreach, follow_up, recruiter (default: networking)
        application_id: optional application for context
    """
    data = request.get_json(force=True)
    contact_ids = data.get("contact_ids")
    if not contact_ids or not isinstance(contact_ids, list):
        return jsonify({"error": "contact_ids array is required"}), 400

    message_type = data.get("message_type", "networking")
    application_id = data.get("application_id")

    # Pull candidate name from resume_header
    header = db.query_one("SELECT full_name FROM resume_header ORDER BY id LIMIT 1")
    candidate_name = header["full_name"] if header else "Candidate"

    # Application context
    role_context = ""
    if application_id:
        app = db.query_one(
            "SELECT * FROM applications WHERE id = %s",
            (application_id,),
        )
        if app:
            role_context = f" regarding the {app.get('role', 'open')} role"

    created = []
    for cid in contact_ids:
        contact = db.query_one(
            "SELECT * FROM contacts WHERE id = %s",
            (cid,),
        )
        if not contact:
            continue

        contact_name = contact.get("name") or contact.get("full_name") or "there"
        contact_company = contact.get("company")
        company_ref = f" at {contact_company}" if contact_company else ""

        personalization_context = {
            "contact_name": contact_name,
            "batch": True,
        }
        if contact_company:
            personalization_context["contact_company"] = contact_company
        if application_id:
            personalization_context["application_id"] = application_id

        subject = f"Connecting{role_context}" if message_type != "cold_outreach" else f"Quick question{company_ref}"
        body = (
            f"Hi {contact_name},\n\n"
            f"My name is {candidate_name}{role_context}. "
            f"I'd love to connect{company_ref}.\n\n"
            f"[AI will personalize per contact.]\n\n"
            f"Best,\n{candidate_name}"
        )

        row = db.execute_returning(
            """
            INSERT INTO outreach_messages
                (contact_id, application_id, message_type, channel, direction, subject, body,
                 personalization_context, voice_check_passed, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                cid,
                application_id,
                message_type,
                "email",
                "outbound",
                subject,
                body,
                json.dumps(personalization_context),
                False,
                "draft",
            ),
        )
        created.append(row)

    return jsonify({"count": len(created), "messages": created}), 201


@bp.route("/api/materials/outreach/<int:message_id>", methods=["PUT", "PATCH"])
def update_materials_outreach(message_id):
    """Update an outreach message.

    Body (JSON): any subset of updatable fields.
        body, subject, status, outcome, sent_at, response_received_at,
        voice_check_passed, gmail_draft_id, channel
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    allowed = ["body", "subject", "status", "outcome", "sent_at",
               "response_received_at", "voice_check_passed", "gmail_draft_id", "channel"]
    sets, params = [], []
    for field in allowed:
        if field in data:
            sets.append(f"{field} = %s")
            params.append(data[field])

    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(message_id)
    row = db.execute_returning(
        f"""
        UPDATE outreach_messages
        SET {', '.join(sets)}
        WHERE id = %s
        RETURNING *
        """,
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/outreach/<int:message_id>/mark-sent", methods=["POST"])
def mark_outreach_sent(message_id):
    """Mark an outreach message as sent."""
    row = db.execute_returning(
        """
        UPDATE outreach_messages
        SET status = 'sent', sent_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (message_id,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# GET /api/materials/history — All generated materials with dates and targets
# ---------------------------------------------------------------------------

@bp.route("/api/materials/history", methods=["GET"])
def materials_history():
    """List all generated materials (cover letters, thank-yous, outreach) with dates and targets.

    Query params:
        days: limit to last N days (default: all)
        material_type: filter by type
        limit: max results (default 100)
    """
    days = request.args.get("days")
    material_type = request.args.get("material_type")
    limit = int(request.args.get("limit", 100))

    clauses, params = [], []

    if days:
        clauses.append("gm.generated_at >= NOW() - INTERVAL '%s days'")
        params.append(int(days))
    if material_type:
        clauses.append("gm.type = %s")
        params.append(material_type)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    rows = db.query(
        f"""
        SELECT gm.id, gm.type, gm.status, gm.generated_at, gm.content_format,
               gm.application_id,
               a.company_name AS target_company, a.role AS target_role,
               LEFT(gm.content, 200) AS content_preview
        FROM generated_materials gm
        LEFT JOIN applications a ON a.id = gm.application_id
        {where}
        ORDER BY gm.generated_at DESC
        LIMIT %s
        """,
        params,
    )

    # Also include outreach messages
    outreach_clauses, outreach_params = [], []
    if days:
        outreach_clauses.append("om.created_at >= NOW() - INTERVAL '%s days'")
        outreach_params.append(int(days))
    outreach_where = f"WHERE {' AND '.join(outreach_clauses)}" if outreach_clauses else ""

    outreach = db.query(
        f"""
        SELECT om.id, om.message_type AS type, om.status, om.created_at AS generated_at,
               'text' AS content_format, om.application_id,
               c.company AS target_company, c.name AS target_contact,
               LEFT(om.body, 200) AS content_preview
        FROM outreach_messages om
        LEFT JOIN contacts c ON c.id = om.contact_id
        {outreach_where}
        ORDER BY om.created_at DESC
        LIMIT 50
        """,
        outreach_params,
    )

    return jsonify({
        "materials": rows or [],
        "outreach": outreach or [],
        "total_materials": len(rows) if rows else 0,
        "total_outreach": len(outreach) if outreach else 0,
    }), 200


# ---------------------------------------------------------------------------
# POST /api/materials/regenerate/<id> — Regenerate a material
# ---------------------------------------------------------------------------

@bp.route("/api/materials/regenerate/<int:material_id>", methods=["POST"])
def regenerate_material(material_id):
    """Regenerate a material with updated context.

    Copies the original material, marks old as 'superseded', creates new as 'draft'.
    Body (JSON, optional):
        updates: dict of fields to override in the new version
    """
    original = db.query_one(
        "SELECT * FROM generated_materials WHERE id = %s",
        (material_id,),
    )
    if not original:
        return jsonify({"error": "Material not found"}), 404

    data = request.get_json(force=True) if request.data else {}
    updates = data.get("updates", {})

    # Mark original as superseded
    db.execute(
        "UPDATE generated_materials SET status = 'superseded' WHERE id = %s",
        (material_id,),
    )

    # Build new material from original + overrides
    new_content = updates.get("content", original.get("content", ""))
    new_type = updates.get("type", original.get("type"))

    row = db.execute_returning(
        """
        INSERT INTO generated_materials
            (type, application_id, content, content_format, status)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            new_type,
            original.get("application_id"),
            new_content,
            original.get("content_format", "text"),
            "draft",
        ),
    )
    return jsonify({
        "new_material": row,
        "superseded_id": material_id,
    }), 201
