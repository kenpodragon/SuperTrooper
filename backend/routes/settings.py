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
