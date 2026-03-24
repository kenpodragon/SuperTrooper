"""Routes for workflow automation engine."""

import json
from flask import Blueprint, request, jsonify
import db
from ai_providers.router import route_inference

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


# ---------------------------------------------------------------------------
# Evaluate all active workflows against current state
# ---------------------------------------------------------------------------

@bp.route("/api/workflows/evaluate", methods=["POST"])
def evaluate_workflows():
    """Evaluate all enabled workflows against current application state.

    Checks trigger conditions (e.g., stale applications) and executes
    matching actions (create notification, draft follow-up, update status).
    """
    workflows = db.query(
        "SELECT * FROM workflows WHERE enabled = TRUE ORDER BY id"
    )
    if not workflows:
        return jsonify({"evaluated": 0, "triggered": 0, "results": []}), 200

    results = []
    triggered_count = 0

    for wf in workflows:
        trigger_type = wf["trigger_type"]
        trigger_config = wf["trigger_config"] or {}
        matched = False
        trigger_data = {}

        # --- Evaluate trigger conditions ---
        if trigger_type == "stale_application":
            days = trigger_config.get("days", 14)
            status_filter = trigger_config.get("status")
            clauses = [
                "a.status NOT IN ('Rejected', 'Ghosted', 'Withdrawn', 'Accepted', 'Rescinded')",
                "COALESCE(a.last_status_change, a.date_applied::timestamp) < NOW() - INTERVAL '%s days'",
            ]
            params = [days]
            if status_filter:
                clauses.append("a.status = %s")
                params.append(status_filter)

            stale = db.query(
                f"""
                SELECT a.id, a.company_name, a.role, a.status,
                       EXTRACT(DAY FROM NOW() - COALESCE(a.last_status_change, a.date_applied::timestamp))::int AS days_stale
                FROM applications a
                WHERE {' AND '.join(clauses)}
                ORDER BY days_stale DESC
                """,
                params,
            )
            if stale:
                matched = True
                trigger_data = {"stale_applications": stale, "count": len(stale)}

        elif trigger_type == "interview_upcoming":
            days_ahead = trigger_config.get("days_ahead", 3)
            upcoming = db.query(
                """
                SELECT i.id, i.date, i.type, a.company_name, a.role
                FROM interviews i
                LEFT JOIN applications a ON a.id = i.application_id
                WHERE i.date BETWEEN NOW() AND NOW() + INTERVAL '%s days'
                  AND i.outcome = 'pending'
                ORDER BY i.date ASC
                """,
                (days_ahead,),
            )
            if upcoming:
                matched = True
                trigger_data = {"upcoming_interviews": upcoming, "count": len(upcoming)}

        elif trigger_type == "status_change":
            target_status = trigger_config.get("status", "Rejected")
            lookback = trigger_config.get("lookback_hours", 24)
            changes = db.query(
                """
                SELECT ash.*, a.company_name, a.role
                FROM application_status_history ash
                LEFT JOIN applications a ON a.id = ash.application_id
                WHERE ash.new_status = %s
                  AND ash.changed_at > NOW() - INTERVAL '%s hours'
                ORDER BY ash.changed_at DESC
                """,
                (target_status, lookback),
            )
            if changes:
                matched = True
                trigger_data = {"status_changes": changes, "count": len(changes)}

        elif trigger_type == "schedule":
            # Schedule-based workflows are evaluated externally; skip here
            continue

        else:
            results.append({
                "workflow_id": wf["id"],
                "name": wf["name"],
                "matched": False,
                "note": f"Unknown trigger_type: {trigger_type}",
            })
            continue

        # --- Execute action if matched ---
        if matched:
            triggered_count += 1
            action_result, success, error_message = _execute_action(wf, trigger_data)

            # Log execution
            db.execute_returning(
                """
                INSERT INTO workflow_log (workflow_id, trigger_data, action_result, success, error_message)
                VALUES (%s, %s::jsonb, %s::jsonb, %s, %s)
                RETURNING id
                """,
                (
                    wf["id"],
                    json.dumps(trigger_data, default=str),
                    json.dumps(action_result, default=str),
                    success,
                    error_message,
                ),
            )
            db.execute("UPDATE workflows SET last_run_at = NOW() WHERE id = %s", (wf["id"],))

            results.append({
                "workflow_id": wf["id"],
                "name": wf["name"],
                "matched": True,
                "success": success,
                "action_result": action_result,
            })
        else:
            results.append({
                "workflow_id": wf["id"],
                "name": wf["name"],
                "matched": False,
            })

    python_result = {
        "evaluated": len(workflows),
        "triggered": triggered_count,
        "results": results,
    }

    def _python_eval_wf(ctx):
        return ctx["r"]

    def _ai_eval_wf(ctx):
        from ai_providers import get_provider
        provider = get_provider()
        triggered = [r for r in ctx["r"]["results"] if r.get("matched")]
        if not triggered:
            return ctx["r"]
        result = provider.analyze_strategy({
            "triggered_workflows": [{"name": t["name"], "result": t.get("action_result")} for t in triggered[:5]],
        })
        base = ctx["r"]
        base["ai_insights"] = result.get("insights", [])
        return base

    enhanced = route_inference(
        task="evaluate_workflows",
        context={"r": python_result},
        python_fallback=_python_eval_wf,
        ai_handler=_ai_eval_wf,
    )
    return jsonify(enhanced), 200


# ---------------------------------------------------------------------------
# Create workflow from predefined templates
# ---------------------------------------------------------------------------

WORKFLOW_TEMPLATES = {
    "stale-to-follow-up": {
        "name": "Stale Application Follow-Up",
        "trigger_type": "stale_application",
        "trigger_config": {"days": 7},
        "action_type": "create_notification",
        "action_config": {
            "type": "follow_up",
            "severity": "warning",
            "title": "Stale applications need follow-up",
            "body": "Applications stale for 7+ days detected. Draft follow-up emails.",
        },
    },
    "interview-prep": {
        "name": "Interview Prep Reminder",
        "trigger_type": "interview_upcoming",
        "trigger_config": {"days_ahead": 3},
        "action_type": "create_notification",
        "action_config": {
            "type": "interview_prep",
            "severity": "info",
            "title": "Upcoming interview — prep needed",
            "body": "Interview scheduled within 3 days. Generate prep package.",
        },
    },
    "rejection-analysis": {
        "name": "Rejection Analysis",
        "trigger_type": "status_change",
        "trigger_config": {"status": "Rejected", "lookback_hours": 24},
        "action_type": "create_notification",
        "action_config": {
            "type": "rejection",
            "severity": "info",
            "title": "New rejection — run analysis",
            "body": "Application rejected. Run rejection analysis to identify patterns.",
        },
    },
}


@bp.route("/api/workflows/templates", methods=["GET"])
def list_workflow_templates():
    """List available workflow templates."""
    templates = []
    for key, tmpl in WORKFLOW_TEMPLATES.items():
        templates.append({"key": key, "name": tmpl["name"], "trigger_type": tmpl["trigger_type"]})
    return jsonify(templates), 200


@bp.route("/api/workflows/templates", methods=["POST"])
def create_from_template():
    """Create a workflow from a predefined template.

    JSON body:
        template (str): one of 'stale-to-follow-up', 'interview-prep', 'rejection-analysis'
        overrides (dict): optional overrides for trigger_config, action_config, name, enabled
    """
    data = request.get_json(force=True)
    template_key = data.get("template")
    if not template_key or template_key not in WORKFLOW_TEMPLATES:
        return jsonify({
            "error": f"template must be one of: {', '.join(WORKFLOW_TEMPLATES.keys())}",
        }), 400

    tmpl = WORKFLOW_TEMPLATES[template_key].copy()
    overrides = data.get("overrides", {})

    # Apply overrides
    name = overrides.get("name", tmpl["name"])
    trigger_config = {**tmpl["trigger_config"], **overrides.get("trigger_config", {})}
    action_config = {**tmpl["action_config"], **overrides.get("action_config", {})}
    enabled = overrides.get("enabled", True)

    row = db.execute_returning(
        """
        INSERT INTO workflows (name, trigger_type, trigger_config, action_type, action_config, enabled)
        VALUES (%s, %s, %s::jsonb, %s, %s::jsonb, %s)
        RETURNING *
        """,
        (
            name,
            tmpl["trigger_type"],
            json.dumps(trigger_config),
            tmpl["action_type"],
            json.dumps(action_config),
            enabled,
        ),
    )
    return jsonify({"template": template_key, "workflow": row}), 201
