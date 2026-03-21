"""MCP tool functions for Application Materials Generation.

These are standalone functions using `import db` for database access.
The orchestrator will integrate them into mcp_server.py.
"""

import json
import db


def generate_cover_letter(
    application_id: int | None = None,
    saved_job_id: int | None = None,
    company_name: str | None = None,
    role_title: str | None = None,
) -> dict:
    """Generate a cover letter for a job application.

    Pulls gap analysis, company dossier, and career bullets from the DB.
    Stores the result in generated_materials. Returns the material record.

    Args:
        application_id: optional application ID (pulls gap analysis automatically)
        saved_job_id: optional saved job ID for context
        company_name: optional company name override
        role_title: optional role title override
    """
    if not application_id and not saved_job_id:
        return {"error": "application_id or saved_job_id is required"}

    generation_context = {}

    # Look up application and gap analysis
    if application_id:
        app = db.query_one(
            "SELECT * FROM applications WHERE id = %s",
            (application_id,),
        )
        if app:
            company_name = company_name or app.get("company")
            role_title = role_title or app.get("role_title") or app.get("title")
            saved_job_id = saved_job_id or app.get("saved_job_id")
            generation_context["application_id"] = application_id

        gap = db.query_one(
            "SELECT * FROM gap_analyses WHERE application_id = %s ORDER BY created_at DESC LIMIT 1",
            (application_id,),
        )
        if gap:
            generation_context["gap_analysis_id"] = gap["id"]

    # Look up saved job
    if saved_job_id:
        job = db.query_one(
            "SELECT * FROM saved_jobs WHERE id = %s",
            (saved_job_id,),
        )
        if job:
            company_name = company_name or job.get("company")
            role_title = role_title or job.get("title")
            generation_context["saved_job_id"] = saved_job_id

    # Company dossier
    if company_name:
        dossier = db.query_one(
            "SELECT * FROM companies WHERE name ILIKE %s LIMIT 1",
            (company_name,),
        )
        if dossier:
            generation_context["company_id"] = dossier["id"]

    # Candidate profile
    profile = db.query_one(
        "SELECT * FROM candidate_profile ORDER BY id LIMIT 1"
    )
    candidate_name = profile["full_name"] if profile else "Candidate"
    generation_context["candidate_profile"] = True

    # Top career bullets
    bullets = db.query(
        "SELECT content FROM bullets ORDER BY impact_score DESC NULLS LAST LIMIT 5"
    )
    top_bullets = [b["content"] for b in bullets] if bullets else []
    generation_context["bullet_count"] = len(top_bullets)

    # Build placeholder cover letter with real data
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
            (material_type, application_id, saved_job_id, company_name, role_title,
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
    return {"material": row}


def generate_thank_you(
    application_id: int,
    interviewer_name: str | None = None,
    interview_notes: str | None = None,
) -> dict:
    """Generate a post-interview thank-you note (under 200 words).

    Pulls debrief data from the DB if available. Stores result in
    generated_materials. Returns the material record.

    Args:
        application_id: application ID (required)
        interviewer_name: optional name of interviewer
        interview_notes: optional notes from the interview
    """
    generation_context = {"application_id": application_id}

    # Look up application
    app = db.query_one(
        "SELECT * FROM applications WHERE id = %s",
        (application_id,),
    )
    company_name = app.get("company") if app else None
    role_title = app.get("role_title") or (app.get("title") if app else None)

    # Pull debrief
    debrief = db.query_one(
        "SELECT * FROM interview_debriefs WHERE application_id = %s ORDER BY created_at DESC LIMIT 1",
        (application_id,),
    )
    debrief_notes = None
    if debrief:
        generation_context["debrief_id"] = debrief["id"]
        debrief_notes = debrief.get("notes")

    if interview_notes:
        generation_context["interview_notes_provided"] = True
    if debrief_notes:
        generation_context["debrief_notes_provided"] = True

    # Candidate profile
    profile = db.query_one(
        "SELECT * FROM candidate_profile ORDER BY id LIMIT 1"
    )
    candidate_name = profile["full_name"] if profile else "Candidate"

    interviewer = interviewer_name or "the team"
    notes_ref = ""
    if interview_notes:
        notes_ref = f" Our discussion about {interview_notes[:80]}... was particularly engaging."
    elif debrief_notes:
        notes_ref = f" I especially valued our conversation about {debrief_notes[:80]}..."

    content = (
        f"Hi {interviewer},\n\n"
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
            (material_type, application_id, company_name, role_title,
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
    return {"material": row}


def generate_outreach(
    contact_id: int,
    message_type: str = "networking",
    channel: str = "email",
    application_id: int | None = None,
) -> dict:
    """Generate a personalized outreach message (under 150 words).

    Pulls contact and company context from the DB. Stores result in
    outreach_messages. Returns the message record.

    Args:
        contact_id: contact to reach out to (required)
        message_type: networking, cold_outreach, follow_up, recruiter (default: networking)
        channel: email, linkedin, phone (default: email)
        application_id: optional application for additional context
    """
    personalization_context = {}

    # Look up contact
    contact = db.query_one(
        "SELECT * FROM contacts WHERE id = %s",
        (contact_id,),
    )
    if not contact:
        return {"error": "Contact not found"}

    contact_name = contact.get("name") or contact.get("full_name") or "there"
    contact_company = contact.get("company")
    contact_title = contact.get("title")
    personalization_context["contact_name"] = contact_name
    if contact_company:
        personalization_context["contact_company"] = contact_company
    if contact_title:
        personalization_context["contact_title"] = contact_title

    # Company lookup
    if contact_company:
        company_info = db.query_one(
            "SELECT * FROM companies WHERE name ILIKE %s LIMIT 1",
            (contact_company,),
        )
        if company_info:
            personalization_context["company_id"] = company_info["id"]

    # Candidate profile
    profile = db.query_one(
        "SELECT * FROM candidate_profile ORDER BY id LIMIT 1"
    )
    candidate_name = profile["full_name"] if profile else "Candidate"

    # Application context
    role_context = ""
    if application_id:
        app = db.query_one(
            "SELECT * FROM applications WHERE id = %s",
            (application_id,),
        )
        if app:
            role_context = f" regarding the {app.get('role_title') or app.get('title', 'open')} role"
            personalization_context["application_id"] = application_id

    company_ref = f" at {contact_company}" if contact_company else ""
    subject = f"Connecting{role_context}" if channel == "email" else None

    body = (
        f"Hi {contact_name},\n\n"
        f"My name is {candidate_name}{role_context}. "
        f"I'd love to connect{company_ref}.\n\n"
        f"[AI will personalize with shared connections, mutual interests, "
        f"and a clear ask.]\n\n"
        f"Best,\n{candidate_name}"
    )

    row = db.execute_returning(
        """
        INSERT INTO outreach_messages
            (contact_id, application_id, message_type, channel, subject, body,
             personalization_context, voice_check_passed, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            contact_id,
            application_id,
            message_type,
            channel,
            subject,
            body,
            json.dumps(personalization_context),
            False,
            "draft",
        ),
    )
    return {"message": row}


def batch_outreach(
    contact_ids: list,
    message_type: str = "networking",
    application_id: int | None = None,
) -> dict:
    """Generate personalized outreach for multiple contacts.

    Creates one outreach message per contact. Returns list of created
    messages with count.

    Args:
        contact_ids: list of contact IDs to reach out to (required)
        message_type: networking, cold_outreach, follow_up, recruiter (default: networking)
        application_id: optional application for additional context
    """
    if not contact_ids:
        return {"error": "contact_ids is required"}

    # Candidate profile (pull once)
    profile = db.query_one(
        "SELECT * FROM candidate_profile ORDER BY id LIMIT 1"
    )
    candidate_name = profile["full_name"] if profile else "Candidate"

    # Application context
    role_context = ""
    if application_id:
        app = db.query_one(
            "SELECT * FROM applications WHERE id = %s",
            (application_id,),
        )
        if app:
            role_context = f" regarding the {app.get('role_title') or app.get('title', 'open')} role"

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
                (contact_id, application_id, message_type, channel, subject, body,
                 personalization_context, voice_check_passed, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                cid,
                application_id,
                message_type,
                "email",
                subject,
                body,
                json.dumps(personalization_context),
                False,
                "draft",
            ),
        )
        created.append(row)

    return {"count": len(created), "messages": created}
