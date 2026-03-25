"""Bullet operations: clone, reorder, stale-count, check-duplicates, AI ops."""

import difflib
import hashlib
import json
import logging
from flask import Blueprint, request, jsonify, Response, stream_with_context
import db
from ai_providers.router import route_inference

logger = logging.getLogger(__name__)

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


# ===========================================================================
# AI-powered bullet operations
# ===========================================================================


def _analyze_single(bullet_id):
    """Analyze a single bullet. Returns (result_dict, error_string|None)."""
    row = db.query_one(
        """
        SELECT b.id, b.text, b.content_hash, b.tags,
               ch.employer, ch.title
        FROM bullets b
        LEFT JOIN career_history ch ON ch.id = b.career_history_id
        WHERE b.id = %s
        """,
        (bullet_id,),
    )
    if not row:
        return None, "not_found"
    if not row.get("text"):
        return None, "no_text"

    ai_ctx = {
        "bullet_text": row["text"],
        "employer": row.get("employer", ""),
        "title": row.get("title", ""),
        "tags": row.get("tags") or [],
        "instructions": (
            "Analyze this resume bullet. Return JSON with: "
            "strength (strong|moderate|weak), "
            "star_check (object with situation, task, action, result booleans), "
            "feedback (string with improvement suggestions), "
            "suggested_skills (array of skill strings detected)."
        ),
    }

    def _fallback(ctx):
        text = ctx.get("bullet_text", "")
        has_numbers = any(c.isdigit() for c in text)
        return {
            "strength": "moderate" if has_numbers else "weak",
            "star_check": None,
            "feedback": "Add metrics and quantifiable outcomes." if not has_numbers else "Consider strengthening with STAR format.",
            "suggested_skills": [],
        }

    def _ai_handler(ctx):
        from ai_providers import get_provider
        provider = get_provider()
        result = provider.generate_content("analyze_bullet", ctx)
        content = result.get("content", "")
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
            return parsed if isinstance(parsed, dict) else {"body": content}
        except (json.JSONDecodeError, TypeError):
            return {"body": content}

    gen_result = route_inference(
        task="analyze_bullet",
        context=ai_ctx,
        python_fallback=_fallback,
        ai_handler=_ai_handler,
    )

    # Persist analysis
    analysis = gen_result if isinstance(gen_result, dict) else {"body": str(gen_result)}
    analysis["content_hash_at_analysis"] = row.get("content_hash")
    db.execute(
        """
        UPDATE bullets
        SET ai_analysis = %s::jsonb, ai_analyzed_at = NOW()
        WHERE id = %s
        """,
        (json.dumps(analysis), bullet_id),
    )
    return analysis, None


# ---------------------------------------------------------------------------
# POST /api/bullets/<id>/analyze  — single bullet analysis
# ---------------------------------------------------------------------------

@bp.route("/api/bullets/<int:bullet_id>/analyze", methods=["POST"])
def analyze_bullet(bullet_id):
    """Analyze a single bullet for strength, STAR format, feedback, skills."""
    result, err = _analyze_single(bullet_id)
    if err == "not_found":
        return jsonify({"error": "Not found"}), 404
    if err == "no_text":
        return jsonify({"error": "Bullet has no text"}), 400
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# POST /api/bullets/analyze  — batch analysis via SSE
# ---------------------------------------------------------------------------

@bp.route("/api/bullets/analyze", methods=["POST"])
def analyze_bullets_batch():
    """Batch analyze bullets via SSE streaming."""
    data = request.get_json(force=True) or {}
    career_history_id = data.get("career_history_id")
    all_flag = data.get("all", False)

    if not career_history_id and not all_flag:
        return jsonify({"error": "Provide career_history_id or {all: true}"}), 400

    # Find stale or never-analyzed bullets
    scope_clause = ""
    params = []
    if career_history_id:
        scope_clause = "AND b.career_history_id = %s"
        params.append(career_history_id)

    bullets = db.query(
        f"""
        SELECT b.id FROM bullets b
        WHERE b.text IS NOT NULL
          AND (
            b.ai_analysis IS NULL
            OR b.content_hash IS DISTINCT FROM (b.ai_analysis->>'content_hash_at_analysis')
          )
          {scope_clause}
        ORDER BY b.id
        """,
        params,
    )

    total = len(bullets)

    def generate():
        yield f"data: {json.dumps({'type': 'start', 'total': total})}\n\n"
        completed = 0
        failed = 0
        for bullet in bullets:
            bid = bullet["id"]
            try:
                _analyze_single(bid)
                completed += 1
                status = "done"
            except Exception as exc:
                logger.warning("Batch analyze failed for bullet %s: %s", bid, exc)
                failed += 1
                status = "failed"
            yield f"data: {json.dumps({'type': 'progress', 'bullet_id': bid, 'status': status, 'completed': completed, 'total': total})}\n\n"
        yield f"data: {json.dumps({'type': 'complete', 'completed': completed, 'failed': failed, 'total': total})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


# ---------------------------------------------------------------------------
# POST /api/bullets/generate  — generate a new bullet from instruction
# ---------------------------------------------------------------------------

@bp.route("/api/bullets/generate", methods=["POST"])
def generate_bullet():
    """Generate a new bullet from instruction using AI."""
    data = request.get_json(force=True) or {}
    career_history_id = data.get("career_history_id")
    instruction = data.get("instruction", "")

    if not career_history_id or not instruction:
        return jsonify({"error": "career_history_id and instruction are required"}), 400

    job = db.query_one(
        "SELECT employer, title FROM career_history WHERE id = %s",
        (career_history_id,),
    )
    if not job:
        return jsonify({"error": "Career history not found"}), 404

    ai_ctx = {
        "employer": job.get("employer", ""),
        "title": job.get("title", ""),
        "instruction": instruction,
        "instructions": (
            "Generate ONE strong resume bullet starting with an action verb. "
            "Include a concrete metric or measurable outcome. "
            "Return JSON with a single key 'text' containing the bullet."
        ),
    }

    def _fallback(ctx):
        return {"error": "Cannot generate bullet without AI provider"}

    def _ai_handler(ctx):
        from ai_providers import get_provider
        provider = get_provider()
        result = provider.generate_content("generate_bullet", ctx)
        content = result.get("content", "")
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
            return parsed if isinstance(parsed, dict) else {"text": content}
        except (json.JSONDecodeError, TypeError):
            return {"text": content}

    gen_result = route_inference(
        task="generate_bullet",
        context=ai_ctx,
        python_fallback=_fallback,
        ai_handler=_ai_handler,
    )

    if gen_result.get("error"):
        return jsonify(gen_result), 503

    text = gen_result.get("text", gen_result.get("body", ""))
    if not text:
        return jsonify({"error": "AI returned empty result"}), 500

    content_hash = hashlib.md5(text.encode()).hexdigest()

    max_order = db.query_one(
        "SELECT COALESCE(MAX(display_order), 0) AS mx FROM bullets WHERE career_history_id = %s",
        (career_history_id,),
    )
    next_order = (max_order["mx"] or 0) + 1

    row = db.execute_returning(
        """
        INSERT INTO bullets (career_history_id, text, type, display_order, content_hash)
        VALUES (%s, %s, 'achievement', %s, %s)
        RETURNING *
        """,
        (career_history_id, text, next_order, content_hash),
    )
    return jsonify(row), 201


# ---------------------------------------------------------------------------
# POST /api/bullets/<id>/wordsmith  — polish a bullet
# ---------------------------------------------------------------------------

@bp.route("/api/bullets/<int:bullet_id>/wordsmith", methods=["POST"])
def wordsmith_bullet(bullet_id):
    """Polish a bullet's text using AI."""
    data = request.get_json(force=True) or {}
    instruction = data.get("instruction", "")

    bullet = db.query_one(
        """
        SELECT b.id, b.text, ch.employer, ch.title
        FROM bullets b
        LEFT JOIN career_history ch ON ch.id = b.career_history_id
        WHERE b.id = %s
        """,
        (bullet_id,),
    )
    if not bullet:
        return jsonify({"error": "Not found"}), 404

    original_text = bullet["text"] or ""

    ai_ctx = {
        "bullet_text": original_text,
        "employer": bullet.get("employer", ""),
        "title": bullet.get("title", ""),
        "instruction": instruction,
        "instructions": (
            "Improve this resume bullet. Keep the core meaning. "
            "Apply any user instruction. Return JSON with key 'text'."
        ),
    }

    def _fallback(ctx):
        return {"text": ctx.get("bullet_text", "")}

    def _ai_handler(ctx):
        from ai_providers import get_provider
        provider = get_provider()
        result = provider.generate_content("wordsmith_bullet", ctx)
        content = result.get("content", "")
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
            return parsed if isinstance(parsed, dict) else {"text": content}
        except (json.JSONDecodeError, TypeError):
            return {"text": content}

    gen_result = route_inference(
        task="wordsmith_bullet",
        context=ai_ctx,
        python_fallback=_fallback,
        ai_handler=_ai_handler,
    )

    updated_text = gen_result.get("text", gen_result.get("body", original_text))
    content_hash = hashlib.md5(updated_text.encode()).hexdigest()

    db.execute(
        "UPDATE bullets SET text = %s, content_hash = %s WHERE id = %s",
        (updated_text, content_hash, bullet_id),
    )

    return jsonify({
        "original": original_text,
        "updated": updated_text,
        "bullet_id": bullet_id,
    }), 200


# ---------------------------------------------------------------------------
# POST /api/bullets/<id>/variant  — generate a variant of existing bullet
# ---------------------------------------------------------------------------

@bp.route("/api/bullets/<int:bullet_id>/variant", methods=["POST"])
def variant_bullet(bullet_id):
    """Generate a variant of an existing bullet."""
    data = request.get_json(force=True) or {}
    instruction = data.get("instruction", "")

    if not instruction:
        return jsonify({"error": "instruction is required"}), 400

    bullet = db.query_one(
        """
        SELECT b.id, b.text, b.career_history_id, b.type, b.tags,
               ch.employer, ch.title
        FROM bullets b
        LEFT JOIN career_history ch ON ch.id = b.career_history_id
        WHERE b.id = %s
        """,
        (bullet_id,),
    )
    if not bullet:
        return jsonify({"error": "Not found"}), 404

    ai_ctx = {
        "bullet_text": bullet["text"] or "",
        "employer": bullet.get("employer", ""),
        "title": bullet.get("title", ""),
        "instruction": instruction,
        "instructions": (
            "Create an alternative version of this resume bullet per the instruction. "
            "Return JSON with key 'text'."
        ),
    }

    def _fallback(ctx):
        return {"text": ctx.get("bullet_text", "")}

    def _ai_handler(ctx):
        from ai_providers import get_provider
        provider = get_provider()
        result = provider.generate_content("variant_bullet", ctx)
        content = result.get("content", "")
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
            return parsed if isinstance(parsed, dict) else {"text": content}
        except (json.JSONDecodeError, TypeError):
            return {"text": content}

    gen_result = route_inference(
        task="variant_bullet",
        context=ai_ctx,
        python_fallback=_fallback,
        ai_handler=_ai_handler,
    )

    new_text = gen_result.get("text", gen_result.get("body", ""))
    if not new_text:
        return jsonify({"error": "AI returned empty result"}), 500

    content_hash = hashlib.md5(new_text.encode()).hexdigest()

    max_order = db.query_one(
        "SELECT COALESCE(MAX(display_order), 0) AS mx FROM bullets WHERE career_history_id = %s",
        (bullet["career_history_id"],),
    )
    next_order = (max_order["mx"] or 0) + 1

    row = db.execute_returning(
        """
        INSERT INTO bullets (career_history_id, text, type, tags, display_order, content_hash)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (bullet["career_history_id"], new_text, bullet.get("type", "achievement"),
         bullet.get("tags"), next_order, content_hash),
    )
    return jsonify(row), 201


# ---------------------------------------------------------------------------
# POST /api/bullets/<id>/strengthen  — strengthen a weak bullet
# ---------------------------------------------------------------------------

@bp.route("/api/bullets/<int:bullet_id>/strengthen", methods=["POST"])
def strengthen_bullet(bullet_id):
    """Strengthen a weak bullet using AI feedback."""
    data = request.get_json(force=True) or {}
    instruction = data.get("instruction", "")

    bullet = db.query_one(
        """
        SELECT b.id, b.text, b.ai_analysis, ch.employer, ch.title
        FROM bullets b
        LEFT JOIN career_history ch ON ch.id = b.career_history_id
        WHERE b.id = %s
        """,
        (bullet_id,),
    )
    if not bullet:
        return jsonify({"error": "Not found"}), 404

    original_text = bullet["text"] or ""

    # Include existing AI feedback if available
    existing_feedback = ""
    ai_analysis = bullet.get("ai_analysis")
    if ai_analysis:
        if isinstance(ai_analysis, str):
            try:
                ai_analysis = json.loads(ai_analysis)
            except (json.JSONDecodeError, TypeError):
                ai_analysis = {}
        existing_feedback = ai_analysis.get("feedback", "")

    ai_ctx = {
        "bullet_text": original_text,
        "employer": bullet.get("employer", ""),
        "title": bullet.get("title", ""),
        "instruction": instruction,
        "existing_feedback": existing_feedback,
        "instructions": (
            "Strengthen this resume bullet. Make it impactful with metrics. "
            "Consider the existing feedback if provided. "
            "Return JSON with key 'text'."
        ),
    }

    def _fallback(ctx):
        return {"text": ctx.get("bullet_text", "")}

    def _ai_handler(ctx):
        from ai_providers import get_provider
        provider = get_provider()
        result = provider.generate_content("strengthen_bullet", ctx)
        content = result.get("content", "")
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
            return parsed if isinstance(parsed, dict) else {"text": content}
        except (json.JSONDecodeError, TypeError):
            return {"text": content}

    gen_result = route_inference(
        task="strengthen_bullet",
        context=ai_ctx,
        python_fallback=_fallback,
        ai_handler=_ai_handler,
    )

    updated_text = gen_result.get("text", gen_result.get("body", original_text))
    content_hash = hashlib.md5(updated_text.encode()).hexdigest()

    db.execute(
        "UPDATE bullets SET text = %s, content_hash = %s WHERE id = %s",
        (updated_text, content_hash, bullet_id),
    )

    return jsonify({
        "original": original_text,
        "updated": updated_text,
        "bullet_id": bullet_id,
    }), 200


# ---------------------------------------------------------------------------
# POST /api/skills/sync-from-tags  — sync bullet tags to skills table
# ---------------------------------------------------------------------------

@bp.route("/api/skills/sync-from-tags", methods=["POST"])
def sync_skills_from_tags():
    """Scan bullet tags, create skill records for any not already in skills table."""
    # Get all distinct tags from bullets
    tag_rows = db.query(
        "SELECT DISTINCT UNNEST(tags) AS tag FROM bullets WHERE tags IS NOT NULL"
    )
    all_tags = {r["tag"].strip() for r in tag_rows if r.get("tag") and r["tag"].strip()}

    if not all_tags:
        return jsonify({"created": 0, "tags_found": 0, "new_skills": []}), 200

    # Get existing skill names (lowercase for comparison)
    existing_rows = db.query("SELECT DISTINCT LOWER(name) AS lname FROM skills")
    existing = {r["lname"] for r in existing_rows}

    new_skills = []
    for tag in sorted(all_tags):
        if tag.lower() not in existing:
            db.execute(
                "INSERT INTO skills (name, category) VALUES (%s, 'bullet_tag') ON CONFLICT DO NOTHING",
                (tag,),
            )
            new_skills.append(tag)
            existing.add(tag.lower())

    return jsonify({
        "tags_found": len(all_tags),
        "created": len(new_skills),
        "new_skills": new_skills,
    }), 200
