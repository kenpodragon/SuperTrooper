"""Routes for interview_prep, interview_debriefs, and interview analytics."""

import json
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("interview_extras", __name__)


# ---------------------------------------------------------------------------
# Interview Prep
# ---------------------------------------------------------------------------

@bp.route("/api/interviews/<int:interview_id>/prep", methods=["GET"])
def get_interview_prep(interview_id):
    """Get prep materials for an interview."""
    row = db.query_one(
        "SELECT * FROM interview_prep WHERE interview_id = %s", (interview_id,)
    )
    if not row:
        return jsonify({"error": "No prep found for this interview"}), 404
    return jsonify(row), 200


@bp.route("/api/interviews/<int:interview_id>/prep", methods=["POST"])
def create_interview_prep(interview_id):
    """Create prep materials for an interview."""
    # Verify interview exists
    interview = db.query_one("SELECT id FROM interviews WHERE id = %s", (interview_id,))
    if not interview:
        return jsonify({"error": "Interview not found"}), 404

    data = request.get_json(force=True)
    row = db.execute_returning(
        """
        INSERT INTO interview_prep (interview_id, company_dossier, prepared_questions,
            talking_points, star_stories_selected, questions_to_ask, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            interview_id,
            json.dumps(data["company_dossier"]) if data.get("company_dossier") else None,
            json.dumps(data["prepared_questions"]) if data.get("prepared_questions") else None,
            json.dumps(data["talking_points"]) if data.get("talking_points") else None,
            json.dumps(data["star_stories_selected"]) if data.get("star_stories_selected") else None,
            json.dumps(data["questions_to_ask"]) if data.get("questions_to_ask") else None,
            data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/interview-prep/<int:prep_id>", methods=["PATCH"])
def update_interview_prep(prep_id):
    """Update interview prep materials."""
    data = request.get_json(force=True)
    allowed = [
        "company_dossier", "prepared_questions", "talking_points",
        "star_stories_selected", "questions_to_ask", "notes",
    ]
    json_fields = {"company_dossier", "prepared_questions", "talking_points",
                   "star_stories_selected", "questions_to_ask"}
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            if key in json_fields:
                params.append(json.dumps(data[key]) if data[key] else None)
            else:
                params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(prep_id)
    row = db.execute_returning(
        f"UPDATE interview_prep SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Interview Debriefs
# ---------------------------------------------------------------------------

@bp.route("/api/interviews/<int:interview_id>/debrief", methods=["GET"])
def get_interview_debrief(interview_id):
    """Get debrief for an interview."""
    row = db.query_one(
        "SELECT * FROM interview_debriefs WHERE interview_id = %s", (interview_id,)
    )
    if not row:
        return jsonify({"error": "No debrief found for this interview"}), 404
    return jsonify(row), 200


@bp.route("/api/interviews/<int:interview_id>/debrief", methods=["POST"])
def create_interview_debrief(interview_id):
    """Create a debrief for an interview."""
    interview = db.query_one("SELECT id FROM interviews WHERE id = %s", (interview_id,))
    if not interview:
        return jsonify({"error": "Interview not found"}), 404

    data = request.get_json(force=True)
    row = db.execute_returning(
        """
        INSERT INTO interview_debriefs (interview_id, went_well, went_poorly,
            questions_asked, next_steps, overall_feeling, lessons_learned, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            interview_id,
            json.dumps(data["went_well"]) if data.get("went_well") else None,
            json.dumps(data["went_poorly"]) if data.get("went_poorly") else None,
            json.dumps(data["questions_asked"]) if data.get("questions_asked") else None,
            data.get("next_steps"),
            data.get("overall_feeling"),
            data.get("lessons_learned"),
            data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/interview-debriefs/<int:debrief_id>", methods=["PATCH"])
def update_interview_debrief(debrief_id):
    """Update an interview debrief."""
    data = request.get_json(force=True)
    allowed = [
        "went_well", "went_poorly", "questions_asked",
        "next_steps", "overall_feeling", "lessons_learned", "notes",
    ]
    json_fields = {"went_well", "went_poorly", "questions_asked"}
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            if key in json_fields:
                params.append(json.dumps(data[key]) if data[key] else None)
            else:
                params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(debrief_id)
    row = db.execute_returning(
        f"UPDATE interview_debriefs SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Interview Analytics
# ---------------------------------------------------------------------------

@bp.route("/api/interviews/analytics", methods=["GET"])
def interview_analytics():
    """Cross-interview pattern analysis: win rates, question themes, prep effectiveness."""
    from mcp_tools_reporting import get_interview_analytics
    result = get_interview_analytics()
    return jsonify(result), 200


@bp.route("/api/interviews/<int:interview_id>/prep/generate", methods=["POST"])
def generate_interview_prep_package(interview_id):
    """Auto-generate a full interview prep package from application context.
    Pulls company dossier, STAR stories, mock questions, and suggested questions to ask.
    """
    # Verify interview exists
    interview = db.query_one(
        """
        SELECT i.*, a.role, a.company_name
        FROM interviews i
        LEFT JOIN applications a ON a.id = i.application_id
        WHERE i.id = %s
        """,
        (interview_id,),
    )
    if not interview:
        return jsonify({"error": "Interview not found"}), 404

    company_name = interview.get("company_name", "")
    role = interview.get("role", "")

    # Fetch company dossier
    company_info = {}
    if company_name:
        co = db.query_one(
            """
            SELECT name, sector, hq_location, size, stage, glassdoor_rating,
                   employee_count, funding_stage, key_differentiator, notes
            FROM companies WHERE name ILIKE %s
            """,
            (f"%{company_name}%",),
        )
        if co:
            company_info = co

    # Fetch contacts at company (warm intros / insiders)
    contacts = []
    if company_name:
        contacts = db.query(
            """
            SELECT name, title, relationship, relationship_strength, last_contact
            FROM contacts WHERE company ILIKE %s
            ORDER BY CASE relationship_strength WHEN 'strong' THEN 1 WHEN 'warm' THEN 2 ELSE 3 END
            LIMIT 5
            """,
            (f"%{company_name}%",),
        )

    # Fetch recent STAR bullets
    keyword = role.split()[0] if role else ""
    star_stories = db.query(
        """
        SELECT b.id, b.text, b.tags, ch.employer, ch.title
        FROM bullets b
        LEFT JOIN career_history ch ON ch.id = b.career_history_id
        WHERE b.type = 'achievement'
        ORDER BY b.id DESC LIMIT 6
        """
    ) if not keyword else db.query(
        """
        SELECT b.id, b.text, b.tags, ch.employer, ch.title
        FROM bullets b
        LEFT JOIN career_history ch ON ch.id = b.career_history_id
        WHERE b.type = 'achievement' AND (b.text ILIKE %s OR b.tags::text ILIKE %s)
        ORDER BY b.id DESC LIMIT 6
        """,
        (f"%{keyword}%", f"%{keyword}%"),
    )
    if not star_stories:
        star_stories = db.query(
            """
            SELECT b.id, b.text, b.tags, ch.employer, ch.title
            FROM bullets b
            LEFT JOIN career_history ch ON ch.id = b.career_history_id
            WHERE b.type = 'achievement'
            ORDER BY b.id DESC LIMIT 6
            """
        )

    # Fetch mock interview questions for this role
    mock_questions = []
    if role:
        mock_questions = db.query(
            """
            SELECT miq.question_text AS question, miq.question_type, mi.difficulty
            FROM mock_interview_questions miq
            JOIN mock_interviews mi ON mi.id = miq.mock_interview_id
            WHERE mi.job_title ILIKE %s
            ORDER BY miq.created_at DESC LIMIT 10
            """,
            (f"%{keyword}%",),
        )

    # Generate questions to ask
    questions_to_ask = [
        f"What does success look like in the first 90 days for this role?",
        f"How does the team handle disagreement on direction?",
        f"What are the biggest challenges the team is facing right now?",
        f"How do you measure performance for this position?",
        f"What's the career path from this role?",
    ]
    if company_name:
        questions_to_ask.insert(1, f"What's the culture like at {company_name} day-to-day?")

    # Recent email thread with this company (news talking points)
    recent_emails = []
    if company_name:
        recent_emails = db.query(
            """
            SELECT date, from_name, subject, snippet
            FROM emails
            WHERE subject ILIKE %s OR from_name ILIKE %s
            ORDER BY date DESC LIMIT 5
            """,
            (f"%{company_name}%", f"%{company_name}%"),
        )

    package = {
        "interview_id": interview_id,
        "role": role,
        "company_name": company_name,
        "interview_date": str(interview.get("date", "")),
        "interview_type": interview.get("type", ""),
        "company_dossier": company_info,
        "insider_contacts": contacts,
        "star_stories": star_stories,
        "mock_questions": mock_questions,
        "questions_to_ask": questions_to_ask,
        "recent_email_threads": recent_emails,
    }
    return jsonify(package), 200
