# Imports needed: from db import db / mcp already defined
# These functions are decorated with @mcp.tool() and registered at module level.
# The orchestrator imports this module and mcp is already defined before import.

from datetime import date, timedelta


@mcp.tool()
def update_relationship_stage(contact_id: int, stage: str) -> dict:
    """Update a contact's relationship stage.

    Args:
        contact_id: Contact ID
        stage: cold, warm, active, close, or dormant

    Returns:
        dict with updated contact info
    """
    valid_stages = {"cold", "warm", "active", "close", "dormant"}
    if stage not in valid_stages:
        return {"error": f"stage must be one of: {', '.join(sorted(valid_stages))}"}

    row = db.execute_returning(
        """
        UPDATE contacts
        SET relationship_stage = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING id, name, company, title, relationship_stage, health_score, updated_at
        """,
        (stage, contact_id),
    )
    if not row:
        return {"error": f"Contact {contact_id} not found"}
    return {"contact": row}


@mcp.tool()
def get_relationship_health(contact_id: int | None = None, limit: int = 20) -> dict:
    """Get contacts ranked by relationship health score (lowest = needs attention).

    Args:
        contact_id: Optional specific contact ID. If None, returns lowest-health contacts.
        limit: Max results (default 20)

    Returns:
        dict with contacts and their health scores
    """
    if contact_id is not None:
        row = db.query_one(
            """
            SELECT id, name, company, title, relationship_stage, health_score,
                   last_touchpoint_at, last_contact, tags
            FROM contacts
            WHERE id = %s
            """,
            (contact_id,),
        )
        if not row:
            return {"error": f"Contact {contact_id} not found"}
        return {"contact": row}

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
    return {"contacts": rows, "count": len(rows)}


@mcp.tool()
def log_touchpoint(
    contact_id: int,
    type: str,
    channel: str = "email",
    direction: str = "outbound",
    notes: str | None = None,
) -> dict:
    """Log a touchpoint (interaction) with a contact. Updates last_touchpoint_at automatically.

    Args:
        contact_id: Contact ID
        type: email, linkedin_message, phone_call, coffee, meeting, event, referral
        channel: linkedin, email, phone, in_person, slack, other
        direction: inbound or outbound
        notes: Optional notes about the interaction

    Returns:
        dict with created touchpoint
    """
    contact = db.query_one("SELECT id FROM contacts WHERE id = %s", (contact_id,))
    if not contact:
        return {"error": f"Contact {contact_id} not found"}

    row = db.execute_returning(
        """
        INSERT INTO touchpoints (contact_id, type, channel, direction, notes)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """,
        (contact_id, type, channel, direction, notes),
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

    return {"touchpoint": row}


@mcp.tool()
def get_networking_tasks(status: str = "pending", days: int = 7) -> dict:
    """Get upcoming networking tasks.

    Args:
        status: 'pending' (incomplete), 'completed', or 'overdue'
        days: For pending, show tasks due within this many days (default 7)

    Returns:
        dict with tasks list
    """
    if status == "completed":
        rows = db.query(
            """
            SELECT nt.id, nt.contact_id, nt.task_type, nt.title, nt.due_date,
                   nt.completed_at, nt.notes, nt.created_at,
                   c.name AS contact_name, c.company AS contact_company
            FROM networking_tasks nt
            JOIN contacts c ON c.id = nt.contact_id
            WHERE nt.completed = TRUE
            ORDER BY nt.completed_at DESC
            LIMIT 50
            """,
        )
    elif status == "overdue":
        today = date.today()
        rows = db.query(
            """
            SELECT nt.id, nt.contact_id, nt.task_type, nt.title, nt.due_date,
                   nt.notes, nt.created_at,
                   c.name AS contact_name, c.company AS contact_company
            FROM networking_tasks nt
            JOIN contacts c ON c.id = nt.contact_id
            WHERE nt.completed = FALSE
              AND nt.due_date < %s
            ORDER BY nt.due_date ASC
            """,
            (today,),
        )
    else:
        # pending — due within N days
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

    return {"tasks": rows, "count": len(rows), "status": status}
