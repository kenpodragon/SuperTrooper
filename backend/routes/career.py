"""Routes for career_history, bullets, skills, summary_variants."""

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("career", __name__)


# ---------------------------------------------------------------------------
# Career History
# ---------------------------------------------------------------------------

@bp.route("/api/career-history", methods=["GET"])
def list_career_history():
    """List all career history entries with optional filters."""
    industry = request.args.get("industry")
    is_current = request.args.get("is_current")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if industry:
        clauses.append("industry ILIKE %s")
        params.append(f"%{industry}%")
    if is_current is not None:
        clauses.append("is_current = %s")
        params.append(is_current.lower() == "true")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT id, employer, title, start_date, end_date, location, industry,
               team_size, budget_usd, revenue_impact, is_current, linkedin_dates,
               notes, created_at, updated_at
        FROM career_history
        {where}
        ORDER BY start_date DESC NULLS LAST
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/career-history/<int:career_id>", methods=["GET"])
def get_career_history(career_id):
    """Single employer with all bullets."""
    career = db.query_one(
        "SELECT * FROM career_history WHERE id = %s", (career_id,)
    )
    if not career:
        return jsonify({"error": "Not found"}), 404

    bullets = db.query(
        """
        SELECT id, text, type, star_situation, star_task, star_action, star_result,
               metrics_json, tags, role_suitability, industry_suitability,
               detail_recall, source_file, created_at
        FROM bullets
        WHERE career_history_id = %s
        ORDER BY id
        """,
        (career_id,),
    )
    career["bullets"] = bullets
    return jsonify(career), 200


# ---------------------------------------------------------------------------
# Bullets
# ---------------------------------------------------------------------------

@bp.route("/api/bullets", methods=["GET"])
def list_bullets():
    """Search bullets by tags, role_type, industry, text search."""
    text_q = request.args.get("q")
    tags = request.args.getlist("tags")
    role_type = request.args.get("role_type")
    industry = request.args.get("industry")
    bullet_type = request.args.get("type")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if text_q:
        clauses.append("b.text ILIKE %s")
        params.append(f"%{text_q}%")
    if tags:
        clauses.append("b.tags && %s")
        params.append(tags)
    if role_type:
        clauses.append("%s = ANY(b.role_suitability)")
        params.append(role_type)
    if industry:
        clauses.append("%s = ANY(b.industry_suitability)")
        params.append(industry)
    if bullet_type:
        clauses.append("b.type = %s")
        params.append(bullet_type)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT b.id, b.career_history_id, b.text, b.type,
               b.star_situation, b.star_task, b.star_action, b.star_result,
               b.metrics_json, b.tags, b.role_suitability, b.industry_suitability,
               b.detail_recall, b.source_file, b.created_at,
               ch.employer, ch.title
        FROM bullets b
        LEFT JOIN career_history ch ON ch.id = b.career_history_id
        {where}
        ORDER BY b.id
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/bullets/<int:bullet_id>", methods=["GET"])
def get_bullet(bullet_id):
    """Single bullet with employer context."""
    row = db.query_one(
        """
        SELECT b.*, ch.employer, ch.title
        FROM bullets b
        LEFT JOIN career_history ch ON ch.id = b.career_history_id
        WHERE b.id = %s
        """,
        (bullet_id,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Summary Variants
# ---------------------------------------------------------------------------

@bp.route("/api/summary-variants", methods=["GET"])
def list_summary_variants():
    """All summary variants."""
    rows = db.query(
        "SELECT id, role_type, text, updated_at FROM summary_variants ORDER BY role_type"
    )
    return jsonify(rows), 200


@bp.route("/api/summary-variants/<role_type>", methods=["GET"])
def get_summary_variant(role_type):
    """Single summary variant by role_type."""
    row = db.query_one(
        "SELECT id, role_type, text, updated_at FROM summary_variants WHERE role_type = %s",
        (role_type,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

@bp.route("/api/skills", methods=["GET"])
def list_skills():
    """All skills with optional category filter."""
    category = request.args.get("category")
    proficiency = request.args.get("proficiency")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if category:
        clauses.append("category = %s")
        params.append(category)
    if proficiency:
        clauses.append("proficiency = %s")
        params.append(proficiency)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT id, name, category, proficiency, last_used_year, career_history_ids, created_at
        FROM skills
        {where}
        ORDER BY category, name
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200
