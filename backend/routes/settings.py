"""Routes for settings (single-row config table)."""

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
