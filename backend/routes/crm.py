"""CRM routes for relationship tracking, touchpoints, networking tasks, and drip sequences."""

import json
import math
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

@bp.route("/api/crm/contacts/<int:contact_id>/stage", methods=["PUT", "PATCH"])
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


# ---------------------------------------------------------------------------
# CRM Tasks (crm_tasks table — richer task/reminder system)
# ---------------------------------------------------------------------------

@bp.route("/api/crm/reminders", methods=["POST"])
def create_crm_task():
    """Create a networking task/reminder with due_date, contact_id, task_type, description."""
    data = request.get_json(force=True)
    if not data.get("task_type"):
        return jsonify({"error": "task_type is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO crm_tasks (contact_id, task_type, description, due_date, status)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            data.get("contact_id"),
            data["task_type"],
            data.get("description"),
            data.get("due_date"),
            data.get("status", "pending"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/crm/reminders", methods=["GET"])
def list_crm_tasks():
    """List CRM reminders with filter: overdue, due_today, upcoming, completed, or all."""
    filter_type = request.args.get("filter", "all")
    limit = int(request.args.get("limit", 100))

    today = date.today()
    clauses, params = [], []

    if filter_type == "overdue":
        clauses.append("t.due_date < %s")
        clauses.append("t.status = 'pending'")
        params.append(today)
    elif filter_type == "due_today":
        clauses.append("t.due_date = %s")
        clauses.append("t.status = 'pending'")
        params.append(today)
    elif filter_type == "upcoming":
        clauses.append("t.due_date > %s")
        clauses.append("t.status = 'pending'")
        params.append(today)
    elif filter_type == "completed":
        clauses.append("t.status = 'completed'")
    elif filter_type == "snoozed":
        clauses.append("t.status = 'snoozed'")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    rows = db.query(
        f"""
        SELECT t.*, c.name AS contact_name, c.company AS contact_company
        FROM crm_tasks t
        LEFT JOIN contacts c ON c.id = t.contact_id
        {where}
        ORDER BY t.due_date ASC NULLS LAST, t.created_at DESC
        LIMIT %s
        """,
        params,
    )
    return jsonify({"tasks": rows, "count": len(rows), "filter": filter_type}), 200


@bp.route("/api/crm/reminders/<int:task_id>", methods=["PUT"])
def update_crm_task(task_id):
    """Update CRM reminder status (pending, completed, snoozed) and other fields."""
    data = request.get_json(force=True)
    allowed = ["task_type", "description", "due_date", "status", "snoozed_until"]
    sets, params = [], []

    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            params.append(data[key])

    # Auto-set completed_at when marking complete
    if data.get("status") == "completed":
        sets.append("completed_at = NOW()")
    elif data.get("status") in ("pending", "snoozed"):
        sets.append("completed_at = NULL")

    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(task_id)
    row = db.execute_returning(
        f"UPDATE crm_tasks SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(row), 200


@bp.route("/api/crm/reminders/overdue", methods=["GET"])
def overdue_crm_tasks():
    """List overdue CRM reminders with contact info."""
    rows = db.query(
        """
        SELECT t.*, c.name AS contact_name, c.company AS contact_company,
               c.email AS contact_email, c.relationship_stage
        FROM crm_tasks t
        LEFT JOIN contacts c ON c.id = t.contact_id
        WHERE t.due_date < CURRENT_DATE
          AND t.status = 'pending'
        ORDER BY t.due_date ASC
        """
    )
    return jsonify({"overdue_tasks": rows, "count": len(rows)}), 200


# ---------------------------------------------------------------------------
# CRM Pipeline Stages
# ---------------------------------------------------------------------------

@bp.route("/api/crm/pipeline/health", methods=["GET"])
def pipeline_health():
    """Aggregate health metrics: % active, % dormant, avg touchpoints/month."""
    total = db.query_one("SELECT COUNT(*) AS cnt FROM contacts")
    total_count = total["cnt"] if total else 0

    if total_count == 0:
        return jsonify({
            "total_contacts": 0,
            "stages": {},
            "pct_active": 0,
            "pct_dormant": 0,
            "avg_touchpoints_per_month": 0,
        }), 200

    stage_counts = db.query(
        """
        SELECT relationship_stage, COUNT(*) AS cnt
        FROM contacts
        GROUP BY relationship_stage
        """
    )
    stages = {r["relationship_stage"]: r["cnt"] for r in stage_counts}

    active_count = stages.get("active", 0) + stages.get("close", 0)
    dormant_count = stages.get("dormant", 0)

    # Avg touchpoints per month (last 90 days extrapolated)
    tp_stats = db.query_one(
        """
        SELECT COUNT(*) AS total_tp
        FROM touchpoints
        WHERE logged_at >= NOW() - INTERVAL '90 days'
        """
    )
    total_tp_90d = tp_stats["total_tp"] if tp_stats else 0
    avg_per_month = round(total_tp_90d / 3.0, 1)

    return jsonify({
        "total_contacts": total_count,
        "stages": stages,
        "pct_active": round(active_count / total_count * 100, 1),
        "pct_dormant": round(dormant_count / total_count * 100, 1),
        "avg_touchpoints_per_month": avg_per_month,
    }), 200


# ---------------------------------------------------------------------------
# Outreach Analytics
# ---------------------------------------------------------------------------

@bp.route("/api/crm/outreach-stats", methods=["GET"])
def outreach_stats():
    """Response rates by channel, by relationship stage, by message type."""
    by_channel = db.query(
        """
        SELECT channel,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE response_received = TRUE) AS responses,
               ROUND(
                   COUNT(*) FILTER (WHERE response_received = TRUE)::NUMERIC
                   / NULLIF(COUNT(*), 0) * 100, 1
               ) AS response_rate_pct
        FROM outreach_messages
        WHERE direction = 'outbound'
        GROUP BY channel
        ORDER BY response_rate_pct DESC NULLS LAST
        """
    )

    by_stage = db.query(
        """
        SELECT c.relationship_stage,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE om.response_received = TRUE) AS responses,
               ROUND(
                   COUNT(*) FILTER (WHERE om.response_received = TRUE)::NUMERIC
                   / NULLIF(COUNT(*), 0) * 100, 1
               ) AS response_rate_pct
        FROM outreach_messages om
        JOIN contacts c ON c.id = om.contact_id
        WHERE om.direction = 'outbound'
        GROUP BY c.relationship_stage
        ORDER BY response_rate_pct DESC NULLS LAST
        """
    )

    by_type = db.query(
        """
        SELECT message_type,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE response_received = TRUE) AS responses,
               ROUND(
                   COUNT(*) FILTER (WHERE response_received = TRUE)::NUMERIC
                   / NULLIF(COUNT(*), 0) * 100, 1
               ) AS response_rate_pct
        FROM outreach_messages
        WHERE direction = 'outbound'
        GROUP BY message_type
        ORDER BY response_rate_pct DESC NULLS LAST
        """
    )

    return jsonify({
        "by_channel": by_channel,
        "by_relationship_stage": by_stage,
        "by_message_type": by_type,
    }), 200


@bp.route("/api/crm/outreach-history/<int:contact_id>", methods=["GET"])
def outreach_history(contact_id):
    """All outreach to a contact with responses."""
    contact = db.query_one("SELECT id, name, company FROM contacts WHERE id = %s", (contact_id,))
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    rows = db.query(
        """
        SELECT id, channel, direction, message_type, subject, body,
               sent_at, response_received, follow_up_date, status, notes, created_at
        FROM outreach_messages
        WHERE contact_id = %s
        ORDER BY sent_at DESC NULLS LAST, created_at DESC
        """,
        (contact_id,),
    )
    return jsonify({
        "contact": contact,
        "outreach": rows,
        "total": len(rows),
        "responses": sum(1 for r in rows if r.get("response_received")),
    }), 200


# ---------------------------------------------------------------------------
# Relationship Scoring Algorithm (Batch Recalculate)
# ---------------------------------------------------------------------------

STAGE_WEIGHTS = {
    "close": 1.2,
    "active": 1.0,
    "warm": 0.8,
    "cold": 0.5,
    "dormant": 0.3,
}


@bp.route("/api/crm/recalculate-scores", methods=["POST"])
def recalculate_all_scores():
    """Recalculate health scores for ALL contacts using a multi-factor algorithm.

    Factors:
        1. Recency of last touchpoint (exponential decay, half-life = 30 days)
        2. Touchpoint frequency (monthly average over last 90 days)
        3. Relationship stage weight
        4. Response rate to outbound outreach
    """
    contacts = db.query(
        """
        SELECT c.id, c.relationship_stage
        FROM contacts c
        WHERE c.merged_into_id IS NULL
        """
    )

    if not contacts:
        return jsonify({"updated": 0, "message": "No contacts to score"}), 200

    contact_ids = [c["id"] for c in contacts]
    stage_map = {c["id"]: c.get("relationship_stage", "cold") for c in contacts}

    # Gather touchpoint stats for all contacts in one query
    tp_stats = db.query(
        """
        SELECT
            contact_id,
            EXTRACT(EPOCH FROM (NOW() - MAX(logged_at))) / 86400 AS days_since_last,
            COUNT(*) FILTER (WHERE logged_at >= NOW() - INTERVAL '90 days') AS count_90d,
            COUNT(*) AS total_touchpoints
        FROM touchpoints
        WHERE contact_id = ANY(%s)
        GROUP BY contact_id
        """,
        (contact_ids,),
    )
    tp_map = {r["contact_id"]: r for r in tp_stats}

    # Gather outreach response rates
    outreach_stats = db.query(
        """
        SELECT
            contact_id,
            COUNT(*) AS outbound_count,
            COUNT(*) FILTER (WHERE response_received = TRUE) AS response_count
        FROM outreach_messages
        WHERE contact_id = ANY(%s) AND direction = 'outbound'
        GROUP BY contact_id
        """,
        (contact_ids,),
    )
    outreach_map = {r["contact_id"]: r for r in outreach_stats}

    updated = []
    half_life = 30.0  # days

    for cid in contact_ids:
        tp = tp_map.get(cid, {})
        om = outreach_map.get(cid, {})
        stage = stage_map.get(cid, "cold")

        days_since = tp.get("days_since_last")
        count_90d = tp.get("count_90d", 0) or 0
        outbound = om.get("outbound_count", 0) or 0
        responses = om.get("response_count", 0) or 0

        # Factor 1: Recency (exponential decay, 0-40 points)
        if days_since is not None:
            recency_score = 40.0 * math.exp(-0.693 * float(days_since) / half_life)
        else:
            recency_score = 0.0

        # Factor 2: Frequency (monthly average over 90 days, 0-25 points)
        monthly_avg = float(count_90d) / 3.0
        frequency_score = min(25.0, monthly_avg * 8.0)

        # Factor 3: Stage weight (0-20 points)
        stage_weight = STAGE_WEIGHTS.get(stage, 0.5)
        stage_score = 20.0 * stage_weight

        # Factor 4: Response rate (0-15 points)
        if outbound > 0:
            response_rate = float(responses) / float(outbound)
            response_score = 15.0 * response_rate
        else:
            response_score = 7.5  # neutral if no outreach

        # Combine and clamp
        total = recency_score + frequency_score + stage_score + response_score
        total = max(0.0, min(100.0, round(total, 1)))

        db.execute(
            "UPDATE contacts SET health_score = %s, updated_at = NOW() WHERE id = %s",
            (total, cid),
        )
        updated.append({"id": cid, "health_score": total})

    return jsonify({
        "updated": len(updated),
        "scores": updated[:50],  # return first 50 for review
        "message": f"Recalculated health scores for {len(updated)} contacts",
    }), 200


# ---------------------------------------------------------------------------
# Networking Event Tracking
# ---------------------------------------------------------------------------

@bp.route("/api/crm/events", methods=["POST"])
def create_networking_event():
    """Log a networking event (conference, meetup, coffee chat, etc.).

    Body JSON:
        event_name (required): name of the event
        event_type: conference | meetup | coffee_chat | webinar | career_fair | other
        event_date: date of event (YYYY-MM-DD)
        location: where it happened
        notes: any notes about the event
        contact_ids: optional array of contact IDs to attach as attendees
    """
    data = request.get_json(force=True)
    name = data.get("event_name")
    if not name:
        return jsonify({"error": "event_name is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO networking_events (event_name, event_type, event_date, location, notes)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            name,
            data.get("event_type", "other"),
            data.get("event_date"),
            data.get("location"),
            data.get("notes"),
        ),
    )

    # Optionally attach contacts as attendees
    contact_ids = data.get("contact_ids", [])
    attendees_added = 0
    if contact_ids and isinstance(contact_ids, list):
        for cid in contact_ids:
            try:
                db.execute(
                    """INSERT INTO networking_event_attendees (event_id, contact_id)
                       VALUES (%s, %s) ON CONFLICT DO NOTHING""",
                    (row["id"], cid),
                )
                attendees_added += 1
            except Exception:
                pass

    return jsonify({**row, "attendees_added": attendees_added}), 201


@bp.route("/api/crm/events", methods=["GET"])
def list_networking_events():
    """List networking events with attendee contacts.

    Query params:
        event_type (optional): filter by type
        limit (int, default 50): max results
    """
    event_type = request.args.get("event_type")
    limit = int(request.args.get("limit", 50))

    clauses, params = [], []
    if event_type:
        clauses.append("e.event_type = %s")
        params.append(event_type)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    events = db.query(
        f"""
        SELECT e.*,
               COALESCE(
                   json_agg(
                       json_build_object(
                           'contact_id', c.id,
                           'name', c.name,
                           'company', c.company,
                           'title', c.title
                       )
                   ) FILTER (WHERE c.id IS NOT NULL),
                   '[]'::json
               ) AS attendees,
               COUNT(c.id) AS attendee_count
        FROM networking_events e
        LEFT JOIN networking_event_attendees nea ON nea.event_id = e.id
        LEFT JOIN contacts c ON c.id = nea.contact_id
        {where}
        GROUP BY e.id
        ORDER BY e.event_date DESC NULLS LAST, e.created_at DESC
        LIMIT %s
        """,
        params,
    )

    return jsonify({"events": events, "count": len(events)}), 200


# ---------------------------------------------------------------------------
# Activity Feed
# ---------------------------------------------------------------------------

@bp.route("/api/crm/activity-feed", methods=["GET"])
def activity_feed():
    """Recent CRM activity: touchpoints, stage changes, tasks completed - chronologically.

    Query params:
        limit (int, default 50): max events
        days (int, default 30): look-back window
    """
    limit = int(request.args.get("limit", 50))
    days = int(request.args.get("days", 30))
    events = []

    # Recent touchpoints
    for r in db.query(
        """SELECT t.id, t.contact_id, t.type, t.channel, t.direction, t.notes, t.logged_at,
                  c.name AS contact_name, c.company AS contact_company
           FROM touchpoints t
           JOIN contacts c ON c.id = t.contact_id
           WHERE t.logged_at >= NOW() - %s * INTERVAL '1 day'
           ORDER BY t.logged_at DESC LIMIT %s""",
        (days, limit),
    ) or []:
        events.append({"event_type": "touchpoint", "date": r["logged_at"],
                        "contact_name": r["contact_name"], "company": r.get("contact_company"),
                        "detail": f"{r['type']} via {r.get('channel', 'unknown')} ({r.get('direction', '')})",
                        "notes": r.get("notes")})

    # Recently completed tasks
    for r in db.query(
        """SELECT nt.id, nt.title, nt.task_type, nt.completed_at,
                  c.name AS contact_name, c.company AS contact_company
           FROM networking_tasks nt
           JOIN contacts c ON c.id = nt.contact_id
           WHERE nt.completed = TRUE AND nt.completed_at >= NOW() - %s * INTERVAL '1 day'
           ORDER BY nt.completed_at DESC LIMIT %s""",
        (days, limit),
    ) or []:
        events.append({"event_type": "task_completed", "date": r["completed_at"],
                        "contact_name": r["contact_name"], "company": r.get("contact_company"),
                        "detail": f"Task completed: {r['title']}"})

    # Recently completed CRM tasks
    for r in db.query(
        """SELECT ct.id, ct.task_type, ct.description, ct.completed_at,
                  c.name AS contact_name, c.company AS contact_company
           FROM crm_tasks ct
           LEFT JOIN contacts c ON c.id = ct.contact_id
           WHERE ct.status = 'completed' AND ct.completed_at >= NOW() - %s * INTERVAL '1 day'
           ORDER BY ct.completed_at DESC LIMIT %s""",
        (days, limit),
    ) or []:
        events.append({"event_type": "crm_task_completed", "date": r["completed_at"],
                        "contact_name": r.get("contact_name"), "company": r.get("contact_company"),
                        "detail": f"CRM task: {r.get('description', r['task_type'])}"})

    events.sort(key=lambda e: str(e.get("date") or ""), reverse=True)
    return jsonify({"activity": events[:limit], "count": min(len(events), limit)}), 200


# ---------------------------------------------------------------------------
# Bulk Touchpoint
# ---------------------------------------------------------------------------

@bp.route("/api/crm/bulk-touchpoint", methods=["POST"])
def bulk_touchpoint():
    """Log the same touchpoint for multiple contacts (e.g., 'met at conference').

    Body JSON:
        contact_ids (list[int]): contacts to log for
        type (str): touchpoint type (meeting, email, call, etc.)
        channel (str, optional): communication channel
        direction (str, optional): inbound/outbound
        notes (str, optional): shared notes
    """
    data = request.get_json(force=True)
    contact_ids = data.get("contact_ids", [])
    tp_type = data.get("type")

    if not contact_ids or not isinstance(contact_ids, list):
        return jsonify({"error": "contact_ids array is required"}), 400
    if not tp_type:
        return jsonify({"error": "type is required"}), 400

    logged = []
    not_found = []
    for cid in contact_ids:
        contact = db.query_one("SELECT id, name FROM contacts WHERE id = %s", (cid,))
        if not contact:
            not_found.append(cid)
            continue

        row = db.execute_returning(
            """INSERT INTO touchpoints (contact_id, type, channel, direction, notes)
               VALUES (%s, %s, %s, %s, %s) RETURNING id, contact_id""",
            (cid, tp_type, data.get("channel", "in_person"), data.get("direction", "outbound"), data.get("notes")),
        )
        db.execute(
            "UPDATE contacts SET last_touchpoint_at = NOW(), last_contact = CURRENT_DATE, updated_at = NOW() WHERE id = %s",
            (cid,),
        )
        logged.append({"contact_id": cid, "contact_name": contact["name"], "touchpoint_id": row["id"]})

    return jsonify({
        "logged_count": len(logged),
        "logged": logged,
        "not_found": not_found,
        "touchpoint_type": tp_type,
    }), 201


@bp.route("/api/crm/events/<int:event_id>/attendees", methods=["POST"])
def add_event_attendees(event_id):
    """Add contacts as attendees to a networking event.

    Body JSON: {"contact_ids": [int, ...]}
    """
    event = db.query_one("SELECT id FROM networking_events WHERE id = %s", (event_id,))
    if not event:
        return jsonify({"error": "Event not found"}), 404

    data = request.get_json(force=True)
    contact_ids = data.get("contact_ids", [])
    if not contact_ids or not isinstance(contact_ids, list):
        return jsonify({"error": "contact_ids array is required"}), 400

    added = []
    already_exists = []
    not_found = []

    for cid in contact_ids:
        contact = db.query_one("SELECT id, name FROM contacts WHERE id = %s", (cid,))
        if not contact:
            not_found.append(cid)
            continue

        existing = db.query_one(
            "SELECT id FROM networking_event_attendees WHERE event_id = %s AND contact_id = %s",
            (event_id, cid),
        )
        if existing:
            already_exists.append(cid)
            continue

        db.execute(
            "INSERT INTO networking_event_attendees (event_id, contact_id) VALUES (%s, %s)",
            (event_id, cid),
        )
        added.append({"contact_id": cid, "name": contact["name"]})

    return jsonify({
        "event_id": event_id,
        "added": added,
        "added_count": len(added),
        "already_existed": already_exists,
        "not_found": not_found,
    }), 201


# ---------------------------------------------------------------------------
# Outreach Generation
# ---------------------------------------------------------------------------

OUTREACH_TEMPLATES = {
    "cold": {
        "subject": "Connecting re: {role} at {company}",
        "body": (
            "Hi {name},\n\n"
            "I came across your profile and wanted to reach out. "
            "I'm exploring opportunities in the {company} space and would love "
            "to learn more about what your team is working on.\n\n"
            "Would you have 15 minutes for a quick chat?\n\n"
            "Best,\nStephen"
        ),
        "channel": "email",
    },
    "warm": {
        "subject": "Great catching up — {company}",
        "body": (
            "Hi {name},\n\n"
            "It was great connecting recently. I've been following what "
            "{company} has been up to and I'm really impressed.\n\n"
            "I'd love to hear more about your experience there and explore "
            "whether there might be a fit for someone with my background.\n\n"
            "Let me know if you have time this week.\n\n"
            "Cheers,\nStephen"
        ),
        "channel": "email",
    },
    "follow_up": {
        "subject": "Following up — {company}",
        "body": (
            "Hi {name},\n\n"
            "Just wanted to follow up on my earlier message. I understand "
            "you're busy... no rush at all. If the timing works better down "
            "the road, I'm happy to reconnect then.\n\n"
            "Thanks,\nStephen"
        ),
        "channel": "email",
    },
}


@bp.route("/api/crm/generate-outreach", methods=["POST"])
def generate_outreach():
    """Generate a template-based outreach message for a contact.

    Body JSON:
        contact_id (int, required): ID of the contact
        type (str): "cold", "warm", or "follow_up" (default: "cold")

    Returns: {outreach: {subject, body, channel}}
    """
    data = request.get_json(force=True)
    contact_id = data.get("contact_id")
    outreach_type = data.get("type", "cold")

    if not contact_id:
        return jsonify({"error": "contact_id is required"}), 400

    if outreach_type not in OUTREACH_TEMPLATES:
        return jsonify({"error": f"Invalid type '{outreach_type}'. Use: cold, warm, follow_up"}), 400

    contact = db.query_one(
        "SELECT id, name, company, title, relationship_stage FROM contacts WHERE id = %s",
        (contact_id,),
    )
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    name = (contact.get("name") or "there").split()[0]  # first name
    company = contact.get("company") or "your company"
    role = contact.get("title") or "your team"

    template = OUTREACH_TEMPLATES[outreach_type]
    outreach = {
        "subject": template["subject"].format(name=name, company=company, role=role),
        "body": template["body"].format(name=name, company=company, role=role),
        "channel": template["channel"],
    }

    return jsonify({"outreach": outreach}), 200
