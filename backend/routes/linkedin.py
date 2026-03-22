"""Routes for LinkedIn Profile & Brand Management."""

import json
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("linkedin", __name__)


# ---------------------------------------------------------------------------
# Profile Audits (S11.1)
# ---------------------------------------------------------------------------

@bp.route("/api/linkedin/profile-audits", methods=["GET"])
def list_profile_audits():
    """List profile audits with pagination.

    Query params:
        limit: max results (default 20)
        offset: pagination offset (default 0)
    """
    limit = int(request.args.get("limit", 20))
    offset = int(request.args.get("offset", 0))
    rows = db.query(
        """
        SELECT * FROM linkedin_profile_audits
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/linkedin/profile-audits/latest", methods=["GET"])
def latest_profile_audit():
    """Get the most recent profile audit."""
    row = db.query_one(
        "SELECT * FROM linkedin_profile_audits ORDER BY created_at DESC LIMIT 1"
    )
    if not row:
        return jsonify({"error": "No audits found"}), 404
    return jsonify(row), 200


@bp.route("/api/linkedin/profile-audits/<int:audit_id>", methods=["GET"])
def get_profile_audit(audit_id):
    """Get a single profile audit by ID."""
    row = db.query_one(
        "SELECT * FROM linkedin_profile_audits WHERE id = %s",
        (audit_id,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/linkedin/profile-audits", methods=["POST"])
def create_profile_audit():
    """Create a new profile audit.

    Body (JSON):
        audit_type: full, headline, about, experience, skills, featured (default: full)
        target_jd_ids: optional list of saved_job IDs for match scoring
    """
    data = request.get_json(force=True)
    audit_type = data.get("audit_type", "full")
    target_jd_ids = data.get("target_jd_ids")

    row = db.execute_returning(
        """
        INSERT INTO linkedin_profile_audits
            (audit_type, target_jd_ids)
        VALUES (%s, %s)
        RETURNING *
        """,
        (audit_type, json.dumps(target_jd_ids) if target_jd_ids else None),
    )
    return jsonify(row), 201


# ---------------------------------------------------------------------------
# Posts (S11.2)
# ---------------------------------------------------------------------------

@bp.route("/api/linkedin/posts", methods=["GET"])
def list_posts():
    """List posts with optional filters.

    Query params:
        status: draft, published, scheduled, archived
        theme_pillar_id: filter by theme pillar
        limit: max results (default 20)
        offset: pagination offset (default 0)
    """
    status = request.args.get("status")
    theme_pillar_id = request.args.get("theme_pillar_id")
    limit = int(request.args.get("limit", 20))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if theme_pillar_id:
        clauses.append("theme_pillar_id = %s")
        params.append(int(theme_pillar_id))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT * FROM linkedin_posts
        {where}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/linkedin/posts/<int:post_id>", methods=["GET"])
def get_post(post_id):
    """Get a single post by ID with engagement data."""
    post = db.query_one(
        "SELECT * FROM linkedin_posts WHERE id = %s",
        (post_id,),
    )
    if not post:
        return jsonify({"error": "Not found"}), 404

    engagement = db.query(
        """
        SELECT * FROM linkedin_post_engagement
        WHERE post_id = %s
        ORDER BY snapshot_day
        """,
        (post_id,),
    )
    post["engagement"] = engagement
    return jsonify(post), 200


@bp.route("/api/linkedin/posts", methods=["POST"])
def create_post():
    """Create a new LinkedIn post draft.

    Body (JSON):
        content (required): post text
        post_type: text, article, poll, carousel, video, document (default: text)
        theme_pillar_id: optional theme pillar ID
        hashtags: optional list of hashtag strings
        hook_text: optional first ~210 chars
    """
    data = request.get_json(force=True)
    if not data.get("content"):
        return jsonify({"error": "content is required"}), 400

    content = data["content"]
    char_count = len(content)
    hook_text = data.get("hook_text") or content[:210]

    row = db.execute_returning(
        """
        INSERT INTO linkedin_posts
            (content, post_type, theme_pillar_id, hashtags, hook_text, char_count)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            content,
            data.get("post_type", "text"),
            data.get("theme_pillar_id"),
            json.dumps(data.get("hashtags")) if data.get("hashtags") else None,
            hook_text,
            char_count,
        ),
    )
    return jsonify(row), 201


@bp.route("/api/linkedin/posts/<int:post_id>", methods=["PUT", "PATCH"])
def update_post(post_id):
    """Update an existing post.

    Body (JSON): any subset of post fields to update.
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    allowed = ["content", "post_type", "theme_pillar_id", "status",
               "hashtags", "hook_text", "linkedin_url"]
    sets, params = [], []
    for field in allowed:
        if field in data:
            val = data[field]
            if field == "hashtags" and val is not None:
                val = json.dumps(val)
            sets.append(f"{field} = %s")
            params.append(val)

    # Recalculate char_count if content changed
    if "content" in data:
        sets.append("char_count = %s")
        params.append(len(data["content"]))
        if "hook_text" not in data:
            sets.append("hook_text = %s")
            params.append(data["content"][:210])

    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(post_id)
    row = db.execute_returning(
        f"""
        UPDATE linkedin_posts
        SET {', '.join(sets)}
        WHERE id = %s
        RETURNING *
        """,
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/linkedin/posts/<int:post_id>", methods=["DELETE"])
def delete_post(post_id):
    """Soft-delete a post by setting status to archived."""
    row = db.execute_returning(
        """
        UPDATE linkedin_posts
        SET status = 'archived'
        WHERE id = %s
        RETURNING id, status
        """,
        (post_id,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/linkedin/posts/<int:post_id>/publish", methods=["POST"])
def publish_post(post_id):
    """Mark a post as published.

    Body (JSON):
        linkedin_url: optional URL of published post
    """
    data = request.get_json(silent=True) or {}
    row = db.execute_returning(
        """
        UPDATE linkedin_posts
        SET status = 'published', published_at = NOW(), linkedin_url = COALESCE(%s, linkedin_url)
        WHERE id = %s
        RETURNING *
        """,
        (data.get("linkedin_url"), post_id),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/linkedin/posts/<int:post_id>/schedule", methods=["POST"])
def schedule_post(post_id):
    """Schedule a post for a specific date/time.

    Body (JSON):
        scheduled_for (required): ISO 8601 datetime string, e.g. "2026-03-25T09:00:00"

    Sets status to 'scheduled' and records the scheduled_for timestamp.
    Returns 400 if the post is already published or archived.
    """
    data = request.get_json(force=True)
    scheduled_for = data.get("scheduled_for")
    if not scheduled_for:
        return jsonify({"error": "scheduled_for is required (ISO 8601 datetime)"}), 400

    # Verify post exists and is in a schedulable state
    post = db.query_one("SELECT id, status FROM linkedin_posts WHERE id = %s", (post_id,))
    if not post:
        return jsonify({"error": "Post not found"}), 404
    if post["status"] in ("published", "archived"):
        return jsonify({
            "error": f"Cannot schedule a post with status '{post['status']}'. Only draft or scheduled posts can be rescheduled."
        }), 400

    row = db.execute_returning(
        """
        UPDATE linkedin_posts
        SET status = 'scheduled', scheduled_for = %s
        WHERE id = %s
        RETURNING *
        """,
        (scheduled_for, post_id),
    )
    return jsonify(row), 200


@bp.route("/api/linkedin/posts/calendar", methods=["GET"])
def content_calendar():
    """Content calendar: scheduled and recently published posts.

    Query params:
        days_ahead: how many days forward to show scheduled posts (default 30)
        days_back: how many days back to show published posts (default 7)

    Returns scheduled posts grouped by date + recently published for context.
    """
    days_ahead = int(request.args.get("days_ahead", 30))
    days_back = int(request.args.get("days_back", 7))

    scheduled = db.query(
        """
        SELECT p.id, p.hook_text, p.post_type, p.status,
               p.scheduled_for, p.theme_pillar_id, tp.name AS theme_pillar_name
        FROM linkedin_posts p
        LEFT JOIN linkedin_theme_pillars tp ON tp.id = p.theme_pillar_id
        WHERE p.status = 'scheduled'
          AND p.scheduled_for BETWEEN NOW() AND NOW() + INTERVAL '1 day' * %s
        ORDER BY p.scheduled_for ASC
        """,
        (days_ahead,),
    )

    recently_published = db.query(
        """
        SELECT p.id, p.hook_text, p.post_type, p.status,
               p.published_at, p.theme_pillar_id, tp.name AS theme_pillar_name,
               e.engagement_rate, e.impressions
        FROM linkedin_posts p
        LEFT JOIN linkedin_theme_pillars tp ON tp.id = p.theme_pillar_id
        LEFT JOIN linkedin_post_engagement e ON e.post_id = p.id AND e.snapshot_day = 7
        WHERE p.status = 'published'
          AND p.published_at >= NOW() - INTERVAL '1 day' * %s
        ORDER BY p.published_at DESC
        """,
        (days_back,),
    )

    drafts_count = db.query_one(
        "SELECT COUNT(*) AS cnt FROM linkedin_posts WHERE status = 'draft'"
    )

    return jsonify({
        "scheduled": scheduled,
        "scheduled_count": len(scheduled),
        "recently_published": recently_published,
        "drafts_available": drafts_count["cnt"] if drafts_count else 0,
        "window": {"days_ahead": days_ahead, "days_back": days_back},
    }), 200


@bp.route("/api/linkedin/posts/import", methods=["POST"])
def import_posts():
    """Bulk import posts.

    Body (JSON): array of post objects, each with at least 'content'.
    """
    data = request.get_json(force=True)
    if not isinstance(data, list):
        return jsonify({"error": "Expected an array of post objects"}), 400

    created = []
    for item in data:
        if not item.get("content"):
            continue
        content = item["content"]
        row = db.execute_returning(
            """
            INSERT INTO linkedin_posts
                (content, post_type, theme_pillar_id, status, hashtags,
                 hook_text, char_count, published_at, linkedin_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                content,
                item.get("post_type", "text"),
                item.get("theme_pillar_id"),
                item.get("status", "draft"),
                json.dumps(item.get("hashtags")) if item.get("hashtags") else None,
                item.get("hook_text") or content[:210],
                len(content),
                item.get("published_at"),
                item.get("linkedin_url"),
            ),
        )
        created.append(row)
    return jsonify({"imported": len(created), "posts": created}), 201


# ---------------------------------------------------------------------------
# Post Engagement (S11.2)
# ---------------------------------------------------------------------------

@bp.route("/api/linkedin/posts/<int:post_id>/engagement", methods=["POST"])
def log_engagement(post_id):
    """Log an engagement snapshot for a post.

    Body (JSON):
        snapshot_day (required): 1, 3, or 7
        impressions: int
        reactions: int
        comments: int
        reposts: int
    """
    data = request.get_json(force=True)
    if "snapshot_day" not in data:
        return jsonify({"error": "snapshot_day is required"}), 400

    impressions = data.get("impressions", 0)
    reactions = data.get("reactions", 0)
    comments = data.get("comments", 0)
    reposts = data.get("reposts", 0)
    engagement_rate = (
        (reactions + comments + reposts) / impressions if impressions > 0 else 0.0
    )

    row = db.execute_returning(
        """
        INSERT INTO linkedin_post_engagement
            (post_id, snapshot_day, impressions, reactions, comments, reposts, engagement_rate)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (post_id, snapshot_day)
        DO UPDATE SET impressions = EXCLUDED.impressions,
                      reactions = EXCLUDED.reactions,
                      comments = EXCLUDED.comments,
                      reposts = EXCLUDED.reposts,
                      engagement_rate = EXCLUDED.engagement_rate,
                      captured_at = NOW()
        RETURNING *
        """,
        (post_id, data["snapshot_day"], impressions, reactions, comments, reposts, engagement_rate),
    )
    return jsonify(row), 201


@bp.route("/api/linkedin/posts/<int:post_id>/engagement", methods=["GET"])
def get_engagement(post_id):
    """Get all engagement snapshots for a post."""
    rows = db.query(
        """
        SELECT * FROM linkedin_post_engagement
        WHERE post_id = %s
        ORDER BY snapshot_day
        """,
        (post_id,),
    )
    return jsonify(rows), 200


@bp.route("/api/linkedin/analytics/content", methods=["GET"])
def content_analytics():
    """Content performance analytics.

    Query params:
        days: lookback window (default 30)

    Returns aggregated stats, best post types, best themes, posting time analysis.
    """
    days = int(request.args.get("days", 30))

    # Overall stats
    overall = db.query_one(
        """
        SELECT
            COUNT(*) AS total_posts,
            COUNT(*) FILTER (WHERE status = 'published') AS published,
            COUNT(*) FILTER (WHERE status = 'draft') AS drafts,
            AVG(char_count) AS avg_char_count
        FROM linkedin_posts
        WHERE created_at >= NOW() - INTERVAL '1 day' * %s
        """,
        (days,),
    )

    # Best post types by avg engagement
    by_type = db.query(
        """
        SELECT p.post_type,
               COUNT(DISTINCT p.id) AS post_count,
               AVG(e.engagement_rate) AS avg_engagement_rate,
               SUM(e.impressions) AS total_impressions
        FROM linkedin_posts p
        LEFT JOIN linkedin_post_engagement e ON e.post_id = p.id
        WHERE p.created_at >= NOW() - INTERVAL '1 day' * %s
        GROUP BY p.post_type
        ORDER BY avg_engagement_rate DESC NULLS LAST
        """,
        (days,),
    )

    # Best themes by avg engagement
    by_theme = db.query(
        """
        SELECT tp.id, tp.name,
               COUNT(DISTINCT p.id) AS post_count,
               AVG(e.engagement_rate) AS avg_engagement_rate,
               SUM(e.impressions) AS total_impressions
        FROM linkedin_posts p
        JOIN linkedin_theme_pillars tp ON tp.id = p.theme_pillar_id
        LEFT JOIN linkedin_post_engagement e ON e.post_id = p.id
        WHERE p.created_at >= NOW() - INTERVAL '1 day' * %s
        GROUP BY tp.id, tp.name
        ORDER BY avg_engagement_rate DESC NULLS LAST
        """,
        (days,),
    )

    # Top 5 posts by engagement
    top_posts = db.query(
        """
        SELECT p.id, p.hook_text, p.post_type, p.published_at,
               e.impressions, e.reactions, e.comments, e.reposts, e.engagement_rate
        FROM linkedin_posts p
        JOIN linkedin_post_engagement e ON e.post_id = p.id AND e.snapshot_day = 7
        WHERE p.created_at >= NOW() - INTERVAL '1 day' * %s
        ORDER BY e.engagement_rate DESC NULLS LAST
        LIMIT 5
        """,
        (days,),
    )

    return jsonify({
        "days": days,
        "overall": overall,
        "by_type": by_type,
        "by_theme": by_theme,
        "top_posts": top_posts,
    }), 200


# ---------------------------------------------------------------------------
# Theme Pillars (S11.2)
# ---------------------------------------------------------------------------

@bp.route("/api/linkedin/theme-pillars", methods=["GET"])
def list_theme_pillars():
    """List all theme pillars."""
    rows = db.query(
        "SELECT * FROM linkedin_theme_pillars ORDER BY sort_order, name"
    )
    return jsonify(rows), 200


@bp.route("/api/linkedin/theme-pillars", methods=["POST"])
def create_theme_pillar():
    """Create a new theme pillar.

    Body (JSON):
        name (required): pillar name
        description: optional description
        target_role_types: optional list
        keywords: optional list
        color: optional hex color
        sort_order: optional integer
    """
    data = request.get_json(force=True)
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO linkedin_theme_pillars
            (name, description, target_role_types, keywords, color, sort_order)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            data["name"],
            data.get("description"),
            json.dumps(data.get("target_role_types")) if data.get("target_role_types") else None,
            json.dumps(data.get("keywords")) if data.get("keywords") else None,
            data.get("color"),
            data.get("sort_order", 0),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/linkedin/theme-pillars/<int:pillar_id>", methods=["PUT", "PATCH"])
def update_theme_pillar(pillar_id):
    """Update a theme pillar."""
    data = request.get_json(force=True)
    allowed = ["name", "description", "target_role_types", "keywords",
               "color", "sort_order", "active"]
    sets, params = [], []
    for field in allowed:
        if field in data:
            val = data[field]
            if field in ("target_role_types", "keywords") and val is not None:
                val = json.dumps(val)
            sets.append(f"{field} = %s")
            params.append(val)

    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(pillar_id)
    row = db.execute_returning(
        f"""
        UPDATE linkedin_theme_pillars
        SET {', '.join(sets)}
        WHERE id = %s
        RETURNING *
        """,
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/linkedin/theme-pillars/<int:pillar_id>", methods=["DELETE"])
def delete_theme_pillar(pillar_id):
    """Delete a theme pillar."""
    count = db.execute(
        "DELETE FROM linkedin_theme_pillars WHERE id = %s",
        (pillar_id,),
    )
    if count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": pillar_id}), 200


# ---------------------------------------------------------------------------
# Voice Rules (S11.4)
# ---------------------------------------------------------------------------

@bp.route("/api/linkedin/voice-rules", methods=["GET"])
def list_voice_rules():
    """List LinkedIn voice rules with optional category filter.

    Query params:
        category: tone, structure, vocabulary, hook, cta, banned_patterns
    """
    category = request.args.get("category")
    if category:
        rows = db.query(
            "SELECT * FROM linkedin_voice_rules WHERE category = %s ORDER BY id",
            (category,),
        )
    else:
        rows = db.query(
            "SELECT * FROM linkedin_voice_rules ORDER BY category, id"
        )
    return jsonify(rows), 200


@bp.route("/api/linkedin/voice-rules", methods=["POST"])
def create_voice_rule():
    """Create a LinkedIn voice rule.

    Body (JSON):
        category (required): tone, structure, vocabulary, hook, cta, banned_patterns
        rule_text (required): the rule text
        source: manual, ai_extracted, template (default: manual)
        persona_template: executive, technical, creative, academic
    """
    data = request.get_json(force=True)
    if not data.get("category"):
        return jsonify({"error": "category is required"}), 400
    if not data.get("rule_text"):
        return jsonify({"error": "rule_text is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO linkedin_voice_rules
            (category, rule_text, source, persona_template)
        VALUES (%s, %s, %s, %s)
        RETURNING *
        """,
        (
            data["category"],
            data["rule_text"],
            data.get("source", "manual"),
            data.get("persona_template"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/linkedin/voice-rules/<int:rule_id>", methods=["PUT", "PATCH"])
def update_voice_rule(rule_id):
    """Update a voice rule."""
    data = request.get_json(force=True)
    allowed = ["category", "rule_text", "source", "persona_template", "active"]
    sets, params = [], []
    for field in allowed:
        if field in data:
            sets.append(f"{field} = %s")
            params.append(data[field])

    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(rule_id)
    row = db.execute_returning(
        f"""
        UPDATE linkedin_voice_rules
        SET {', '.join(sets)}
        WHERE id = %s
        RETURNING *
        """,
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/linkedin/voice-rules/<int:rule_id>", methods=["DELETE"])
def delete_voice_rule(rule_id):
    """Delete a voice rule."""
    count = db.execute(
        "DELETE FROM linkedin_voice_rules WHERE id = %s",
        (rule_id,),
    )
    if count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": rule_id}), 200


@bp.route("/api/linkedin/voice-rules/template", methods=["POST"])
def load_voice_template():
    """Load a starter voice rule template.

    Body (JSON):
        persona_template (required): executive, technical, creative, academic
    """
    data = request.get_json(force=True)
    persona = data.get("persona_template")
    if not persona:
        return jsonify({"error": "persona_template is required"}), 400

    templates = {
        "executive": [
            {"category": "tone", "rule_text": "Authoritative but approachable. Lead with outcomes and strategic thinking."},
            {"category": "structure", "rule_text": "Open with a bold statement or counter-intuitive insight. Keep paragraphs to 1-2 lines."},
            {"category": "vocabulary", "rule_text": "Use business impact language: revenue, growth, transformation, scale. Avoid jargon without context."},
            {"category": "hook", "rule_text": "First line must create curiosity or challenge a common assumption."},
            {"category": "cta", "rule_text": "End with a question that invites perspective sharing, not just agreement."},
            {"category": "banned_patterns", "rule_text": "No: 'thought leader', 'synergy', 'circle back', 'at the end of the day', 'it goes without saying'."},
        ],
        "technical": [
            {"category": "tone", "rule_text": "Precise and practical. Show don't tell. Code examples welcome."},
            {"category": "structure", "rule_text": "Problem-solution-result format. Use numbered lists for steps."},
            {"category": "vocabulary", "rule_text": "Technical terms are fine for the target audience. Define acronyms on first use."},
            {"category": "hook", "rule_text": "Start with a real problem you solved or a surprising technical finding."},
            {"category": "cta", "rule_text": "Ask what approaches others have tried or invite alternative solutions."},
            {"category": "banned_patterns", "rule_text": "No: 'game-changer', 'revolutionary', 'simply put', vague performance claims without numbers."},
        ],
        "creative": [
            {"category": "tone", "rule_text": "Storytelling-driven. Personal anecdotes that connect to universal truths."},
            {"category": "structure", "rule_text": "Narrative arc: setup, tension, resolution, takeaway. Short punchy lines."},
            {"category": "vocabulary", "rule_text": "Conversational and vivid. Use analogies and metaphors from everyday life."},
            {"category": "hook", "rule_text": "Open with a scene, a moment, or a surprising personal admission."},
            {"category": "cta", "rule_text": "Invite readers to share their own story or experience."},
            {"category": "banned_patterns", "rule_text": "No: corporate speak, passive voice, 'I am pleased to announce', humble brags."},
        ],
        "academic": [
            {"category": "tone", "rule_text": "Evidence-based and thoughtful. Reference research but make it accessible."},
            {"category": "structure", "rule_text": "Thesis, evidence, implications. Use data points as anchors."},
            {"category": "vocabulary", "rule_text": "Precise but not dense. Translate academic concepts into business value."},
            {"category": "hook", "rule_text": "Lead with a surprising statistic or a common misconception you can debunk."},
            {"category": "cta", "rule_text": "Ask readers if their experience matches the research or invite counter-examples."},
            {"category": "banned_patterns", "rule_text": "No: 'studies show' without citing which study, unnecessary hedging, walls of text."},
        ],
    }

    rules = templates.get(persona)
    if not rules:
        return jsonify({"error": f"Unknown persona: {persona}. Choose: executive, technical, creative, academic"}), 400

    created = []
    for rule in rules:
        row = db.execute_returning(
            """
            INSERT INTO linkedin_voice_rules
                (category, rule_text, source, persona_template)
            VALUES (%s, %s, 'template', %s)
            RETURNING *
            """,
            (rule["category"], rule["rule_text"], persona),
        )
        created.append(row)

    return jsonify({"persona": persona, "rules_created": len(created), "rules": created}), 201


@bp.route("/api/linkedin/voice-check", methods=["POST"])
def voice_check():
    """Validate text against LinkedIn voice rules.

    Body (JSON):
        text (required): text to validate
        category: optional category to check against (default: all active rules)

    Returns violations and suggestions.
    """
    data = request.get_json(force=True)
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "text is required"}), 400

    category = data.get("category")
    if category:
        rules = db.query(
            "SELECT * FROM linkedin_voice_rules WHERE category = %s AND active = TRUE",
            (category,),
        )
    else:
        rules = db.query(
            "SELECT * FROM linkedin_voice_rules WHERE active = TRUE ORDER BY category"
        )

    text_lower = text.lower()
    violations = []
    for rule in rules:
        if rule["category"] == "banned_patterns":
            # Extract banned phrases from rule_text (after "No:" pattern)
            rule_text = rule["rule_text"]
            if "No:" in rule_text or "no:" in rule_text:
                phrases_part = rule_text.split(":", 1)[1] if ":" in rule_text else rule_text
                phrases = [p.strip().strip("'\"") for p in phrases_part.split(",")]
                for phrase in phrases:
                    clean = phrase.strip().rstrip(".")
                    if clean and clean.lower() in text_lower:
                        violations.append({
                            "rule_id": rule["id"],
                            "category": rule["category"],
                            "violation": f"Banned pattern found: '{clean}'",
                            "rule_text": rule["rule_text"],
                        })

    return jsonify({
        "text_length": len(text),
        "rules_checked": len(rules),
        "violations": violations,
        "passed": len(violations) == 0,
    }), 200


# ---------------------------------------------------------------------------
# Skills Audits (S11.3)
# ---------------------------------------------------------------------------

@bp.route("/api/linkedin/skills-audits", methods=["GET"])
def list_skills_audits():
    """List skills audits with pagination.

    Query params:
        limit: max results (default 20)
        offset: pagination offset (default 0)
    """
    limit = int(request.args.get("limit", 20))
    offset = int(request.args.get("offset", 0))
    rows = db.query(
        """
        SELECT * FROM linkedin_skills_audits
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/linkedin/skills-audits/latest", methods=["GET"])
def latest_skills_audit():
    """Get the most recent skills audit."""
    row = db.query_one(
        "SELECT * FROM linkedin_skills_audits ORDER BY created_at DESC LIMIT 1"
    )
    if not row:
        return jsonify({"error": "No skills audits found"}), 404
    return jsonify(row), 200


@bp.route("/api/linkedin/skills-audits/<int:audit_id>", methods=["GET"])
def get_skills_audit(audit_id):
    """Get a single skills audit by ID."""
    row = db.query_one(
        "SELECT * FROM linkedin_skills_audits WHERE id = %s",
        (audit_id,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/linkedin/skills-audits", methods=["POST"])
def create_skills_audit():
    """Create a new skills audit.

    Body (JSON):
        target_jd_ids: optional list of saved_job IDs
    """
    data = request.get_json(force=True)
    target_jd_ids = data.get("target_jd_ids")

    row = db.execute_returning(
        """
        INSERT INTO linkedin_skills_audits (target_jd_ids)
        VALUES (%s)
        RETURNING *
        """,
        (json.dumps(target_jd_ids) if target_jd_ids else None,),
    )
    return jsonify(row), 201


# ---------------------------------------------------------------------------
# Recruiter Search Optimization (S11.5)
# ---------------------------------------------------------------------------

@bp.route("/api/linkedin/keyword-gap", methods=["POST"])
def keyword_gap():
    """Run keyword gap analysis: profile content vs target JDs.

    Body (JSON):
        profile_text (required): current LinkedIn profile text
        target_jd_ids: optional list of saved_job IDs to compare against
    """
    data = request.get_json(force=True)
    profile_text = data.get("profile_text", "")
    if not profile_text:
        return jsonify({"error": "profile_text is required"}), 400

    target_jd_ids = data.get("target_jd_ids", [])

    # Get keywords from target JDs if provided
    jd_keywords = set()
    if target_jd_ids:
        jobs = db.query(
            """
            SELECT title, company, description
            FROM saved_jobs
            WHERE id = ANY(%s)
            """,
            (target_jd_ids,),
        )
        for job in jobs:
            desc = (job.get("description") or "").lower()
            title = (job.get("title") or "").lower()
            # Simple keyword extraction from JDs
            for word in (desc + " " + title).split():
                clean = word.strip(".,;:!?()[]{}\"'").lower()
                if len(clean) > 3:
                    jd_keywords.add(clean)

    profile_words = set()
    for word in profile_text.lower().split():
        clean = word.strip(".,;:!?()[]{}\"'").lower()
        if len(clean) > 3:
            profile_words.add(clean)

    missing = sorted(jd_keywords - profile_words) if jd_keywords else []
    overlap = sorted(jd_keywords & profile_words) if jd_keywords else []

    return jsonify({
        "profile_word_count": len(profile_words),
        "jd_keyword_count": len(jd_keywords),
        "overlap_count": len(overlap),
        "missing_keywords": missing[:50],
        "matching_keywords": overlap[:50],
        "coverage_pct": round(len(overlap) / len(jd_keywords) * 100, 1) if jd_keywords else 0,
    }), 200


@bp.route("/api/linkedin/recruiter-search-tips", methods=["GET"])
def recruiter_search_tips():
    """Get optimization tips based on latest profile audit."""
    audit = db.query_one(
        "SELECT * FROM linkedin_profile_audits ORDER BY created_at DESC LIMIT 1"
    )
    if not audit:
        return jsonify({"error": "No profile audits found. Run a profile audit first."}), 404

    tips = []
    section_scores = audit.get("section_scores") or {}
    keyword_gaps = audit.get("keyword_gaps") or {}

    # Generate tips based on section scores
    for section, score in section_scores.items():
        if isinstance(score, (int, float)) and score < 70:
            tips.append({
                "section": section,
                "score": score,
                "priority": "high" if score < 50 else "medium",
                "tip": f"Your {section} section scores {score}/100. Focus on adding relevant keywords and quantified achievements.",
            })

    # Tips from keyword gaps
    missing = keyword_gaps.get("missing", [])
    if missing:
        tips.append({
            "section": "keywords",
            "priority": "high",
            "tip": f"Add these missing keywords to improve recruiter search visibility: {', '.join(missing[:10])}",
        })

    # General tips
    tips.append({
        "section": "general",
        "priority": "low",
        "tip": "Use industry-standard job titles in your headline for better search matching.",
    })
    tips.append({
        "section": "general",
        "priority": "low",
        "tip": "Add location keywords if targeting specific markets.",
    })

    return jsonify({
        "audit_id": audit["id"],
        "audit_date": audit["created_at"],
        "overall_score": audit.get("overall_score"),
        "tips": tips,
    }), 200


# ---------------------------------------------------------------------------
# Endorsement Strategy (S11)
# ---------------------------------------------------------------------------

@bp.route("/api/linkedin/endorsement-strategy", methods=["GET"])
def endorsement_strategy():
    """Identify skills with low endorsement counts and suggest endorsers.

    Cross-references skills table with target role requirements.
    Returns priority list: skill name, current endorsement count,
    target roles needing it, and suggested contacts who could endorse.
    """
    # Get all skills (endorsement_count may not exist yet; use demand_frequency as proxy)
    skills = db.query(
        """
        SELECT id, name, category, proficiency,
               COALESCE(demand_frequency, 0) AS endorsement_count
        FROM skills
        ORDER BY COALESCE(demand_frequency, 0) ASC, name
        """
    )
    if not skills:
        return jsonify({"error": "No skills found in database"}), 404

    # Get target roles from active applications and saved jobs
    target_roles = db.query(
        """
        SELECT DISTINCT role FROM (
            SELECT role FROM applications
            WHERE status NOT IN ('Rejected', 'Ghosted', 'Withdrawn', 'Rescinded')
            UNION
            SELECT title AS role FROM saved_jobs
            WHERE status NOT IN ('archived', 'rejected')
        ) roles
        WHERE role IS NOT NULL
        LIMIT 20
        """
    )
    role_titles = [r["role"] for r in target_roles] if target_roles else []

    # Get active contacts who could endorse
    endorsers = db.query(
        """
        SELECT id, name, title, company, relationship, relationship_strength, linkedin_url
        FROM contacts
        WHERE relationship_stage = 'active'
           OR relationship_strength IN ('strong', 'warm')
        ORDER BY
            CASE relationship_strength WHEN 'strong' THEN 1 WHEN 'warm' THEN 2 ELSE 3 END,
            last_contact DESC NULLS LAST
        LIMIT 30
        """
    )

    # Build priority list
    priority_skills = []
    for skill in skills:
        endorsement_count = skill["endorsement_count"]
        # Low endorsement = high priority
        if endorsement_count < 5:
            priority = "high"
        elif endorsement_count < 15:
            priority = "medium"
        else:
            priority = "low"

        # Find matching endorsers (people in similar domain)
        suggested = []
        skill_name_lower = (skill["name"] or "").lower()
        for contact in (endorsers or []):
            contact_title = (contact.get("title") or "").lower()
            # Simple heuristic: suggest contacts whose title relates to skill category
            if skill_name_lower in contact_title or (skill.get("category") or "").lower() in contact_title:
                suggested.append({
                    "name": contact["name"],
                    "title": contact.get("title"),
                    "company": contact.get("company"),
                    "relationship_strength": contact.get("relationship_strength"),
                })
            if len(suggested) >= 3:
                break

        # If no specific matches, suggest top strong contacts
        if not suggested and endorsers:
            for contact in endorsers[:3]:
                suggested.append({
                    "name": contact["name"],
                    "title": contact.get("title"),
                    "company": contact.get("company"),
                    "relationship_strength": contact.get("relationship_strength"),
                })

        priority_skills.append({
            "skill_id": skill["id"],
            "skill_name": skill["name"],
            "category": skill.get("category"),
            "proficiency": skill.get("proficiency"),
            "endorsement_count": endorsement_count,
            "priority": priority,
            "target_roles": role_titles[:5],
            "suggested_endorsers": suggested,
        })

    # Sort: high priority first, then by endorsement count ascending
    priority_order = {"high": 0, "medium": 1, "low": 2}
    priority_skills.sort(key=lambda x: (priority_order.get(x["priority"], 3), x["endorsement_count"]))

    return jsonify({
        "total_skills": len(skills),
        "low_endorsement_count": sum(1 for s in priority_skills if s["priority"] == "high"),
        "target_roles": role_titles,
        "skills": priority_skills,
    }), 200


# ---------------------------------------------------------------------------
# LinkedIn Import Enrichment (S9 — match imported connections to existing contacts)
# ---------------------------------------------------------------------------

@bp.route("/api/linkedin/import/enrich", methods=["POST"])
def import_enrich():
    """After CSV import, match imported connections to existing contacts by name/email.

    Body JSON:
        connections (required): array of {name, email, company, title, linkedin_url}

    Returns matched records (linked) and unmatched (flagged as new potential contacts).
    """
    data = request.get_json(force=True)
    connections = data.get("connections", [])
    if not connections:
        return jsonify({"error": "connections array is required"}), 400

    matched = []
    unmatched = []

    for conn in connections:
        name = (conn.get("name") or "").strip()
        email = (conn.get("email") or "").strip()

        if not name and not email:
            continue

        # Try to match by email first (strongest signal), then by name
        existing = None
        if email:
            existing = db.query_one(
                "SELECT id, name, company, email FROM contacts WHERE email ILIKE %s AND merged_into_id IS NULL",
                (email,),
            )
        if not existing and name:
            existing = db.query_one(
                "SELECT id, name, company, email FROM contacts WHERE name ILIKE %s AND merged_into_id IS NULL",
                (name,),
            )

        if existing:
            # Enrich existing contact with any new data
            enrich_sets, enrich_params = [], []
            if conn.get("linkedin_url") and not existing.get("linkedin_url"):
                enrich_sets.append("linkedin_url = %s")
                enrich_params.append(conn["linkedin_url"])
            if conn.get("title"):
                enrich_sets.append("title = %s")
                enrich_params.append(conn["title"])
            if conn.get("company") and not existing.get("company"):
                enrich_sets.append("company = %s")
                enrich_params.append(conn["company"])

            if enrich_sets:
                enrich_sets.append("enriched_at = NOW()")
                enrich_sets.append("enrichment_source = 'linkedin_import'")
                enrich_sets.append("updated_at = NOW()")
                enrich_params.append(existing["id"])
                db.execute(
                    f"UPDATE contacts SET {', '.join(enrich_sets)} WHERE id = %s",
                    enrich_params,
                )

            matched.append({
                "contact_id": existing["id"],
                "name": existing["name"],
                "matched_by": "email" if email and existing.get("email") and email.lower() == (existing["email"] or "").lower() else "name",
                "enriched_fields": [s.split(" =")[0] for s in enrich_sets if s not in ("enriched_at = NOW()", "enrichment_source = 'linkedin_import'", "updated_at = NOW()")],
            })
        else:
            unmatched.append({
                "name": name,
                "email": email,
                "company": conn.get("company"),
                "title": conn.get("title"),
                "linkedin_url": conn.get("linkedin_url"),
                "status": "new_potential_contact",
            })

    return jsonify({
        "matched": matched,
        "matched_count": len(matched),
        "unmatched": unmatched,
        "unmatched_count": len(unmatched),
        "total_processed": len(matched) + len(unmatched),
    }), 200
