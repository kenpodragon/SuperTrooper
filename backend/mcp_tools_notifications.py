# Notifications MCP Tools
# Imports needed (already available in mcp_server.py):
#   from db import db
#   mcp is already defined
#
# Integration: copy these tool functions into mcp_server.py
# after the existing tools. The @mcp.tool() decorator registers them.


@mcp.tool()
def get_notifications(
    status: str | None = None,
    type: str | None = None,
    severity: str | None = None,
    limit: int = 20,
) -> dict:
    """Get notifications, optionally filtered.

    Args:
        status: Filter by status - 'unread', 'read', 'dismissed', or None for all
        type: Filter by notification type (new_job, status_change, follow_up_due,
              stale_warning, interview_reminder, contact_follow_up, digest_ready, email_matched)
        severity: Filter by severity level (info, action_needed, urgent)
        limit: Max results (default 20)

    Returns:
        dict with count and notifications list
    """
    clauses, params = [], []

    if status == "unread":
        clauses.append("read = FALSE")
        clauses.append("dismissed = FALSE")
    elif status == "read":
        clauses.append("read = TRUE")
    elif status == "dismissed":
        clauses.append("dismissed = TRUE")
    else:
        # Default: hide dismissed
        clauses.append("dismissed = FALSE")

    if type:
        clauses.append("type = %s")
        params.append(type)

    if severity:
        clauses.append("severity = %s")
        params.append(severity)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT *
        FROM notifications
        {where}
        ORDER BY created_at DESC
        LIMIT %s
        """,
        params + [limit],
    )
    return {"count": len(rows), "notifications": rows}


@mcp.tool()
def dismiss_notification(notification_id: int) -> dict:
    """Dismiss a notification by ID.

    Args:
        notification_id: The notification ID to dismiss

    Returns:
        dict with success status and notification ID
    """
    count = db.execute(
        "UPDATE notifications SET dismissed = TRUE, read = TRUE WHERE id = %s",
        (notification_id,),
    )
    if count == 0:
        return {"success": False, "error": f"Notification {notification_id} not found"}
    return {"success": True, "id": notification_id, "dismissed": True}


@mcp.tool()
def create_notification(
    type: str,
    title: str,
    severity: str = "info",
    body: str | None = None,
    link: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> dict:
    """Create a new notification.

    Args:
        type: Notification type (new_job, status_change, follow_up_due,
              stale_warning, interview_reminder, contact_follow_up,
              digest_ready, email_matched)
        title: Notification title
        severity: info, action_needed, or urgent (default: info)
        body: Optional detailed body text
        link: Optional frontend route path (e.g., /applications/42)
        entity_type: Optional entity type (application, saved_job, contact, fresh_job)
        entity_id: Optional entity ID

    Returns:
        dict with created notification record
    """
    row = db.execute_returning(
        """
        INSERT INTO notifications
            (type, severity, title, body, link, entity_type, entity_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (type, severity, title, body, link, entity_type, entity_id),
    )
    return row or {"error": "Insert failed"}
