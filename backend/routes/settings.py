"""Routes for settings (single-row config table)."""

import json
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("settings", __name__)

ALLOWED_FIELDS = {
    "ai_provider",
    "ai_enabled",
    "ai_model",
    "default_template_id",
    "duplicate_threshold",
    "preferences",
}


def _serialize_row(row):
    """Convert RealDictRow to plain dict, serializing datetimes."""
    d = dict(row)
    for key in ("created_at", "updated_at"):
        if d.get(key) is not None:
            d[key] = d[key].isoformat()
    return d


@bp.route("/api/settings", methods=["GET"])
def get_settings():
    """Return the single settings row."""
    rows = db.query(
        """
        SELECT id, ai_provider, ai_enabled, ai_model, default_template_id,
               duplicate_threshold, preferences, created_at, updated_at
        FROM settings
        WHERE id = 1
        """,
        (),
    )
    if not rows:
        return jsonify({"error": "Settings row not found"}), 404
    return jsonify(_serialize_row(rows[0]))


@bp.route("/api/settings", methods=["PATCH"])
def update_settings():
    """Update allowed settings fields and return the updated row."""
    body = request.get_json(silent=True) or {}

    updates = {k: v for k, v in body.items() if k in ALLOWED_FIELDS}
    if not updates:
        return jsonify({"error": "No valid fields provided"}), 400

    set_clauses = ", ".join(f"{col} = %s" for col in updates)
    values = list(updates.values()) + [1]

    row = db.execute_returning(
        f"""
        UPDATE settings
        SET {set_clauses}, updated_at = NOW()
        WHERE id = %s
        RETURNING id, ai_provider, ai_enabled, ai_model, default_template_id,
                  duplicate_threshold, preferences, created_at, updated_at
        """,
        values,
    )
    if not row:
        return jsonify({"error": "Settings row not found after update"}), 500
    return jsonify(_serialize_row(row))


@bp.route("/api/settings/config", methods=["GET"])
def get_config():
    """Return current platform configuration.

    Returns the settings row plus computed platform metadata
    (version, available integrations, data counts).
    """
    rows = db.query(
        """
        SELECT id, ai_provider, ai_enabled, ai_model, default_template_id,
               duplicate_threshold, preferences, created_at, updated_at
        FROM settings
        WHERE id = 1
        """,
        (),
    )
    if not rows:
        return jsonify({"error": "Settings row not found"}), 404

    config = _serialize_row(rows[0])

    # Add computed platform metadata
    counts = {}
    for table in ("career_history", "bullets", "skills", "applications",
                   "contacts", "companies", "resume_recipes", "resume_templates"):
        try:
            r = db.query(f"SELECT count(*) AS cnt FROM {table}", ())
            counts[table] = r[0]["cnt"] if r else 0
        except Exception:
            counts[table] = 0

    config["platform"] = {
        "version": "0.1.0",
        "data_counts": counts,
    }
    return jsonify(config)


@bp.route("/api/settings/config", methods=["PUT"])
def update_config():
    """Update configuration values and return the updated config.

    Accepts the same fields as PATCH /api/settings, returns the
    enriched config response (same as GET /api/settings/config).
    """
    body = request.get_json(silent=True) or {}

    updates = {k: v for k, v in body.items() if k in ALLOWED_FIELDS}
    if not updates:
        return jsonify({"error": "No valid fields provided. Allowed: " + ", ".join(sorted(ALLOWED_FIELDS))}), 400

    set_clauses = ", ".join(f"{col} = %s" for col in updates)
    values = list(updates.values()) + [1]

    row = db.execute_returning(
        f"""
        UPDATE settings
        SET {set_clauses}, updated_at = NOW()
        WHERE id = %s
        RETURNING id, ai_provider, ai_enabled, ai_model, default_template_id,
                  duplicate_threshold, preferences, created_at, updated_at
        """,
        values,
    )
    if not row:
        return jsonify({"error": "Settings row not found after update"}), 500

    config = _serialize_row(row)

    # Add computed platform metadata (same as GET)
    counts = {}
    for table in ("career_history", "bullets", "skills", "applications",
                   "contacts", "companies", "resume_recipes", "resume_templates"):
        try:
            r = db.query(f"SELECT count(*) AS cnt FROM {table}", ())
            counts[table] = r[0]["cnt"] if r else 0
        except Exception:
            counts[table] = 0

    config["platform"] = {
        "version": "0.1.0",
        "data_counts": counts,
    }
    return jsonify(config)


@bp.route("/api/settings/test-ai", methods=["POST"])
def test_ai_connection():
    """Test the configured AI provider connection."""
    from ai_providers import get_provider, list_providers

    data = request.get_json() or {}
    provider_name = data.get("provider")

    if provider_name:
        # Test specific provider
        from ai_providers import PROVIDERS
        if provider_name not in PROVIDERS:
            return jsonify({"error": f"Unknown provider: {provider_name}"}), 400
        provider = PROVIDERS[provider_name]()
    else:
        # Test configured provider
        provider = get_provider()

    if not provider:
        return jsonify({
            "status": "disabled",
            "message": "AI is disabled or no provider configured.",
            "providers": list_providers(),
        })

    health = provider.health_check()
    return jsonify({
        "status": "ok" if health.get("available") else "error",
        "provider": provider.name,
        "health": health,
        "providers": list_providers(),
    })


# ---------------------------------------------------------------------------
# Configurable Aging Thresholds
# ---------------------------------------------------------------------------

DEFAULT_AGING_RULES = {
    "applied": 14,
    "interviewing": 7,
    "post_interview": 7,
    "saved": 30,
}


@bp.route("/api/settings/aging-rules", methods=["GET"])
def get_aging_rules():
    """Return current aging thresholds per status.

    Reads from settings.preferences->aging_rules. Falls back to defaults.
    """
    row = db.query_one("SELECT preferences FROM settings WHERE id = 1")
    prefs = (row.get("preferences") or {}) if row else {}

    # preferences may be a string or dict depending on DB driver
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except (json.JSONDecodeError, TypeError):
            prefs = {}

    aging_rules = prefs.get("aging_rules", DEFAULT_AGING_RULES)
    return jsonify({
        "aging_rules": aging_rules,
        "defaults": DEFAULT_AGING_RULES,
    }), 200


@bp.route("/api/settings/aging-rules", methods=["PUT"])
def update_aging_rules():
    """Update aging thresholds per status.

    JSON body:
        applied (int): days before 'Applied' is stale (default 14)
        interviewing (int): days before 'Interviewing' is stale (default 7)
        post_interview (int): days after interview with no response (default 7)
        saved (int): days before saved job is stale (default 30)
    """
    data = request.get_json(force=True)

    # Validate: all values must be positive integers
    new_rules = {}
    for key in DEFAULT_AGING_RULES:
        if key in data:
            val = data[key]
            if not isinstance(val, int) or val < 1:
                return jsonify({"error": f"{key} must be a positive integer"}), 400
            new_rules[key] = val

    if not new_rules:
        return jsonify({"error": "Provide at least one threshold: " + ", ".join(DEFAULT_AGING_RULES.keys())}), 400

    # Read current preferences
    row = db.query_one("SELECT preferences FROM settings WHERE id = 1")
    prefs = (row.get("preferences") or {}) if row else {}
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except (json.JSONDecodeError, TypeError):
            prefs = {}

    # Merge with existing aging_rules (keep defaults for unset keys)
    existing_rules = prefs.get("aging_rules", DEFAULT_AGING_RULES.copy())
    existing_rules.update(new_rules)
    prefs["aging_rules"] = existing_rules

    db.execute(
        "UPDATE settings SET preferences = %s::jsonb, updated_at = NOW() WHERE id = 1",
        (json.dumps(prefs),),
    )

    return jsonify({
        "aging_rules": existing_rules,
        "updated_keys": list(new_rules.keys()),
    }), 200


@bp.route("/api/plugin/health", methods=["GET"])
def plugin_health():
    """Plugin-specific health check with version and feature info."""
    rows = db.query(
        "SELECT count(*) AS cnt FROM applications WHERE status NOT IN ('Rejected', 'Ghosted', 'Withdrawn')",
        (),
    )
    active = rows[0]["cnt"] if rows else 0
    return jsonify({
        "status": "healthy",
        "version": "0.1.0",
        "active_applications": active,
        "features": {
            "job_capture": True,
            "gap_analysis": True,
            "auto_apply": False,
            "networking": False,
        },
    })


# ---------------------------------------------------------------------------
# Voice Rules CRUD
# ---------------------------------------------------------------------------

@bp.route("/api/settings/voice-rules", methods=["GET"])
def list_voice_rules():
    """List all active voice rules (for settings UI).

    Query params:
        category: filter by category (banned_word, banned_construction, resume_rule, etc.)
    """
    category = request.args.get("category")
    clauses, params = [], []

    if category:
        clauses.append("category = %s")
        params.append(category)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT id, category, subcategory, rule_text, explanation, created_at
        FROM voice_rules
        {where}
        ORDER BY category, subcategory, id
        """,
        params,
    )

    # Group by category
    grouped = {}
    for r in (rows or []):
        cat = r.get("category", "other")
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(r)

    return jsonify({
        "rules": rows or [],
        "by_category": grouped,
        "total": len(rows) if rows else 0,
    }), 200


@bp.route("/api/settings/voice-rules", methods=["POST"])
def add_voice_rule():
    """Add a custom voice rule.

    Body (JSON):
        category (required): banned_word, banned_construction, resume_rule, style_rule, custom
        rule_text (required): the rule text or banned word/phrase
        subcategory: optional grouping
        explanation: why this rule exists
    """
    data = request.get_json(force=True)
    category = data.get("category")
    rule_text = data.get("rule_text", "").strip()

    if not category or not rule_text:
        return jsonify({"error": "category and rule_text are required"}), 400

    # Check for duplicate
    existing = db.query_one(
        "SELECT id FROM voice_rules WHERE category = %s AND rule_text = %s",
        (category, rule_text),
    )
    if existing:
        return jsonify({"error": "Rule already exists", "existing_id": existing["id"]}), 409

    row = db.execute_returning(
        """
        INSERT INTO voice_rules (part, part_title, category, subcategory, rule_text, explanation, sort_order)
        VALUES (99, 'Custom Rules', %s, %s, %s, %s, 999)
        RETURNING *
        """,
        (
            category,
            data.get("subcategory"),
            rule_text,
            data.get("explanation"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/settings/voice-rules/<int:rule_id>", methods=["DELETE"])
def delete_voice_rule(rule_id):
    """Remove a voice rule (hard delete)."""
    row = db.execute_returning(
        """
        DELETE FROM voice_rules
        WHERE id = %s
        RETURNING id, category, rule_text
        """,
        (rule_id,),
    )
    if not row:
        return jsonify({"error": "Voice rule not found"}), 404
    return jsonify({"deleted": True, "rule": row}), 200


# ---------------------------------------------------------------------------
# User Preferences
# ---------------------------------------------------------------------------

@bp.route("/api/settings/preferences", methods=["GET"])
def get_preferences():
    """Get user preferences (notification, display, search settings).

    Reads from settings.preferences JSONB column.
    """
    row = db.query_one("SELECT preferences FROM settings WHERE id = 1")
    prefs = (row.get("preferences") or {}) if row else {}

    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except (json.JSONDecodeError, TypeError):
            prefs = {}

    # Provide defaults for expected keys
    defaults = {
        "notifications_enabled": True,
        "email_digest": "weekly",
        "display_theme": "light",
        "default_search_limit": 50,
        "auto_voice_check": True,
        "aging_rules": DEFAULT_AGING_RULES,
    }

    # Merge defaults with stored prefs
    merged = {**defaults, **prefs}

    return jsonify(merged), 200


@bp.route("/api/settings/preferences", methods=["PUT"])
def update_preferences():
    """Update user preferences.

    Body (JSON): any preference keys to update. Merges with existing.
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No preferences provided"}), 400

    # Read current preferences
    row = db.query_one("SELECT preferences FROM settings WHERE id = 1")
    prefs = (row.get("preferences") or {}) if row else {}
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except (json.JSONDecodeError, TypeError):
            prefs = {}

    # Merge new values
    prefs.update(data)

    db.execute(
        "UPDATE settings SET preferences = %s::jsonb, updated_at = NOW() WHERE id = 1",
        (json.dumps(prefs),),
    )

    return jsonify({
        "preferences": prefs,
        "updated_keys": list(data.keys()),
    }), 200


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

@bp.route("/api/health", methods=["GET"])
def health_check():
    """Simple health check returning status and version."""
    try:
        db.query_one("SELECT 1")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    return jsonify({"status": "ok", "version": "1.0", "db": db_status}), 200


# ---------------------------------------------------------------------------
# Settings Export / Import
# ---------------------------------------------------------------------------

@bp.route("/api/settings/export", methods=["GET"])
def export_settings():
    """Export all settings as JSON for backup."""
    row = db.query_one(
        """SELECT id, ai_provider, ai_enabled, ai_model, default_template_id,
                  duplicate_threshold, preferences, created_at, updated_at
           FROM settings WHERE id = 1"""
    )
    if not row:
        return jsonify({"error": "Settings row not found"}), 404

    settings_data = _serialize_row(row)

    # Include voice rules
    voice_rules = db.query("SELECT category, subcategory, rule_text, explanation FROM voice_rules ORDER BY id")

    # Include aging rules from preferences
    prefs = settings_data.get("preferences") or {}
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except (json.JSONDecodeError, TypeError):
            prefs = {}

    return jsonify({
        "export_version": "1.0",
        "exported_at": __import__("datetime").datetime.utcnow().isoformat(),
        "settings": settings_data,
        "voice_rules": voice_rules or [],
        "preferences": prefs,
    }), 200


@bp.route("/api/settings/import", methods=["POST"])
def import_settings():
    """Import settings from JSON backup.

    Body JSON: output of GET /api/settings/export
    """
    data = request.get_json(force=True)
    if not data.get("settings"):
        return jsonify({"error": "Missing 'settings' key in import data"}), 400

    imported = data["settings"]
    updates = {k: v for k, v in imported.items() if k in ALLOWED_FIELDS}

    if updates:
        set_clauses = ", ".join(f"{col} = %s" for col in updates)
        values = list(updates.values()) + [1]
        db.execute(
            f"UPDATE settings SET {set_clauses}, updated_at = NOW() WHERE id = %s",
            values,
        )

    # Import voice rules if present
    imported_rules = 0
    for rule in data.get("voice_rules", []):
        existing = db.query_one(
            "SELECT id FROM voice_rules WHERE category = %s AND rule_text = %s",
            (rule.get("category"), rule.get("rule_text")),
        )
        if not existing:
            db.execute(
                """INSERT INTO voice_rules (part, part_title, category, subcategory, rule_text, explanation, sort_order)
                   VALUES (99, 'Imported', %s, %s, %s, %s, 999)""",
                (rule.get("category"), rule.get("subcategory"), rule.get("rule_text"), rule.get("explanation")),
            )
            imported_rules += 1

    return jsonify({
        "status": "imported",
        "settings_fields_updated": list(updates.keys()),
        "voice_rules_imported": imported_rules,
    }), 200


# ---------------------------------------------------------------------------
# Integrations Status
# ---------------------------------------------------------------------------

@bp.route("/api/settings/integrations", methods=["GET"])
def list_integrations():
    """List available integrations and their connection status."""
    import os

    integrations = [
        {
            "name": "Gmail",
            "key": "gmail",
            "description": "Email search and recruiter detection",
            "connected": bool(os.environ.get("GMAIL_TOKEN") or os.environ.get("GOOGLE_TOKEN")),
            "icon": "mail",
        },
        {
            "name": "Google Calendar",
            "key": "google_calendar",
            "description": "Interview scheduling and event tracking",
            "connected": bool(os.environ.get("GCAL_TOKEN") or os.environ.get("GOOGLE_TOKEN")),
            "icon": "calendar",
        },
        {
            "name": "Indeed",
            "key": "indeed",
            "description": "Job search and company data",
            "connected": bool(os.environ.get("INDEED_API_KEY") or os.environ.get("INDEED_TOKEN")),
            "icon": "briefcase",
        },
        {
            "name": "LinkedIn",
            "key": "linkedin",
            "description": "Profile import, connection sync, and content",
            "connected": bool(os.environ.get("LINKEDIN_TOKEN") or os.environ.get("LINKEDIN_COOKIE")),
            "icon": "users",
        },
    ]
    return jsonify({"integrations": integrations}), 200
