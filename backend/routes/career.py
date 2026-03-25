"""Routes for career_history, bullets, skills, summary_variants."""

import json
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


@bp.route("/api/career-history", methods=["POST"])
def create_career_history():
    """Add a new career history entry."""
    data = request.get_json(force=True)
    if not data.get("employer") or not data.get("title"):
        return jsonify({"error": "employer and title are required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO career_history (employer, title, start_date, end_date, location,
            industry, team_size, budget_usd, revenue_impact, is_current,
            linkedin_dates, intro_text, career_links, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data["employer"], data["title"], data.get("start_date"),
            data.get("end_date"), data.get("location"), data.get("industry"),
            data.get("team_size"), data.get("budget_usd"), data.get("revenue_impact"),
            data.get("is_current", False), data.get("linkedin_dates"),
            data.get("intro_text"),
            json.dumps(data["career_links"]) if data.get("career_links") else None,
            data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/career-history/<int:career_id>", methods=["PATCH"])
def update_career_history(career_id):
    """Update career history fields."""
    data = request.get_json(force=True)
    allowed = [
        "employer", "title", "start_date", "end_date", "location", "industry",
        "team_size", "budget_usd", "revenue_impact", "is_current",
        "linkedin_dates", "intro_text", "career_links", "notes",
        "metadata", "start_date_raw", "end_date_raw", "start_date_iso", "end_date_iso",
    ]
    sets, params = [], []
    for key in allowed:
        if key in data:
            if key == "career_links":
                sets.append(f"{key} = %s")
                params.append(json.dumps(data[key]) if data[key] else None)
            elif key == "metadata":
                sets.append(f"{key} = %s::jsonb")
                params.append(json.dumps(data[key]) if data[key] is not None else None)
            else:
                sets.append(f"{key} = %s")
                params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(career_id)
    row = db.execute_returning(
        f"UPDATE career_history SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/career-history/<int:career_id>", methods=["DELETE"])
def delete_career_history(career_id):
    """Delete a career history entry. Cascades to bullets."""
    count = db.execute("DELETE FROM career_history WHERE id = %s", (career_id,))
    if count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": career_id}), 200


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

    career_history_id = request.args.get("career_history_id", type=int)

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
    if career_history_id:
        clauses.append("b.career_history_id = %s")
        params.append(career_history_id)
    if bullet_type:
        if bullet_type.startswith("!"):
            clauses.append("b.type != %s")
            params.append(bullet_type[1:])
        else:
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
        ORDER BY b.display_order NULLS LAST, b.id
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


@bp.route("/api/bullets", methods=["POST"])
def create_bullet():
    """Add a new bullet."""
    data = request.get_json(force=True)
    if not data.get("text"):
        return jsonify({"error": "text is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO bullets (career_history_id, text, type, star_situation, star_task,
            star_action, star_result, metrics_json, tags, role_suitability,
            industry_suitability, detail_recall, source_file)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data.get("career_history_id"), data["text"], data.get("type", "core"),
            data.get("star_situation"), data.get("star_task"),
            data.get("star_action"), data.get("star_result"),
            json.dumps(data["metrics_json"]) if data.get("metrics_json") else None,
            data.get("tags"), data.get("role_suitability"),
            data.get("industry_suitability"), data.get("detail_recall", "high"),
            data.get("source_file"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/bullets/<int:bullet_id>", methods=["PATCH"])
def update_bullet(bullet_id):
    """Update bullet fields."""
    data = request.get_json(force=True)
    allowed = [
        "career_history_id", "text", "type", "star_situation", "star_task",
        "star_action", "star_result", "metrics_json", "tags",
        "role_suitability", "industry_suitability", "detail_recall", "source_file",
    ]
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            if key == "metrics_json":
                params.append(json.dumps(data[key]) if data[key] else None)
            else:
                params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(bullet_id)
    row = db.execute_returning(
        f"UPDATE bullets SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/bullets/<int:bullet_id>", methods=["DELETE"])
def delete_bullet(bullet_id):
    """Delete a bullet."""
    count = db.execute("DELETE FROM bullets WHERE id = %s", (bullet_id,))
    if count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": bullet_id}), 200


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


@bp.route("/api/summary-variants", methods=["POST"])
def create_summary_variant():
    """Add a new summary variant."""
    data = request.get_json(force=True)
    if not data.get("role_type") or not data.get("text"):
        return jsonify({"error": "role_type and text are required"}), 400

    row = db.execute_returning(
        "INSERT INTO summary_variants (role_type, text) VALUES (%s, %s) RETURNING *",
        (data["role_type"], data["text"]),
    )
    return jsonify(row), 201


@bp.route("/api/summary-variants/<int:variant_id>", methods=["PATCH"])
def update_summary_variant(variant_id):
    """Update a summary variant."""
    data = request.get_json(force=True)
    sets, params = [], []
    for key in ("role_type", "text"):
        if key in data:
            sets.append(f"{key} = %s")
            params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(variant_id)
    row = db.execute_returning(
        f"UPDATE summary_variants SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/summary-variants/<int:variant_id>", methods=["DELETE"])
def delete_summary_variant(variant_id):
    """Delete a summary variant."""
    count = db.execute("DELETE FROM summary_variants WHERE id = %s", (variant_id,))
    if count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": variant_id}), 200


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


@bp.route("/api/skills", methods=["POST"])
def create_skill():
    """Add a new skill."""
    data = request.get_json(force=True)
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO skills (name, category, proficiency, last_used_year, career_history_ids)
        VALUES (%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data["name"], data.get("category"), data.get("proficiency"),
            data.get("last_used_year"), data.get("career_history_ids"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/skills/<int:skill_id>", methods=["PATCH"])
def update_skill(skill_id):
    """Update a skill."""
    data = request.get_json(force=True)
    allowed = ["name", "category", "proficiency", "last_used_year", "career_history_ids"]
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(skill_id)
    row = db.execute_returning(
        f"UPDATE skills SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/skills/<int:skill_id>", methods=["DELETE"])
def delete_skill(skill_id):
    """Delete a skill."""
    count = db.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
    if count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": skill_id}), 200


# ---------------------------------------------------------------------------
# KB Export
# ---------------------------------------------------------------------------

@bp.route("/api/kb/export", methods=["GET"])
def export_kb():
    """Export all knowledge base data as JSON."""
    career = db.query("SELECT * FROM career_history ORDER BY start_date DESC NULLS LAST")
    bullets = db.query(
        """
        SELECT b.*, ch.employer FROM bullets b
        LEFT JOIN career_history ch ON ch.id = b.career_history_id
        ORDER BY b.career_history_id, b.id
        """
    )
    skills = db.query("SELECT * FROM skills ORDER BY category, name")
    summaries = db.query("SELECT * FROM summary_variants ORDER BY role_type")
    header = db.query_one("SELECT * FROM resume_header LIMIT 1")
    education = db.query("SELECT * FROM education ORDER BY sort_order")
    certifications = db.query(
        "SELECT * FROM certifications WHERE is_active = TRUE ORDER BY sort_order"
    )

    return jsonify({
        "career_history": career,
        "bullets": bullets,
        "skills": skills,
        "summary_variants": summaries,
        "resume_header": header,
        "education": education,
        "certifications": certifications,
        "counts": {
            "career_history": len(career),
            "bullets": len(bullets),
            "skills": len(skills),
            "summary_variants": len(summaries),
            "education": len(education),
            "certifications": len(certifications),
        },
    }), 200
