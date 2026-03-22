"""Routes for LinkedIn data import — connections, messages, applications, profile."""

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("linkedin_import", __name__)


@bp.route("/api/import/linkedin-connections", methods=["POST"])
def import_connections():
    """Import LinkedIn connections as contacts."""
    data = request.get_json(force=True)
    connections = data.get("connections", [])
    if not connections:
        return jsonify({"error": "connections array is required"}), 400

    imported = 0
    skipped = 0
    companies_linked = 0

    for conn in connections:
        name = conn.get("name", "").strip()
        company = conn.get("company", "").strip()
        title = conn.get("title", "").strip()
        connected_on = conn.get("connected_on")

        if not name:
            continue

        # Check for duplicate by name + company
        existing = db.query_one(
            "SELECT id FROM contacts WHERE name ILIKE %s AND company ILIKE %s",
            (name, company if company else ""),
        )
        if existing:
            skipped += 1
            continue

        # Try to link to existing company
        company_id = None
        if company:
            co = db.query_one(
                "SELECT id FROM companies WHERE name ILIKE %s", (company,)
            )
            if co:
                company_id = co["id"]
                companies_linked += 1

        db.execute_returning(
            """
            INSERT INTO contacts (name, company, company_id, title, source, last_contact)
            VALUES (%s, %s, %s, %s, 'linkedin', %s)
            RETURNING id
            """,
            (name, company, company_id, title, connected_on),
        )
        imported += 1

    return jsonify({
        "imported": imported,
        "skipped_duplicates": skipped,
        "companies_linked": companies_linked,
    }), 200


@bp.route("/api/import/linkedin-messages", methods=["POST"])
def import_messages():
    """Import LinkedIn messages as outreach records."""
    data = request.get_json(force=True)
    messages = data.get("messages", [])
    candidate_name = data.get("candidate_name", "Stephen Salaka")
    if not messages:
        return jsonify({"error": "messages array is required"}), 400

    imported = 0
    linked = 0

    for msg in messages:
        from_name = msg.get("from_name", "").strip()
        to_name = msg.get("to_name", "").strip()
        date_val = msg.get("date")
        content = msg.get("content", "")

        # Determine direction
        direction = "sent" if from_name.lower() == candidate_name.lower() else "received"

        # Try to link to a contact
        other_name = to_name if direction == "sent" else from_name
        contact = db.query_one(
            "SELECT id FROM contacts WHERE name ILIKE %s", (other_name,)
        ) if other_name else None

        contact_id = contact["id"] if contact else None
        if contact_id:
            linked += 1

        db.execute_returning(
            """
            INSERT INTO outreach_messages (contact_id, channel, direction, subject, body, status, created_at)
            VALUES (%s, 'linkedin', %s, %s, %s, 'delivered', COALESCE(%s::timestamp, NOW()))
            RETURNING id
            """,
            (contact_id, direction, f"LinkedIn message with {other_name}", content, date_val),
        )
        imported += 1

    return jsonify({
        "imported": imported,
        "linked_to_contacts": linked,
    }), 200


@bp.route("/api/import/linkedin-applications", methods=["POST"])
def import_applications():
    """Import LinkedIn Easy Apply history."""
    data = request.get_json(force=True)
    applications = data.get("applications", [])
    if not applications:
        return jsonify({"error": "applications array is required"}), 400

    imported = 0
    skipped = 0

    for app in applications:
        company = app.get("company", "").strip()
        role = app.get("role", "").strip()
        date_applied = app.get("date_applied")
        status = app.get("status", "applied")

        if not company or not role:
            continue

        # Deduplicate by company + role
        existing = db.query_one(
            "SELECT id FROM applications WHERE company_name ILIKE %s AND role ILIKE %s",
            (company, role),
        )
        if existing:
            skipped += 1
            continue

        db.execute_returning(
            """
            INSERT INTO applications (company_name, role, source, status, date_applied)
            VALUES (%s, %s, 'linkedin', %s, %s)
            RETURNING id
            """,
            (company, role, status, date_applied),
        )
        imported += 1

    return jsonify({
        "imported": imported,
        "skipped_duplicates": skipped,
    }), 200


@bp.route("/api/import/linkedin-profile", methods=["POST"])
def import_profile():
    """Extract career history and skills from LinkedIn profile data."""
    data = request.get_json(force=True)
    positions = data.get("positions", [])
    skills_list = data.get("skills", [])

    positions_added = 0
    bullets_extracted = 0
    skills_added = 0

    # Import positions
    for pos in positions:
        title = pos.get("title", "").strip()
        company = pos.get("company", "").strip()
        start_date = pos.get("start_date")
        end_date = pos.get("end_date")
        # Normalize partial dates: "2010-01" -> "2010-01-01"
        if start_date and len(start_date) == 7:
            start_date = start_date + "-01"
        if end_date and len(end_date) == 7:
            end_date = end_date + "-01"
        description = pos.get("description", "")

        if not title or not company:
            continue

        # Check for existing career_history entry
        existing = db.query_one(
            "SELECT id FROM career_history WHERE employer ILIKE %s AND title ILIKE %s",
            (company, title),
        )
        if existing:
            continue

        ch = db.execute_returning(
            """
            INSERT INTO career_history (employer, title, start_date, end_date)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (company, title, start_date, end_date),
        )
        positions_added += 1

        # Extract bullets from description
        if description and ch:
            lines = [
                line.strip().lstrip("-").lstrip("*").lstrip("•").strip()
                for line in description.split("\n")
                if line.strip() and len(line.strip()) > 10
            ]
            for line in lines:
                db.execute_returning(
                    """
                    INSERT INTO bullets (career_history_id, text, type)
                    VALUES (%s, %s, 'achievement')
                    RETURNING id
                    """,
                    (ch["id"], line),
                )
                bullets_extracted += 1

    # Import skills
    for skill_name in skills_list:
        skill_name = skill_name.strip()
        if not skill_name:
            continue
        existing = db.query_one(
            "SELECT id FROM skills WHERE name ILIKE %s", (skill_name,)
        )
        if existing:
            continue
        db.execute_returning(
            """
            INSERT INTO skills (name, category, proficiency)
            VALUES (%s, 'linkedin_import', 'intermediate')
            RETURNING id
            """,
            (skill_name,),
        )
        skills_added += 1

    return jsonify({
        "positions_added": positions_added,
        "bullets_extracted": bullets_extracted,
        "skills_added": skills_added,
    }), 200
