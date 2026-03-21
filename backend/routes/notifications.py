"""Routes for notifications system."""

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("notifications", __name__)


@bp.route("/api/notifications", methods=["GET"])
def list_notifications():
    """List notifications with optional filters.

    Query params:
        read: 'true' or 'false' to filter by read status
        dismissed: 'true' or 'false' (default: false — hide dismissed)
        type: notification type string
        severity: info, action_needed, urgent
        limit: max results (default 50)
        offset: pagination offset (default 0)
    """
    read_param = request.args.get("read")
    dismissed_param = request.args.get("dismissed", "false")
    type_param = request.args.get("type")
    severity_param = request.args.get("severity")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []

    if read_param is not None:
        clauses.append("read = %s")
        params.append(read_param.lower() == "true")

    # Default: hide dismissed unless caller explicitly requests them
    if dismissed_param.lower() == "false":
        clauses.append("dismissed = FALSE")
    elif dismissed_param.lower() == "true":
        clauses.append("dismissed = TRUE")
    # else: dismissed param omitted entirely — show all

    if type_param:
        clauses.append("type = %s")
        params.append(type_param)

    if severity_param:
        clauses.append("severity = %s")
        params.append(severity_param)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT *
        FROM notifications
        {where}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/notifications/unread-count", methods=["GET"])
def unread_count():
    """Return count of unread, non-dismissed notifications."""
    row = db.query_one(
        "SELECT COUNT(*) AS count FROM notifications WHERE read = FALSE AND dismissed = FALSE"
    )
    return jsonify({"count": row["count"] if row else 0}), 200


@bp.route("/api/notifications/<int:notification_id>", methods=["GET"])
def get_notification(notification_id):
    """Get a single notification by ID."""
    row = db.query_one(
        "SELECT * FROM notifications WHERE id = %s",
        (notification_id,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/notifications", methods=["POST"])
def create_notification():
    """Create a new notification.

    Body (JSON):
        type (required): notification type
        title (required): notification title
        severity: info, action_needed, urgent (default: info)
        body: optional detailed text
        link: optional frontend route path
        entity_type: optional polymorphic entity type
        entity_id: optional entity ID
        expires_at: optional ISO timestamp
    """
    data = request.get_json(force=True)
    if not data.get("type"):
        return jsonify({"error": "type is required"}), 400
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO notifications
            (type, severity, title, body, link, entity_type, entity_id, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            data["type"],
            data.get("severity", "info"),
            data["title"],
            data.get("body"),
            data.get("link"),
            data.get("entity_type"),
            data.get("entity_id"),
            data.get("expires_at"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/notifications/<int:notification_id>/read", methods=["PUT"])
def mark_read(notification_id):
    """Mark a notification as read."""
    count = db.execute(
        "UPDATE notifications SET read = TRUE WHERE id = %s",
        (notification_id,),
    )
    if count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"id": notification_id, "read": True}), 200


@bp.route("/api/notifications/<int:notification_id>/dismiss", methods=["PUT"])
def dismiss_notification(notification_id):
    """Mark a notification as dismissed."""
    count = db.execute(
        "UPDATE notifications SET dismissed = TRUE, read = TRUE WHERE id = %s",
        (notification_id,),
    )
    if count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"id": notification_id, "dismissed": True}), 200


@bp.route("/api/notifications/mark-all-read", methods=["POST"])
def mark_all_read():
    """Mark all unread notifications as read."""
    count = db.execute(
        "UPDATE notifications SET read = TRUE WHERE read = FALSE"
    )
    return jsonify({"updated": count}), 200


@bp.route("/api/notifications/preferences", methods=["GET"])
def list_preferences():
    """List all notification preferences."""
    rows = db.query(
        "SELECT * FROM notification_preferences ORDER BY notification_type"
    )
    return jsonify(rows), 200


@bp.route("/api/notifications/preferences/<string:notification_type>", methods=["PUT"])
def update_preference(notification_type):
    """Update a notification preference (enabled true/false).

    Body (JSON):
        enabled (required): boolean
    """
    data = request.get_json(force=True)
    if "enabled" not in data:
        return jsonify({"error": "enabled is required"}), 400

    row = db.execute_returning(
        """
        UPDATE notification_preferences
        SET enabled = %s
        WHERE notification_type = %s
        RETURNING *
        """,
        (bool(data["enabled"]), notification_type),
    )
    if not row:
        return jsonify({"error": "Preference type not found"}), 404
    return jsonify(row), 200
