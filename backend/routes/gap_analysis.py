"""Routes for gap_analyses (persisted gap analysis results)."""

import json
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("gap_analysis", __name__)


@bp.route("/api/gap-analyses", methods=["GET"])
def list_gap_analyses():
    """List gap analyses with optional filters."""
    application_id = request.args.get("application_id")
    saved_job_id = request.args.get("saved_job_id")
    recommendation = request.args.get("recommendation")
    min_score = request.args.get("min_score")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if application_id:
        clauses.append("g.application_id = %s")
        params.append(int(application_id))
    if saved_job_id:
        clauses.append("g.saved_job_id = %s")
        params.append(int(saved_job_id))
    if recommendation:
        clauses.append("g.recommendation = %s")
        params.append(recommendation)
    if min_score:
        clauses.append("g.overall_score >= %s")
        params.append(float(min_score))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT g.id, g.application_id, g.saved_job_id, g.overall_score,
               g.recommendation, g.notes, g.created_at, g.updated_at,
               a.company_name, a.role AS app_role,
               sj.title AS job_title, sj.company AS job_company
        FROM gap_analyses g
        LEFT JOIN applications a ON a.id = g.application_id
        LEFT JOIN saved_jobs sj ON sj.id = g.saved_job_id
        {where}
        ORDER BY g.created_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/gap-analyses/<int:gap_id>", methods=["GET"])
def get_gap_analysis(gap_id):
    """Single gap analysis with full details."""
    row = db.query_one(
        """
        SELECT g.*, a.company_name, a.role AS app_role,
               sj.title AS job_title, sj.company AS job_company
        FROM gap_analyses g
        LEFT JOIN applications a ON a.id = g.application_id
        LEFT JOIN saved_jobs sj ON sj.id = g.saved_job_id
        WHERE g.id = %s
        """,
        (gap_id,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/gap-analyses", methods=["POST"])
def create_gap_analysis():
    """Save a new gap analysis."""
    data = request.get_json(force=True)

    row = db.execute_returning(
        """
        INSERT INTO gap_analyses (application_id, saved_job_id, jd_text, jd_parsed,
            strong_matches, partial_matches, gaps, bonus_value,
            fit_scores, overall_score, recommendation, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data.get("application_id"), data.get("saved_job_id"),
            data.get("jd_text"),
            json.dumps(data["jd_parsed"]) if data.get("jd_parsed") else None,
            json.dumps(data["strong_matches"]) if data.get("strong_matches") else None,
            json.dumps(data["partial_matches"]) if data.get("partial_matches") else None,
            json.dumps(data["gaps"]) if data.get("gaps") else None,
            json.dumps(data["bonus_value"]) if data.get("bonus_value") else None,
            json.dumps(data["fit_scores"]) if data.get("fit_scores") else None,
            data.get("overall_score"),
            data.get("recommendation"),
            data.get("notes"),
        ),
    )

    # Link to application if provided
    if data.get("application_id"):
        db.execute(
            "UPDATE applications SET gap_analysis_id = %s WHERE id = %s",
            (row["id"], data["application_id"]),
        )

    return jsonify(row), 201


@bp.route("/api/gap-analyses/<int:gap_id>", methods=["PATCH"])
def update_gap_analysis(gap_id):
    """Update a gap analysis."""
    data = request.get_json(force=True)
    allowed = [
        "application_id", "saved_job_id", "jd_text", "jd_parsed",
        "strong_matches", "partial_matches", "gaps", "bonus_value",
        "fit_scores", "overall_score", "recommendation", "notes",
    ]
    json_fields = {"jd_parsed", "strong_matches", "partial_matches", "gaps",
                   "bonus_value", "fit_scores"}
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

    params.append(gap_id)
    row = db.execute_returning(
        f"UPDATE gap_analyses SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/gap-analyses/<int:gap_id>", methods=["DELETE"])
def delete_gap_analysis(gap_id):
    """Delete a gap analysis."""
    count = db.execute("DELETE FROM gap_analyses WHERE id = %s", (gap_id,))
    if count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": gap_id}), 200
