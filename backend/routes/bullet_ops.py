"""Bullet operations: clone, reorder, stale-count, check-duplicates."""

import difflib
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("bullet_ops", __name__)


# ---------------------------------------------------------------------------
# POST /api/bullets/<id>/clone
# ---------------------------------------------------------------------------

@bp.route("/api/bullets/<int:bullet_id>/clone", methods=["POST"])
def clone_bullet(bullet_id):
    """Clone a bullet (copy with new ID, same job). Sets display_order to MAX+1."""
    original = db.query_one("SELECT * FROM bullets WHERE id = %s", (bullet_id,))
    if not original:
        return jsonify({"error": "Not found"}), 404

    # Get next display_order for this job
    max_order = db.query_one(
        "SELECT COALESCE(MAX(display_order), 0) AS mx FROM bullets WHERE career_history_id = %s",
        (original["career_history_id"],),
    )
    next_order = (max_order["mx"] or 0) + 1

    # Append " [COPY]" to text to avoid unique constraint on (career_history_id, type, md5(text))
    row = db.execute_returning(
        """
        INSERT INTO bullets (
            career_history_id, text, type, star_situation, star_task,
            star_action, star_result, metrics_json, tags, role_suitability,
            industry_suitability, detail_recall, source_file, display_order,
            content_hash, ai_analysis
        )
        SELECT
            career_history_id, text || ' [COPY]', type, star_situation, star_task,
            star_action, star_result, metrics_json, tags, role_suitability,
            industry_suitability, detail_recall, source_file, %s,
            content_hash, ai_analysis
        FROM bullets WHERE id = %s
        RETURNING *
        """,
        (next_order, bullet_id),
    )
    return jsonify(row), 201


# ---------------------------------------------------------------------------
# POST /api/bullets/reorder
# ---------------------------------------------------------------------------

@bp.route("/api/bullets/reorder", methods=["POST"])
def reorder_bullets():
    """Update display_order for bullets within a career_history_id.

    Body: {career_history_id: int, items: [{id: int, order: int}, ...]}
    """
    data = request.get_json(force=True)
    career_history_id = data.get("career_history_id")
    items = data.get("items", [])

    if not career_history_id or not items:
        return jsonify({"error": "career_history_id and items are required"}), 400

    updated = 0
    for item in items:
        count = db.execute(
            "UPDATE bullets SET display_order = %s WHERE id = %s AND career_history_id = %s",
            (item["order"], item["id"], career_history_id),
        )
        updated += count

    return jsonify({"updated": updated}), 200


# ---------------------------------------------------------------------------
# GET /api/bullets/stale-count
# ---------------------------------------------------------------------------

@bp.route("/api/bullets/stale-count", methods=["GET"])
def stale_count():
    """Count stale and never-analyzed bullets.

    Optional query param: ?career_history_id=N
    """
    career_history_id = request.args.get("career_history_id", type=int)

    scope_clause = ""
    params = []
    if career_history_id:
        scope_clause = "AND career_history_id = %s"
        params.append(career_history_id)

    stale = db.query_one(
        f"""
        SELECT COUNT(*) AS cnt FROM bullets
        WHERE ai_analysis IS NOT NULL
          AND content_hash IS DISTINCT FROM (ai_analysis->>'content_hash_at_analysis')
          {scope_clause}
        """,
        params,
    )

    never = db.query_one(
        f"""
        SELECT COUNT(*) AS cnt FROM bullets
        WHERE ai_analysis IS NULL AND text IS NOT NULL
          {scope_clause}
        """,
        params,
    )

    return jsonify({
        "stale": stale["cnt"] if stale else 0,
        "never_analyzed": never["cnt"] if never else 0,
    }), 200


# ---------------------------------------------------------------------------
# POST /api/bullets/<id>/check-duplicates
# ---------------------------------------------------------------------------

@bp.route("/api/bullets/<int:bullet_id>/check-duplicates", methods=["POST"])
def check_duplicates(bullet_id):
    """Find near-duplicate bullets using difflib.SequenceMatcher (ratio >= 0.7).

    Returns within_job and cross_job matches with similarity scores.
    """
    source = db.query_one(
        """
        SELECT b.id, b.text, b.career_history_id, ch.employer, ch.title
        FROM bullets b
        LEFT JOIN career_history ch ON ch.id = b.career_history_id
        WHERE b.id = %s
        """,
        (bullet_id,),
    )
    if not source:
        return jsonify({"error": "Not found"}), 404
    if not source.get("text"):
        return jsonify({"within_job": [], "cross_job": [], "has_duplicates": False}), 200

    # Get all other bullets
    others = db.query(
        """
        SELECT b.id, b.text, b.career_history_id, ch.employer, ch.title
        FROM bullets b
        LEFT JOIN career_history ch ON ch.id = b.career_history_id
        WHERE b.id != %s AND b.text IS NOT NULL
        """,
        (bullet_id,),
    )

    within_job = []
    cross_job = []
    source_text = source["text"].lower()

    for other in others:
        ratio = difflib.SequenceMatcher(None, source_text, other["text"].lower()).ratio()
        if ratio >= 0.7:
            match = {
                "id": other["id"],
                "text": other["text"][:120],
                "similarity": round(ratio, 3),
                "employer": other.get("employer"),
                "title": other.get("title"),
            }
            if other["career_history_id"] == source["career_history_id"]:
                within_job.append(match)
            else:
                cross_job.append(match)

    # Sort by similarity descending
    within_job.sort(key=lambda m: m["similarity"], reverse=True)
    cross_job.sort(key=lambda m: m["similarity"], reverse=True)

    return jsonify({
        "within_job": within_job,
        "cross_job": cross_job,
        "has_duplicates": bool(within_job or cross_job),
    }), 200
