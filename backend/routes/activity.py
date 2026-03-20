"""Routes for activity_log (audit trail)."""

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("activity", __name__)


@bp.route("/api/activity", methods=["GET"])
def list_activity():
    """Recent activity feed with optional filters."""
    action = request.args.get("action")
    entity_type = request.args.get("entity_type")
    entity_id = request.args.get("entity_id")
    days = request.args.get("days")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if action:
        clauses.append("action = %s")
        params.append(action)
    if entity_type:
        clauses.append("entity_type = %s")
        params.append(entity_type)
    if entity_id:
        clauses.append("entity_id = %s")
        params.append(int(entity_id))
    if days:
        clauses.append("created_at >= NOW() - INTERVAL '%s days'")
        params.append(int(days))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT * FROM activity_log
        {where}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/activity", methods=["POST"])
def create_activity():
    """Log an activity event."""
    data = request.get_json(force=True)
    if not data.get("action"):
        return jsonify({"error": "action is required"}), 400

    import json
    row = db.execute_returning(
        """
        INSERT INTO activity_log (action, entity_type, entity_id, details)
        VALUES (%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data["action"], data.get("entity_type"), data.get("entity_id"),
            json.dumps(data["details"]) if data.get("details") else None,
        ),
    )
    return jsonify(row), 201
