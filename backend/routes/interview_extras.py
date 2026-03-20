"""Routes for interview_prep and interview_debriefs."""

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
