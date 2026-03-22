"""MCP tools for reference management."""

import db


def get_reference_roster():
    """List all references with status, topics, role types, and usage stats."""
    rows = db.query(
        """
        SELECT id, name, company, title, relationship, relationship_strength,
               last_contact, reference_topics, reference_role_types,
               reference_times_used, reference_last_used,
               reference_effectiveness, is_reference, reference_priority
        FROM contacts
        WHERE is_reference = TRUE OR relationship = 'reference'
        ORDER BY reference_priority = 'primary' DESC,
                 relationship_strength = 'strong' DESC,
                 name
        """
    )
    return {"references": rows, "count": len(rows)}


def match_references_to_role(role_type: str):
    """Match references to a given role type, ranked by fit + warmth + usage."""
    if not role_type:
        return {"error": "role_type is required"}

    rows = db.query(
        """
        SELECT id, name, company, title, reference_topics, reference_role_types,
               relationship_strength, reference_times_used, reference_last_used,
               reference_priority, last_contact,
               (%s = ANY(reference_role_types)) AS role_match
        FROM contacts
        WHERE is_reference = TRUE OR relationship = 'reference'
        ORDER BY
            (%s = ANY(reference_role_types)) DESC,
            relationship_strength = 'strong' DESC,
            reference_times_used ASC,
            last_contact DESC NULLS LAST
        """,
        [role_type, role_type],
    )
    return {"role_type": role_type, "matches": rows}


def check_reference_warmth():
    """Return warmth report for all references."""
    rows = db.query(
        """
        SELECT id, name, company, title, relationship_strength, last_contact,
               reference_times_used, reference_priority,
               CASE
                   WHEN last_contact IS NULL THEN NULL
                   ELSE CURRENT_DATE - last_contact
               END AS days_since_contact
        FROM contacts
        WHERE is_reference = TRUE OR relationship = 'reference'
        ORDER BY last_contact ASC NULLS FIRST
        """
    )

    needs_checkin = []
    for row in rows:
        days = row.get("days_since_contact")
        if days is None or days > 90:
            row["warmth_status"] = "cold" if (days and days > 180) else "cooling" if (days and days > 90) else "unknown"
            row["needs_checkin"] = True
            needs_checkin.append(row)
        elif days > 30:
            row["warmth_status"] = "warm"
            row["needs_checkin"] = False
        else:
            row["warmth_status"] = "hot"
            row["needs_checkin"] = False

    return {
        "total_references": len(rows),
        "needing_checkin": len(needs_checkin),
        "references": rows,
    }


def log_reference_use(contact_id: int, application_id: int):
    """Log that a reference was used for an application."""
    if not contact_id or not application_id:
        return {"error": "contact_id and application_id are required"}

    contact = db.query_one("SELECT id, name FROM contacts WHERE id = %s", [contact_id])
    if not contact:
        return {"error": "Contact not found"}

    db.execute_returning(
        """
        UPDATE contacts
        SET reference_times_used = COALESCE(reference_times_used, 0) + 1,
            reference_last_used = CURRENT_DATE,
            updated_at = NOW()
        WHERE id = %s
        RETURNING id
        """,
        [contact_id],
    )

    existing = db.query_one(
        "SELECT id FROM referrals WHERE contact_id = %s AND application_id = %s",
        [contact_id, application_id],
    )
    if not existing:
        db.execute_returning(
            """
            INSERT INTO referrals (contact_id, application_id, referral_date, status)
            VALUES (%s, %s, CURRENT_DATE, 'submitted')
            RETURNING *
            """,
            [contact_id, application_id],
        )

    return {"status": "logged", "contact": contact["name"], "application_id": application_id}
