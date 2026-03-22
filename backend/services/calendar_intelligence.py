"""Calendar Intelligence service.

Processes calendar event data to detect upcoming interviews, match them to
applications, create/update interview records, and generate notifications.

Calendar events are posted by Claude after calling the Google Calendar MCP
tools -- the backend cannot call those tools directly.
"""

import re
import db


# Keywords that signal a calendar event is likely an interview
INTERVIEW_KEYWORDS = [
    "interview",
    "phone screen",
    "technical",
    "panel",
    "onsite",
    "culture fit",
    "hiring manager",
    "recruiter call",
    "final round",
    "coding challenge",
    "take home",
    "assessment",
]

# Pre-compile a single regex for keyword detection
_KW_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in INTERVIEW_KEYWORDS),
    re.IGNORECASE,
)


def _looks_like_interview(event: dict) -> bool:
    """Return True if the event title or description contains interview keywords."""
    text = " ".join(
        filter(None, [event.get("title", ""), event.get("description", "")])
    )
    return bool(_KW_PATTERN.search(text))


def _fuzzy_match_application(event: dict) -> dict | None:
    """Try to match a calendar event to an existing application by company name.

    Checks event title, description, attendees, and location against the
    company_name column in applications (case-insensitive substring match).
    Returns the application row or None.
    """
    # Gather searchable text from the event
    search_parts = [
        event.get("title", ""),
        event.get("description", ""),
        event.get("location", ""),
    ]
    attendees = event.get("attendees") or []
    for att in attendees:
        if isinstance(att, dict):
            search_parts.append(att.get("email", ""))
            search_parts.append(att.get("displayName", ""))
        elif isinstance(att, str):
            search_parts.append(att)

    search_text = " ".join(filter(None, search_parts)).lower()
    if not search_text.strip():
        return None

    # Get active applications and check for substring match
    apps = db.query(
        """
        SELECT id, company_name, role, status
        FROM applications
        WHERE status NOT IN ('Rejected', 'Withdrawn', 'Closed')
        ORDER BY updated_at DESC
        """
    )

    for app in apps:
        company = (app.get("company_name") or "").strip()
        if not company:
            continue
        # Simple case-insensitive substring match
        if company.lower() in search_text:
            return app

    return None


def _extract_interview_type(title: str) -> str:
    """Infer interview type from the event title."""
    title_lower = title.lower()
    type_map = {
        "phone screen": "Phone Screen",
        "recruiter call": "Phone Screen",
        "technical": "Technical",
        "coding challenge": "Technical",
        "take home": "Take Home",
        "assessment": "Assessment",
        "panel": "Panel",
        "onsite": "Onsite",
        "culture fit": "Culture Fit",
        "hiring manager": "Hiring Manager",
        "final round": "Final Round",
    }
    for keyword, interview_type in type_map.items():
        if keyword in title_lower:
            return interview_type
    return "Interview"


def _extract_interviewers(event: dict) -> list[str]:
    """Pull interviewer names from attendees, excluding the candidate."""
    attendees = event.get("attendees") or []
    names = []
    for att in attendees:
        if isinstance(att, dict):
            # Skip the event organiser / self if flagged
            if att.get("self"):
                continue
            name = att.get("displayName") or att.get("email", "")
            if name:
                names.append(name)
        elif isinstance(att, str):
            names.append(att)
    return names


def detect_interviews(events: list[dict]) -> dict:
    """Process a list of calendar events, detecting interviews.

    Each event dict should contain:
        title, start, end, attendees, description, location, event_id

    Returns:
        dict with matched/unmatched interview counts and details.
    """
    matched = []
    unmatched = []
    skipped = 0

    for event in events:
        if not _looks_like_interview(event):
            skipped += 1
            continue

        event_id = event.get("event_id") or event.get("id")
        title = event.get("title", "")
        start = event.get("start")
        interviewers = _extract_interviewers(event)
        interview_type = _extract_interview_type(title)

        app = _fuzzy_match_application(event)

        if app:
            # --- Matched to an application ---
            app_id = app["id"]
            company = app["company_name"]
            role = app.get("role") or "Unknown Role"

            # Upsert interview record (dedup on calendar_event_id)
            existing_interview = None
            if event_id:
                existing_interview = db.query_one(
                    "SELECT id FROM interviews WHERE calendar_event_id = %s",
                    (str(event_id),),
                )

            if existing_interview:
                # Update existing
                db.execute(
                    """
                    UPDATE interviews
                    SET date = %s, type = %s, interviewers = %s, notes = %s
                    WHERE id = %s
                    """,
                    (start, interview_type, interviewers,
                     event.get("description"), existing_interview["id"]),
                )
                interview_id = existing_interview["id"]
            else:
                # Check unique constraint (application_id, date) before insert
                if start:
                    dup = db.query_one(
                        "SELECT id FROM interviews WHERE application_id = %s AND date = %s",
                        (app_id, start),
                    )
                    if dup:
                        interview_id = dup["id"]
                        db.execute(
                            """
                            UPDATE interviews
                            SET type = %s, interviewers = %s,
                                calendar_event_id = %s, notes = %s
                            WHERE id = %s
                            """,
                            (interview_type, interviewers,
                             str(event_id) if event_id else None,
                             event.get("description"), dup["id"]),
                        )
                    else:
                        row = db.execute_returning(
                            """
                            INSERT INTO interviews
                                (application_id, date, type, interviewers,
                                 calendar_event_id, notes)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING id
                            """,
                            (app_id, start, interview_type, interviewers,
                             str(event_id) if event_id else None,
                             event.get("description")),
                        )
                        interview_id = row["id"]
                else:
                    row = db.execute_returning(
                        """
                        INSERT INTO interviews
                            (application_id, type, interviewers,
                             calendar_event_id, notes)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (app_id, interview_type, interviewers,
                         str(event_id) if event_id else None,
                         event.get("description")),
                    )
                    interview_id = row["id"]

            # Upgrade application status to Interviewing if not already further
            if app.get("status") in ("Saved", "Applied"):
                db.execute(
                    "UPDATE applications SET status = 'Interviewing', last_status_change = NOW() WHERE id = %s",
                    (app_id,),
                )

            # Create notification (dedup: same entity_id + type)
            existing_notif = db.query_one(
                """
                SELECT id FROM notifications
                WHERE type = 'interview_detected'
                  AND entity_type = 'interview'
                  AND entity_id = %s
                """,
                (interview_id,),
            )
            if not existing_notif:
                db.execute_returning(
                    """
                    INSERT INTO notifications
                        (type, severity, title, body, link, entity_type, entity_id)
                    VALUES (%s, %s, %s, %s, %s, 'interview', %s)
                    RETURNING id
                    """,
                    (
                        "interview_detected",
                        "action_needed",
                        f"Interview detected: {company} - {interview_type}",
                        f"{interview_type} for {role} at {company} on {start or 'TBD'}.",
                        f"/pipeline/{app_id}",
                        interview_id,
                    ),
                )

            matched.append({
                "event_title": title,
                "company": company,
                "role": role,
                "interview_type": interview_type,
                "interview_id": interview_id,
                "application_id": app_id,
                "date": start,
            })

        else:
            # --- Unmatched: no application found ---
            # Create notification suggesting user link it
            # Dedup on event_id stored in body
            dedup_key = str(event_id) if event_id else title
            existing_notif = db.query_one(
                """
                SELECT id FROM notifications
                WHERE type = 'interview_unmatched'
                  AND body LIKE %s
                """,
                (f"%{dedup_key}%",),
            )
            if not existing_notif:
                db.execute_returning(
                    """
                    INSERT INTO notifications
                        (type, severity, title, body, link, entity_type, entity_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        "interview_unmatched",
                        "action_needed",
                        f"Possible interview: {title}",
                        f"Calendar event \"{title}\" on {start or 'TBD'} looks like an interview "
                        f"but couldn't be matched to an application. Event ID: {dedup_key}",
                        None,
                        None,
                        None,
                    ),
                )

            unmatched.append({
                "event_title": title,
                "date": start,
                "event_id": event_id,
            })

    return {
        "total_events": len(events),
        "interviews_detected": len(matched) + len(unmatched),
        "matched": matched,
        "unmatched": unmatched,
        "skipped_non_interview": skipped,
    }


def get_upcoming_interviews(days: int = 14) -> list:
    """Return interviews scheduled in the next N days, enriched with application data."""
    rows = db.query(
        """
        SELECT i.id, i.application_id, i.date, i.type, i.interviewers,
               i.calendar_event_id, i.outcome, i.notes, i.thank_you_sent,
               a.company_name, a.role, a.status AS app_status
        FROM interviews i
        LEFT JOIN applications a ON a.id = i.application_id
        WHERE i.date >= NOW()
          AND i.date <= NOW() + INTERVAL '%s days'
        ORDER BY i.date ASC
        """,
        (days,),
    )
    return rows


def get_interview_prep_needed() -> list:
    """Return upcoming interviews (next 7 days) that don't have prep notes saved."""
    rows = db.query(
        """
        SELECT i.id, i.application_id, i.date, i.type, i.interviewers,
               a.company_name, a.role
        FROM interviews i
        LEFT JOIN applications a ON a.id = i.application_id
        LEFT JOIN interview_prep p ON p.interview_id = i.id
        WHERE i.date >= NOW()
          AND i.date <= NOW() + INTERVAL '7 days'
          AND p.id IS NULL
        ORDER BY i.date ASC
        """
    )
    return rows
