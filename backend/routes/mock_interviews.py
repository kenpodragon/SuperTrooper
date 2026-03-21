"""Routes for mock interview sessions and questions."""

from flask import Blueprint, request, jsonify
import db
from mcp_tools_mock_interviews import (
    create_mock_interview,
    get_mock_interview,
    evaluate_mock_interview,
    _generate_questions,
)

bp = Blueprint("mock_interviews", __name__)


@bp.route("/api/mock-interviews", methods=["GET"])
def list_mock_interviews():
    """List mock interviews with optional filters."""
    status = request.args.get("status")
    interview_type = request.args.get("interview_type")
    application_id = request.args.get("application_id")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if interview_type:
        clauses.append("interview_type = %s")
        params.append(interview_type)
    if application_id:
        clauses.append("application_id = %s")
        params.append(int(application_id))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT *
        FROM mock_interviews
        {where}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/mock-interviews/<int:interview_id>", methods=["GET"])
def get_interview(interview_id):
    """Get a single mock interview with all questions."""
    result = get_mock_interview(interview_id)
    if result is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(result), 200


@bp.route("/api/mock-interviews", methods=["POST"])
def create_interview():
    """Create a new mock interview session."""
    data = request.get_json(force=True)
    if not data.get("job_title"):
        return jsonify({"error": "job_title is required"}), 400
    if not data.get("company"):
        return jsonify({"error": "company is required"}), 400

    result = create_mock_interview(
        job_title=data["job_title"],
        company=data["company"],
        interview_type=data.get("interview_type", "behavioral"),
        difficulty=data.get("difficulty", "medium"),
        application_id=data.get("application_id"),
    )
    return jsonify(result), 201


@bp.route("/api/mock-interviews/<int:interview_id>/questions", methods=["POST"])
def generate_questions(interview_id):
    """Generate additional questions for an interview."""
    interview = db.query_one(
        "SELECT * FROM mock_interviews WHERE id = %s", (interview_id,)
    )
    if not interview:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(force=True) or {}
    count = int(data.get("count", 5))

    # Mark as in_progress when questions are being added
    db.execute(
        "UPDATE mock_interviews SET status = 'in_progress', started_at = COALESCE(started_at, NOW()) WHERE id = %s",
        (interview_id,),
    )

    # Find the current max question number
    max_q = db.query_one(
        "SELECT COALESCE(MAX(question_number), 0) AS max_num FROM mock_interview_questions WHERE mock_interview_id = %s",
        (interview_id,),
    )
    start_num = (max_q["max_num"] if max_q else 0) + 1

    questions = _generate_questions(
        interview_type=interview["interview_type"],
        difficulty=interview.get("difficulty", "medium"),
        count=count,
        start_number=start_num,
        interview_id=interview_id,
    )
    return jsonify({"questions": questions, "count": len(questions)}), 201


@bp.route("/api/mock-interviews/<int:interview_id>/answer", methods=["PUT"])
def submit_answer(interview_id):
    """Submit an answer for a specific question."""
    interview = db.query_one(
        "SELECT id FROM mock_interviews WHERE id = %s", (interview_id,)
    )
    if not interview:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(force=True)
    question_id = data.get("question_id")
    user_answer = data.get("user_answer")
    if not question_id:
        return jsonify({"error": "question_id is required"}), 400
    if not user_answer:
        return jsonify({"error": "user_answer is required"}), 400

    updated = db.execute_returning(
        """
        UPDATE mock_interview_questions
        SET user_answer = %s
        WHERE id = %s AND mock_interview_id = %s
        RETURNING *
        """,
        (user_answer, question_id, interview_id),
    )
    if not updated:
        return jsonify({"error": "Question not found for this interview"}), 404

    # Ensure interview is in_progress
    db.execute(
        "UPDATE mock_interviews SET status = 'in_progress', started_at = COALESCE(started_at, NOW()) WHERE id = %s AND status = 'pending'",
        (interview_id,),
    )

    return jsonify(updated), 200


@bp.route("/api/mock-interviews/<int:interview_id>/evaluate", methods=["PUT"])
def evaluate_interview(interview_id):
    """Evaluate all answers and score the interview."""
    interview = db.query_one(
        "SELECT id FROM mock_interviews WHERE id = %s", (interview_id,)
    )
    if not interview:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(force=True) or {}
    answers = data.get("answers", {})  # {question_id: answer_text} — optional overrides

    result = evaluate_mock_interview(interview_id, answers)
    return jsonify(result), 200


@bp.route("/api/mock-interviews/<int:interview_id>", methods=["DELETE"])
def delete_interview(interview_id):
    """Soft delete — set status to archived."""
    updated = db.execute_returning(
        "UPDATE mock_interviews SET status = 'archived' WHERE id = %s RETURNING id",
        (interview_id,),
    )
    if not updated:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"archived": interview_id}), 200
