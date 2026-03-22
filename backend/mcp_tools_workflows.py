"""MCP tool functions for workflow automation engine.

Orchestrator note: call register_workflows_tools(mcp) in mcp_server.py.
"""

from __future__ import annotations

import json

import db


def register_workflows_tools(mcp):
    """Register all workflow MCP tools with the given MCP server instance."""

    @mcp.tool()
    def get_workflows(enabled: bool | None = None, trigger_type: str | None = None) -> dict:
        """List all workflows, optionally filtered.

        Args:
            enabled: Filter by enabled status
            trigger_type: Filter by trigger type (schedule, event)

        Returns:
            dict with workflows list
        """
        clauses, params = [], []
        if enabled is not None:
            clauses.append("enabled = %s")
            params.append(enabled)
        if trigger_type:
            clauses.append("trigger_type = %s")
            params.append(trigger_type)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = db.query(
            f"SELECT * FROM workflows {where} ORDER BY created_at DESC",
            params or None,
        )
        return {"workflows": rows, "count": len(rows)}

    @mcp.tool()
    def trigger_workflow(workflow_id: int, trigger_data: str | None = None) -> dict:
        """Manually trigger a workflow and execute its action.

        Args:
            workflow_id: Workflow ID to trigger
            trigger_data: Optional JSON string with trigger context data

        Returns:
            dict with execution result
        """
        workflow = db.query_one("SELECT * FROM workflows WHERE id = %s", (workflow_id,))
        if not workflow:
            return {"error": f"Workflow {workflow_id} not found"}

        parsed_trigger_data = None
        if trigger_data:
            try:
                parsed_trigger_data = json.loads(trigger_data)
            except json.JSONDecodeError:
                return {"error": "trigger_data is not valid JSON"}

        action_type = workflow["action_type"]
        action_config = workflow["action_config"] or {}
        action_result = {}
        success = True
        error_message = None

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
                action_result = {"action": "create_notification", "notification": notif}

            elif action_type == "log_activity":
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
                    action_result = {"action": "log_activity", "logged": True}
                except Exception as inner_err:
                    action_result = {
                        "action": "log_activity",
                        "logged": False,
                        "note": "activity_log table unavailable; logged to workflow_log only",
                        "detail": str(inner_err),
                    }

            elif action_type == "update_field":
                action_result = {
                    "action": "update_field",
                    "simulated": True,
                    "would_update": {
                        "table": action_config.get("table"),
                        "field": action_config.get("field"),
                        "value": action_config.get("value"),
                        "where": action_config.get("where"),
                    },
                    "note": "update_field is simulated in MVP — no DB write performed",
                }

            else:
                action_result = {"action": action_type, "error": f"Unknown action_type: {action_type}"}
                success = False
                error_message = f"Unknown action_type: {action_type}"

        except Exception as exc:
            action_result = {"action": action_type, "error": str(exc)}
            success = False
            error_message = str(exc)

        log_row = db.execute_returning(
            """
            INSERT INTO workflow_log (workflow_id, trigger_data, action_result, success, error_message)
            VALUES (%s, %s::jsonb, %s::jsonb, %s, %s)
            RETURNING *
            """,
            (
                workflow_id,
                json.dumps(parsed_trigger_data) if parsed_trigger_data is not None else None,
                json.dumps(action_result),
                success,
                error_message,
            ),
        )

        db.execute("UPDATE workflows SET last_run_at = NOW() WHERE id = %s", (workflow_id,))

        return {
            "workflow_id": workflow_id,
            "workflow_name": workflow["name"],
            "success": success,
            "result": action_result,
            "log_id": log_row["id"] if log_row else None,
            "error": error_message,
        }

    @mcp.tool()
    def create_workflow(
        name: str,
        trigger_type: str,
        trigger_config: str,
        action_type: str,
        action_config: str,
        conditions: str | None = None,
    ) -> dict:
        """Create a new workflow automation.

        Args:
            name: Workflow name
            trigger_type: schedule or event
            trigger_config: JSON string with trigger configuration
            action_type: create_notification, update_field, or log_activity
            action_config: JSON string with action configuration
            conditions: Optional JSON string with conditions

        Returns:
            dict with created workflow
        """
        try:
            parsed_trigger_config = json.loads(trigger_config)
        except json.JSONDecodeError:
            return {"error": "trigger_config is not valid JSON"}

        try:
            parsed_action_config = json.loads(action_config)
        except json.JSONDecodeError:
            return {"error": "action_config is not valid JSON"}

        parsed_conditions = None
        if conditions:
            try:
                parsed_conditions = json.loads(conditions)
            except json.JSONDecodeError:
                return {"error": "conditions is not valid JSON"}

        valid_trigger_types = ("schedule", "event")
        if trigger_type not in valid_trigger_types:
            return {"error": f"trigger_type must be one of: {', '.join(valid_trigger_types)}"}

        valid_action_types = ("create_notification", "update_field", "log_activity")
        if action_type not in valid_action_types:
            return {"error": f"action_type must be one of: {', '.join(valid_action_types)}"}

        row = db.execute_returning(
            """
            INSERT INTO workflows (name, trigger_type, trigger_config, conditions, action_type, action_config, enabled)
            VALUES (%s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, TRUE)
            RETURNING *
            """,
            (
                name,
                trigger_type,
                json.dumps(parsed_trigger_config),
                json.dumps(parsed_conditions) if parsed_conditions is not None else None,
                action_type,
                json.dumps(parsed_action_config),
            ),
        )
        return {"workflow": row, "created": True}
