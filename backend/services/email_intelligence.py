"""Email Intelligence pipeline.

Processes email scan results into notifications, application status updates,
and ghosted-application detection.
"""

import db
from ai_providers.router import route_inference


# Maps email scan_status categories to application status + notification config
STATUS_MAP = {
    "rejection": {
        "app_status": "Rejected",
        "notif_type": "status_change",
        "notif_severity": "action_needed",
        "title_tpl": "Rejection from {company}",
        "body_tpl": "Your application for {role} at {company} was declined.",
    },
    "interview": {
        "app_status": "Interviewing",
        "notif_type": "interview_scheduled",
        "notif_severity": "action_needed",
        "title_tpl": "Interview signal from {company}",
        "body_tpl": "An interview-related email was detected for {role} at {company}. Check your inbox for scheduling details.",
    },
    "offer": {
        "app_status": "Offer",
        "notif_type": "offer_received",
        "notif_severity": "urgent",
        "title_tpl": "Possible offer from {company}",
        "body_tpl": "An offer-related email was detected for {role} at {company}. Review the email immediately.",
    },
    "confirmation": {
        "app_status": "Applied",
        "notif_type": "application_confirmed",
        "notif_severity": "info",
        "title_tpl": "Application confirmed at {company}",
        "body_tpl": "Your application for {role} at {company} has been confirmed received.",
    },
}

# Only upgrade status in certain directions to avoid rolling back progress
STATUS_PRIORITY = {
    "Saved": 0,
    "Applied": 1,
    "Interviewing": 2,
    "Offer": 3,
    "Rejected": -1,  # always apply rejections
}

GHOSTED_THRESHOLD_DAYS = 14


def process_email_scan_results():
    """Find newly categorized emails and create notifications + update applications.

    Returns:
        dict with counts of notifications created and applications updated.
    """
    categorized = db.query(
        """
        SELECT e.id, e.scan_status, e.application_id, e.subject, e.from_name,
               a.company_name, a.role, a.status AS app_status, a.id AS app_id
        FROM emails e
        LEFT JOIN applications a ON a.id = e.application_id
        WHERE e.auto_categorized = TRUE
          AND e.scan_status IN ('rejection', 'interview', 'offer', 'confirmation')
          AND e.id NOT IN (
              SELECT entity_id FROM notifications
              WHERE entity_type = 'email' AND entity_id IS NOT NULL
          )
        ORDER BY e.date DESC
        """
    )

    notifications_created = 0
    applications_updated = 0

    for email in categorized:
        category = email["scan_status"]
        config = STATUS_MAP.get(category)
        if not config:
            continue

        company = email.get("company_name") or email.get("from_name") or "Unknown"
        role = email.get("role") or "Unknown Role"
        app_id = email.get("app_id")

        # Update application status if linked
        if app_id:
            current_status = email.get("app_status") or ""
            new_status = config["app_status"]
            current_priority = STATUS_PRIORITY.get(current_status, -99)
            new_priority = STATUS_PRIORITY.get(new_status, -99)

            # Apply rejection always; otherwise only upgrade
            should_update = (
                new_status == "Rejected"
                or new_priority > current_priority
            )

            if should_update and current_status != new_status:
                db.execute(
                    """
                    UPDATE applications
                    SET status = %s, last_status_change = NOW()
                    WHERE id = %s
                    """,
                    (new_status, app_id),
                )
                # Log status history
                db.execute(
                    """
                    INSERT INTO application_status_history
                        (application_id, old_status, new_status, notes)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (app_id, current_status, new_status,
                     f"Auto-updated by email intelligence (email #{email['id']})"),
                )
                applications_updated += 1

        # Create notification
        title = config["title_tpl"].format(company=company, role=role)
        body = config["body_tpl"].format(company=company, role=role)
        link = f"/pipeline/{app_id}" if app_id else None

        db.execute_returning(
            """
            INSERT INTO notifications
                (type, severity, title, body, link, entity_type, entity_id)
            VALUES (%s, %s, %s, %s, %s, 'email', %s)
            RETURNING id
            """,
            (config["notif_type"], config["notif_severity"],
             title, body, link, email["id"]),
        )
        notifications_created += 1

    python_result = {
        "emails_processed": len(categorized),
        "notifications_created": notifications_created,
        "applications_updated": applications_updated,
    }

    def _python_email_proc(ctx):
        return ctx["r"]

    def _ai_email_proc(ctx):
        from ai_providers import get_provider
        provider = get_provider()
        result = provider.generate_content("email_intelligence_summary", {
            "processed": ctx["r"]["emails_processed"],
            "notifications": ctx["r"]["notifications_created"],
            "updated": ctx["r"]["applications_updated"],
        })
        base = ctx["r"]
        base["ai_summary"] = result.get("content", "")
        return base

    return route_inference(
        task="process_email_scan_results",
        context={"r": python_result},
        python_fallback=_python_email_proc,
        ai_handler=_ai_email_proc,
    )


def detect_ghosted_applications():
    """Find applications that appear ghosted (no activity for 14+ days).

    Criteria:
    - Status is Applied or Interviewing
    - applied_at/updated_at is > 14 days ago
    - No email activity for that company in last 14 days

    Returns:
        dict with ghosted list and notification count.
    """
    stale = db.query(
        """
        SELECT a.id, a.company_name, a.role, a.status,
               a.date_applied, a.last_status_change, a.updated_at,
               EXTRACT(DAY FROM NOW() - COALESCE(a.last_status_change, a.date_applied::timestamp)) AS days_stale
        FROM applications a
        WHERE a.status IN ('Applied', 'Interviewing')
          AND COALESCE(a.last_status_change, a.date_applied::timestamp)
              < NOW() - INTERVAL '%s days'
        ORDER BY days_stale DESC
        """,
        (GHOSTED_THRESHOLD_DAYS,),
    )

    if not stale:
        return {"ghosted": [], "notifications_created": 0}

    ghosted = []
    notifications_created = 0

    for app in stale:
        # Check for recent email activity with this company
        company = app.get("company_name") or ""
        if not company:
            continue

        recent_email = db.query_one(
            """
            SELECT id FROM emails
            WHERE (application_id = %s
                   OR from_address ILIKE %s
                   OR from_name ILIKE %s
                   OR subject ILIKE %s)
              AND date > NOW() - INTERVAL '%s days'
            LIMIT 1
            """,
            (app["id"], f"%{company}%", f"%{company}%",
             f"%{company}%", GHOSTED_THRESHOLD_DAYS),
        )

        if recent_email:
            continue  # has recent email activity, not ghosted

        ghosted.append({
            "application_id": app["id"],
            "company_name": company,
            "role": app.get("role"),
            "status": app["status"],
            "days_stale": int(app.get("days_stale") or 0),
        })

        # Check if we already created a ghosted warning for this app recently
        existing = db.query_one(
            """
            SELECT id FROM notifications
            WHERE type = 'ghosted_warning'
              AND entity_type = 'application'
              AND entity_id = %s
              AND created_at > NOW() - INTERVAL '7 days'
            """,
            (app["id"],),
        )
        if existing:
            continue  # don't spam repeat warnings

        days = int(app.get("days_stale") or GHOSTED_THRESHOLD_DAYS)
        role = app.get("role") or "Unknown Role"

        db.execute_returning(
            """
            INSERT INTO notifications
                (type, severity, title, body, link, entity_type, entity_id)
            VALUES (%s, %s, %s, %s, %s, 'application', %s)
            RETURNING id
            """,
            (
                "ghosted_warning",
                "action_needed",
                f"No response from {company} in {days} days",
                f"Your {role} application at {company} has had no activity for {days} days. "
                f"Consider sending a follow-up or moving on.",
                f"/pipeline/{app['id']}",
                app["id"],
            ),
        )
        notifications_created += 1

    return {
        "ghosted": ghosted,
        "notifications_created": notifications_created,
    }


def get_scan_stats():
    """Return email scan statistics.

    Returns:
        dict with total emails, scanned count, and categorized breakdown.
    """
    total = db.query_one("SELECT COUNT(*) AS count FROM emails")
    scanned = db.query_one(
        "SELECT COUNT(*) AS count FROM emails WHERE scan_status IS NOT NULL AND scan_status != 'unscanned'"
    )
    breakdown = db.query(
        """
        SELECT scan_status, COUNT(*) AS count
        FROM emails
        WHERE scan_status IS NOT NULL AND scan_status != 'unscanned'
        GROUP BY scan_status
        ORDER BY count DESC
        """
    )
    unlinked = db.query_one(
        "SELECT COUNT(*) AS count FROM emails WHERE application_id IS NULL AND auto_categorized = TRUE"
    )

    return {
        "total_emails": total["count"] if total else 0,
        "scanned": scanned["count"] if scanned else 0,
        "unlinked_categorized": unlinked["count"] if unlinked else 0,
        "breakdown": {row["scan_status"]: row["count"] for row in breakdown},
    }


def run_full_pipeline():
    """Orchestrate the full email intelligence pipeline.

    Steps:
    1. Scan emails for status signals (via the MCP tool's logic inlined here)
    2. Process scan results into notifications + app status updates
    3. Detect ghosted applications
    4. Return combined summary

    Returns:
        dict with scan, processing, and ghosted results.
    """
    # Step 1: Scan emails (reuse the scan logic from mcp_tools_search_intel)
    from mcp_tools_search_intel import scan_emails_for_status
    scan_result = scan_emails_for_status()

    # Step 2: Process results into notifications + app updates
    process_result = process_email_scan_results()

    # Step 3: Detect ghosted applications
    ghosted_result = detect_ghosted_applications()

    return {
        "scan": scan_result,
        "processing": process_result,
        "ghosted": {
            "count": len(ghosted_result["ghosted"]),
            "notifications_created": ghosted_result["notifications_created"],
            "applications": ghosted_result["ghosted"],
        },
    }
