"""CRM routes for relationship tracking, touchpoints, networking tasks, and drip sequences."""

import json
from datetime import date, timedelta

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("crm", __name__)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

@bp.route("/api/crm/pipeline", methods=["GET"])
def get_pipeline():
    """Contacts grouped by relationship_stage with counts and contact list."""
    stages = ["cold", "warm", "active", "close", "dormant"]

    result = {}
    for stage in stages:
        contacts = db.query(
            """
            SELECT id, name, company, title, relationship_stage, health_score,
                   last_touchpoint_at, last_contact, email, linkedin_url, tags
            FROM contacts
            WHERE relationship_stage = %s
            ORDER BY health_score ASC NULLS LAST, name
            """,
            (stage,),
        )
        result[stage] = {"count": len(contacts), "contacts": contacts}

    return jsonify(result), 200


# ---------------------------------------------------------------------------
# Touchpoints
# ---------------------------------------------------------------------------

@bp.route("/api/crm/contacts/<int:contact_id>/touchpoints", methods=["GET"])
def list_touchpoints(contact_id):
    """List touchpoints for a contact."""
    contact = db.query_one("SELECT id FROM contacts WHERE id = %s", (contact_id,))
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    rows = db.query(
        """
        SELECT id, contact_id, type, channel, direction, notes, logged_at
        FROM touchpoints
        WHERE contact_id = %s
        ORDER BY logged_at DESC
        """,
        (contact_id,),
    )
    return jsonify(rows), 200


@bp.route("/api/crm/contacts/<int:contact_id>/touchpoints", methods=["POST"])
def log_touchpoint(contact_id):
    """Log a new touchpoint and update contact's last_touchpoint_at and last_contact."""
    contact = db.query_one("SELECT id FROM contacts WHERE id = %s", (contact_id,))
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    data = request.get_json(force=True)
    if not data.get("type"):
        return jsonify({"error": "type is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO touchpoints (contact_id, type, channel, direction, notes)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            contact_id,
            data["type"],
            data.get("channel", "email"),
            data.get("direction", "outbound"),
            data.get("notes"),
        ),
    )

    # Update contact timestamps
    db.execute(
        """
        UPDATE contacts
        SET last_touchpoint_at = NOW(),
            last_contact = CURRENT_DATE,
            updated_at = NOW()
        WHERE id = %s
        """,
        (contact_id,),
    )

    return jsonify(row), 201


# ---------------------------------------------------------------------------
# Networking Tasks
# ---------------------------------------------------------------------------

@bp.route("/api/crm/contacts/<int:contact_id>/tasks", methods=["GET"])
def list_tasks(contact_id):
    """List networking tasks for a contact."""
    contact = db.query_one("SELECT id FROM contacts WHERE id = %s", (contact_id,))
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    rows = db.query(
        """
        SELECT id, contact_id, task_type, title, due_date, completed,
               completed_at, notes, created_at
        FROM networking_tasks
        WHERE contact_id = %s
        ORDER BY completed ASC, due_date ASC NULLS LAST, created_at DESC
        """,
        (contact_id,),
    )
    return jsonify(rows), 200


@bp.route("/api/crm/contacts/<int:contact_id>/tasks", methods=["POST"])
def create_task(contact_id):
    """Create a networking task for a contact."""
    contact = db.query_one("SELECT id FROM contacts WHERE id = %s", (contact_id,))
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    data = request.get_json(force=True)
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400
    if not data.get("task_type"):
        return jsonify({"error": "task_type is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO networking_tasks (contact_id, task_type, title, due_date, notes)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            contact_id,
            data["task_type"],
            data["title"],
            data.get("due_date"),
            data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/crm/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    """Update a networking task (complete it, change due date, etc.)."""
    data = request.get_json(force=True)
    allowed = ["task_type", "title", "due_date", "completed", "notes"]
    sets, params = [], []

    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            params.append(data[key])

    # Auto-set completed_at when marking complete
    if data.get("completed") is True:
        sets.append("completed_at = NOW()")
    elif data.get("completed") is False:
        sets.append("completed_at = NULL")

    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(task_id)
    row = db.execute_returning(
        f"UPDATE networking_tasks SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

@bp.route("/api/crm/contacts/<int:contact_id>/stage", methods=["PUT"])
def update_stage(contact_id):
    """Update a contact's relationship stage."""
    valid_stages = {"cold", "warm", "active", "close", "dormant"}
    data = request.get_json(force=True)
    stage = data.get("stage")
    if not stage:
        return jsonify({"error": "stage is required"}), 400
    if stage not in valid_stages:
        return jsonify({"error": f"stage must be one of: {', '.join(sorted(valid_stages))}"}), 400

    row = db.execute_returning(
        """
        UPDATE contacts
        SET relationship_stage = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING id, name, company, relationship_stage, updated_at
        """,
        (stage, contact_id),
    )
    if not row:
        return jsonify({"error": "Contact not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Upcoming tasks
# ---------------------------------------------------------------------------

@bp.route("/api/crm/tasks/upcoming", methods=["GET"])
def upcoming_tasks():
    """All incomplete tasks due within N days (default 7)."""
    days = int(request.args.get("days", 7))
    cutoff = date.today() + timedelta(days=days)

    rows = db.query(
        """
        SELECT nt.id, nt.contact_id, nt.task_type, nt.title, nt.due_date,
               nt.notes, nt.created_at,
               c.name AS contact_name, c.company AS contact_company
        FROM networking_tasks nt
        JOIN contacts c ON c.id = nt.contact_id
        WHERE nt.completed = FALSE
          AND (nt.due_date IS NULL OR nt.due_date <= %s)
        ORDER BY nt.due_date ASC NULLS LAST, nt.created_at ASC
        """,
        (cutoff,),
    )
    return jsonify(rows), 200


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@bp.route("/api/crm/health", methods=["GET"])
def health_overview():
    """Contacts sorted by health_score ascending (lowest = needs attention)."""
    limit = int(request.args.get("limit", 50))
    rows = db.query(
        """
        SELECT id, name, company, title, relationship_stage, health_score,
               last_touchpoint_at, last_contact, tags
        FROM contacts
        ORDER BY health_score ASC NULLS FIRST
        LIMIT %s
        """,
        (limit,),
    )
    return jsonify(rows), 200


@bp.route("/api/crm/stale-contacts", methods=["GET"])
def stale_contacts():
    """Return contacts with health_score below threshold with suggested actions.

    Query params:
        threshold (int, default 30): health score cutoff
        limit (int, default 50): max results
    """
    threshold = float(request.args.get("threshold", 30))
    limit = int(request.args.get("limit", 50))

    rows = db.query(
        """
        SELECT id, name, company, title, relationship_stage, health_score,
               last_touchpoint_at, last_contact, tags,
               EXTRACT(EPOCH FROM (NOW() - last_touchpoint_at)) / 86400 AS days_since_touchpoint
        FROM contacts
        WHERE health_score < %s OR (health_score IS NULL AND last_touchpoint_at IS NULL)
        ORDER BY health_score ASC NULLS FIRST
        LIMIT %s
        """,
        (threshold, limit),
    )

    # Attach a suggested action to each stale contact
    result = []
    for r in rows:
        days = r.get("days_since_touchpoint")
        score = r.get("health_score")
        if days is None or days > 180:
            action = "Re-engage: no contact in 6+ months. Send a check-in message."
        elif days > 90:
            action = "Follow up: last touch was 3-6 months ago. Share an update or article."
        elif score is not None and score < 15:
            action = "Priority: very low score. Schedule a call or coffee chat."
        else:
            action = "Nudge: health score is low. Log a touchpoint to rebuild momentum."
        result.append({**r, "suggested_action": action})

    return jsonify({"stale_contacts": result, "count": len(result), "threshold": threshold}), 200


@bp.route("/api/crm/contacts/<int:contact_id>/health", methods=["PUT"])
def recalculate_health(contact_id):
    """Recalculate health score for a contact based on touchpoint recency and frequency."""
    contact = db.query_one("SELECT id, last_touchpoint_at FROM contacts WHERE id = %s", (contact_id,))
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    # Gather touchpoint stats
    stats = db.query_one(
        """
        SELECT
            EXTRACT(EPOCH FROM (NOW() - MAX(logged_at))) / 86400 AS days_since_last,
            COUNT(*) FILTER (WHERE logged_at >= NOW() - INTERVAL '30 days') AS count_30d,
            COUNT(*) FILTER (WHERE logged_at >= NOW() - INTERVAL '90 days') AS count_90d
        FROM touchpoints
        WHERE contact_id = %s
        """,
        (contact_id,),
    )

    days_since = stats["days_since_last"] if stats and stats["days_since_last"] is not None else 365
    count_30d = stats["count_30d"] if stats else 0
    count_90d = stats["count_90d"] if stats else 0

    # Base formula
    score = 100.0
    score -= days_since * 2
    if count_30d == 0:
        score -= 10
    score += count_90d * 5

    # Clamp 0-100
    score = max(0.0, min(100.0, score))

    row = db.execute_returning(
        """
        UPDATE contacts
        SET health_score = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING id, name, company, relationship_stage, health_score, last_touchpoint_at
        """,
        (score, contact_id),
    )
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Drip Sequences
# ---------------------------------------------------------------------------

@bp.route("/api/crm/drip-sequences", methods=["POST"])
def create_drip_sequence():
    """Create a multi-touch outreach sequence.

    Body (JSON):
        sequence_name (required): name for this drip sequence
        contact_id (required): contact to run the sequence for
        steps (required): array of step objects:
            [{day_offset: int, message_type: str, channel: str, subject: str, body: str}]
    """
    data = request.get_json(force=True)
    name = data.get("sequence_name")
    contact_id = data.get("contact_id")
    steps = data.get("steps")

    if not name:
        return jsonify({"error": "sequence_name is required"}), 400
    if not contact_id:
        return jsonify({"error": "contact_id is required"}), 400
    if not steps or not isinstance(steps, list):
        return jsonify({"error": "steps array is required"}), 400

    # Verify contact exists
    contact = db.query_one("SELECT id, name FROM contacts WHERE id = %s", (contact_id,))
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    row = db.execute_returning(
        """INSERT INTO drip_sequences (sequence_name, contact_id, steps, current_step, status)
           VALUES (%s, %s, %s, 0, 'active')
           RETURNING *""",
        (name, contact_id, json.dumps(steps)),
    )

    return jsonify(row), 201


@bp.route("/api/crm/drip-sequences", methods=["GET"])
def list_drip_sequences():
    """List all drip sequences with optional filters.

    Query params:
        contact_id (optional): filter by contact
        status (optional): filter by status (active, paused, completed)
    """
    contact_id = request.args.get("contact_id")
    status = request.args.get("status")

    clauses, params = [], []
    if contact_id:
        clauses.append("ds.contact_id = %s")
        params.append(int(contact_id))
    if status:
        clauses.append("ds.status = %s")
        params.append(status)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    rows = db.query(
        f"""SELECT ds.*, c.name AS contact_name, c.company AS contact_company
            FROM drip_sequences ds
            JOIN contacts c ON c.id = ds.contact_id
            {where}
            ORDER BY ds.created_at DESC""",
        params,
    )

    return jsonify(rows), 200


@bp.route("/api/crm/drip-sequences/<int:seq_id>/advance", methods=["POST"])
def advance_drip_sequence(seq_id):
    """Advance a drip sequence to its next step.

    Increments current_step, returns the next step details.
    If all steps completed, marks sequence as 'completed'.
    """
    seq = db.query_one("SELECT * FROM drip_sequences WHERE id = %s", (seq_id,))
    if not seq:
        return jsonify({"error": "Drip sequence not found"}), 404

    if seq["status"] != "active":
        return jsonify({"error": f"Sequence is {seq['status']}, cannot advance"}), 400

    steps = seq["steps"]
    if isinstance(steps, str):
        steps = json.loads(steps)

    current = seq["current_step"]
    next_step = current + 1

    if next_step >= len(steps):
        # All steps completed
        row = db.execute_returning(
            """UPDATE drip_sequences
               SET status = 'completed', current_step = %s,
                   completed_at = NOW(), updated_at = NOW()
               WHERE id = %s RETURNING *""",
            (next_step, seq_id),
        )
        return jsonify({
            "sequence": row,
            "message": "Sequence completed - all steps done",
            "completed": True,
        }), 200

    # Advance to next step
    row = db.execute_returning(
        """UPDATE drip_sequences
           SET current_step = %s, updated_at = NOW()
           WHERE id = %s RETURNING *""",
        (next_step, seq_id),
    )

    next_step_detail = steps[next_step] if next_step < len(steps) else None

    return jsonify({
        "sequence": row,
        "current_step_index": next_step,
        "current_step_detail": next_step_detail,
        "steps_remaining": len(steps) - next_step - 1,
        "completed": False,
    }), 200


@bp.route("/api/crm/drip-sequences/<int:seq_id>", methods=["GET"])
def get_drip_sequence(seq_id):
    """Get a single drip sequence with full details."""
    row = db.query_one(
        """SELECT ds.*, c.name AS contact_name, c.company AS contact_company
           FROM drip_sequences ds
           JOIN contacts c ON c.id = ds.contact_id
           WHERE ds.id = %s""",
        (seq_id,),
    )
    if not row:
        return jsonify({"error": "Drip sequence not found"}), 404

    steps = row.get("steps", [])
    if isinstance(steps, str):
        steps = json.loads(steps)

    current = row.get("current_step", 0)
    return jsonify({
        **row,
        "total_steps": len(steps),
        "current_step_detail": steps[current] if current < len(steps) else None,
        "steps_remaining": max(0, len(steps) - current - 1),
    }), 200


@bp.route("/api/crm/drip-sequences/<int:seq_id>/pause", methods=["POST"])
def pause_drip_sequence(seq_id):
    """Pause an active drip sequence."""
    row = db.execute_returning(
        """UPDATE drip_sequences
           SET status = 'paused', updated_at = NOW()
           WHERE id = %s AND status = 'active'
           RETURNING *""",
        (seq_id,),
    )
    if not row:
        return jsonify({"error": "Sequence not found or not active"}), 404
    return jsonify(row), 200


@bp.route("/api/crm/drip-sequences/<int:seq_id>/resume", methods=["POST"])
def resume_drip_sequence(seq_id):
    """Resume a paused drip sequence."""
    row = db.execute_returning(
        """UPDATE drip_sequences
           SET status = 'active', updated_at = NOW()
           WHERE id = %s AND status = 'paused'
           RETURNING *""",
        (seq_id,),
    )
    if not row:
        return jsonify({"error": "Sequence not found or not paused"}), 404
    return jsonify(row), 200
