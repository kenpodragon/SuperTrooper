"""Routes for workflow automation engine."""

import json
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("workflows", __name__)


def _execute_action(workflow, trigger_data=None):
    """Execute a workflow's action. Returns (action_result dict, success bool, error_message str|None)."""
    action_type = workflow["action_type"]
    action_config = workflow["action_config"] or {}

    try:
        if action_type == "create_notification":
            notif = db.execute_returning(
                """
                INSERT INTO notifications (type, severity, title, body)
                VALUES (%s, %s, %s, %s)
                RETURNING id, type, severity, title, body, created_at
                """,
                (
                    action_config.get("type", "workflow"),
                    action_config.get("severity", "info"),
                    action_config.get("title", f"Workflow: {workflow['name']}"),
                    action_config.get("body", ""),
                ),
            )
            return {"action": "create_notification", "notification": notif}, True, None

        elif action_type == "log_activity":
            # Try activity_log table; fall through gracefully if it doesn't exist
            try:
                db.execute(
                    """
                    INSERT INTO activity_log (entity_type, entity_id, action, details)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (
                        action_config.get("entity_type", "workflow"),
                        action_config.get("entity_id"),
                        action_config.get("action", workflow["name"]),
                        json.dumps(action_config.get("details", {})),
                    ),
                )
                return {"action": "log_activity", "logged": True}, True, None
            except Exception as inner_err:
                # activity_log table may not exist; record in workflow_log only
                return {
                    "action": "log_activity",
                    "logged": False,
                    "note": "activity_log table unavailable; logged to workflow_log only",
                    "detail": str(inner_err),
                }, True, None

        elif action_type == "update_field":
            # MVP: never execute the update — just log what would happen
            return {
                "action": "update_field",
                "simulated": True,
                "would_update": {
                    "table": action_config.get("table"),
                    "field": action_config.get("field"),
                    "value": action_config.get("value"),
                    "where": action_config.get("where"),
                },
                "note": "update_field is simulated in MVP — no DB write performed",
            }, True, None

        else:
            return {
                "action": action_type,
                "error": f"Unknown action_type: {action_type}",
            }, False, f"Unknown action_type: {action_type}"

    except Exception as exc:
        return {"action": action_type, "error": str(exc)}, False, str(exc)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@bp.route("/api/workflows", methods=["GET"])
def list_workflows():
    """List all workflows with optional filters."""
    enabled_param = request.args.get("enabled")
    trigger_type = request.args.get("trigger_type")

    clauses, params = [], []
    if enabled_param is not None:
        clauses.append("enabled = %s")
        params.append(enabled_param.lower() in ("true", "1", "yes"))
    if trigger_type:
        clauses.append("trigger_type = %s")
        params.append(trigger_type)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"SELECT * FROM workflows {where} ORDER BY created_at DESC",
        params or None,
    )
    return jsonify(rows), 200


# ---------------------------------------------------------------------------
# All workflow logs (global)
# ---------------------------------------------------------------------------

@bp.route("/api/workflows/log", methods=["GET"])
def list_all_workflow_logs():
    """Get all workflow logs, recent first."""
    limit = int(request.args.get("limit", 50))
    rows = db.query(
        """
        SELECT wl.*, w.name AS workflow_name
        FROM workflow_log wl
        LEFT JOIN workflows w ON w.id = wl.workflow_id
        ORDER BY wl.triggered_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    return jsonify(rows), 200


# ---------------------------------------------------------------------------
# Single workflow
# ---------------------------------------------------------------------------

@bp.route("/api/workflows/<int:workflow_id>", methods=["GET"])
def get_workflow(workflow_id):
    """Get a single workflow with recent log entries."""
    workflow = db.query_one("SELECT * FROM workflows WHERE id = %s", (workflow_id,))
    if not workflow:
        return jsonify({"error": "Not found"}), 404

    workflow["recent_log"] = db.query(
        """
        SELECT * FROM workflow_log
        WHERE workflow_id = %s
        ORDER BY triggered_at DESC
        LIMIT 20
        """,
        (workflow_id,),
    )
    return jsonify(workflow), 200


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@bp.route("/api/workflows", methods=["POST"])
def create_workflow():
    """Create a new workflow."""
    data = request.get_json(force=True)
    for required in ("name", "trigger_type", "trigger_config", "action_type", "action_config"):
        if not data.get(required):
            return jsonify({"error": f"{required} is required"}), 400

    trigger_config = data["trigger_config"]
    action_config = data["action_config"]
    conditions = data.get("conditions")

    # Accept dicts or JSON strings
    if isinstance(trigger_config, str):
        trigger_config = json.loads(trigger_config)
    if isinstance(action_config, str):
        action_config = json.loads(action_config)
    if isinstance(conditions, str) and conditions:
        conditions = json.loads(conditions)

    row = db.execute_returning(
        """
        INSERT INTO workflows (name, trigger_type, trigger_config, conditions, action_type, action_config, enabled)
        VALUES (%s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s)
        RETURNING *
        """,
        (
            data["name"],
            data["trigger_type"],
            json.dumps(trigger_config),
            json.dumps(conditions) if conditions is not None else None,
            data["action_type"],
            json.dumps(action_config),
            data.get("enabled", True),
        ),
    )
    return jsonify(row), 201


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

@bp.route("/api/workflows/<int:workflow_id>", methods=["PUT"])
def update_workflow(workflow_id):
    """Update a workflow."""
    data = request.get_json(force=True)
    allowed_scalar = ["name", "trigger_type", "action_type", "enabled"]
    allowed_jsonb = ["trigger_config", "conditions", "action_config"]

    sets, params = [], []
    for key in allowed_scalar:
        if key in data:
            sets.append(f"{key} = %s")
            params.append(data[key])
    for key in allowed_jsonb:
        if key in data:
            val = data[key]
            if isinstance(val, str):
                val = json.loads(val)
            sets.append(f"{key} = %s::jsonb")
            params.append(json.dumps(val))

    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(workflow_id)
    row = db.execute_returning(
        f"UPDATE workflows SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Enable / Disable
# ---------------------------------------------------------------------------

@bp.route("/api/workflows/<int:workflow_id>/enable", methods=["PUT"])
def enable_workflow(workflow_id):
    """Enable a workflow."""
    row = db.execute_returning(
        "UPDATE workflows SET enabled = TRUE WHERE id = %s RETURNING *",
        (workflow_id,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/workflows/<int:workflow_id>/disable", methods=["PUT"])
def disable_workflow(workflow_id):
    """Disable a workflow."""
    row = db.execute_returning(
        "UPDATE workflows SET enabled = FALSE WHERE id = %s RETURNING *",
        (workflow_id,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Manual trigger
# ---------------------------------------------------------------------------

@bp.route("/api/workflows/<int:workflow_id>/trigger", methods=["POST"])
def trigger_workflow(workflow_id):
    """Manually trigger a workflow and execute its action."""
    workflow = db.query_one("SELECT * FROM workflows WHERE id = %s", (workflow_id,))
    if not workflow:
        return jsonify({"error": "Not found"}), 404

    body = request.get_json(silent=True) or {}
    trigger_data = body.get("trigger_data")

    action_result, success, error_message = _execute_action(workflow, trigger_data)

    # Log execution
    log_row = db.execute_returning(
        """
        INSERT INTO workflow_log (workflow_id, trigger_data, action_result, success, error_message)
        VALUES (%s, %s::jsonb, %s::jsonb, %s, %s)
        RETURNING *
        """,
        (
            workflow_id,
            json.dumps(trigger_data) if trigger_data is not None else None,
            json.dumps(action_result),
            success,
            error_message,
        ),
    )

    # Update last_run_at
    db.execute(
        "UPDATE workflows SET last_run_at = NOW() WHERE id = %s",
        (workflow_id,),
    )

    return jsonify({"log": log_row, "result": action_result, "success": success}), 200


# ---------------------------------------------------------------------------
# Workflow-specific log
# ---------------------------------------------------------------------------

@bp.route("/api/workflows/<int:workflow_id>/log", methods=["GET"])
def get_workflow_log(workflow_id):
    """Get execution log for a specific workflow."""
    workflow = db.query_one("SELECT id, name FROM workflows WHERE id = %s", (workflow_id,))
    if not workflow:
        return jsonify({"error": "Not found"}), 404

    limit = int(request.args.get("limit", 50))
    rows = db.query(
        "SELECT * FROM workflow_log WHERE workflow_id = %s ORDER BY triggered_at DESC LIMIT %s",
        (workflow_id, limit),
    )
    return jsonify({"workflow": workflow, "log": rows}), 200
