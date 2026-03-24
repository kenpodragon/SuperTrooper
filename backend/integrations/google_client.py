"""
Google Workspace client — direct API calls, credentials from DB.

Uses google-api-python-client + google-auth to call Gmail, Calendar, and
Drive APIs directly. Credentials (OAuth token + client config) stored in
the settings.integrations JSONB column. No files, no subprocess, no MCP
protocol overhead.

The MCP path uses these same functions — they're registered as
SuperTroopers MCP tools in mcp_tools_google.py.
"""

import base64
import json
import logging
from datetime import datetime, timezone
from email.mime.text import MIMEText
from functools import lru_cache

log = logging.getLogger(__name__)


def _get_google_config():
    """Load Google config from settings.integrations JSONB."""
    try:
        import db
        row = db.query_one("SELECT integrations FROM settings WHERE id = 1")
        if row and row.get("integrations"):
            integrations = row["integrations"]
            if isinstance(integrations, str):
                integrations = json.loads(integrations)
            return integrations.get("google", {})
    except Exception as e:
        log.warning("Failed to load Google config: %s", e)
    return {}


def _get_credentials():
    """Build google.oauth2.credentials.Credentials from DB-stored token."""
    config = _get_google_config()
    creds_data = config.get("credentials", {})
    token_data = config.get("token")

    if not creds_data or not token_data:
        return None

    # Extract client config (handles both 'installed' and 'web' wrapper)
    client_config = creds_data.get("installed") or creds_data.get("web") or creds_data
    client_id = client_config.get("client_id")
    client_secret = client_config.get("client_secret")

    if not client_id or not client_secret:
        return None

    try:
        from google.oauth2.credentials import Credentials
        creds = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )
        return creds
    except Exception as e:
        log.error("Failed to build Google credentials: %s", e)
        return None


def _build_service(service_name: str, version: str):
    """Build a Google API service client from DB credentials."""
    creds = _get_credentials()
    if not creds:
        return None
    try:
        from googleapiclient.discovery import build
        return build(service_name, version, credentials=creds)
    except Exception as e:
        log.error("Failed to build Google %s service: %s", service_name, e)
        return None


def is_configured():
    """Check if Google OAuth credentials and token are stored in DB."""
    config = _get_google_config()
    return bool(config.get("credentials")) and bool(config.get("token"))


def health_check() -> dict:
    """Test Google API connectivity by fetching Gmail profile."""
    if not is_configured():
        config = _get_google_config()
        return {
            "status": "setup_required",
            "message": "Google OAuth credentials not found. Use the setup wizard in Settings > Integrations.",
            "credentials_stored": bool(config.get("credentials")),
            "token_stored": bool(config.get("token")),
        }

    try:
        gmail = _build_service("gmail", "v1")
        if not gmail:
            return {"status": "error", "message": "Failed to build Gmail service"}

        profile = gmail.users().getProfile(userId="me").execute()
        return {
            "status": "connected",
            "message": f"Connected as {profile.get('emailAddress')}",
            "email": profile.get("emailAddress"),
            "messages_total": profile.get("messagesTotal"),
        }
    except Exception as e:
        error_msg = str(e)
        if "invalid_grant" in error_msg or "Token has been expired" in error_msg:
            return {"status": "token_expired", "message": "Token expired. Re-run the authorization flow in Settings."}
        return {"status": "error", "message": error_msg[:200]}


# ---------------------------------------------------------------------------
# Gmail
# ---------------------------------------------------------------------------

def gmail_search(query: str, max_results: int = 10) -> dict:
    """Search Gmail messages."""
    gmail = _build_service("gmail", "v1")
    if not gmail:
        return {"error": "Google not configured", "setup_required": True}

    try:
        results = gmail.users().messages().list(
            userId="me", q=query, maxResults=min(max_results, 100),
        ).execute()

        messages = []
        for msg_stub in results.get("messages", []):
            msg = gmail.users().messages().get(
                userId="me", id=msg_stub["id"], format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"],
            ).execute()

            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            messages.append({
                "id": msg["id"],
                "thread_id": msg.get("threadId"),
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "snippet": msg.get("snippet", ""),
                "label_ids": msg.get("labelIds", []),
            })

        return {"messages": messages, "count": len(messages), "query": query}
    except Exception as e:
        log.warning("Gmail search failed: %s", e)
        return {"error": str(e)[:200]}


def gmail_read(message_id: str) -> dict:
    """Read a specific Gmail message with full body."""
    gmail = _build_service("gmail", "v1")
    if not gmail:
        return {"error": "Google not configured", "setup_required": True}

    try:
        msg = gmail.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

        # Extract body text
        body = ""
        payload = msg.get("payload", {})
        if payload.get("body", {}).get("data"):
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
        elif payload.get("parts"):
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                    break

        return {
            "id": msg["id"],
            "thread_id": msg.get("threadId"),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "body": body,
            "snippet": msg.get("snippet", ""),
            "label_ids": msg.get("labelIds", []),
        }
    except Exception as e:
        log.warning("Gmail read failed: %s", e)
        return {"error": str(e)[:200]}


def gmail_draft(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> dict:
    """Create a Gmail draft."""
    gmail = _build_service("gmail", "v1")
    if not gmail:
        return {"error": "Google not configured", "setup_required": True}

    try:
        mime = MIMEText(body)
        mime["To"] = to
        mime["Subject"] = subject
        if cc:
            mime["Cc"] = cc
        if bcc:
            mime["Bcc"] = bcc

        encoded = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        draft = gmail.users().drafts().create(
            userId="me", body={"message": {"raw": encoded}},
        ).execute()

        return {"draft_id": draft["id"], "message_id": draft["message"]["id"], "status": "created"}
    except Exception as e:
        log.warning("Gmail draft failed: %s", e)
        return {"error": str(e)[:200]}


def gmail_update_draft(draft_id: str, to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> dict:
    """Update an existing Gmail draft."""
    gmail = _build_service("gmail", "v1")
    if not gmail:
        return {"error": "Google not configured", "setup_required": True}

    try:
        mime = MIMEText(body)
        mime["To"] = to
        mime["Subject"] = subject
        if cc:
            mime["Cc"] = cc
        if bcc:
            mime["Bcc"] = bcc

        encoded = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        draft = gmail.users().drafts().update(
            userId="me", id=draft_id, body={"message": {"raw": encoded}},
        ).execute()

        return {"draft_id": draft["id"], "message_id": draft["message"]["id"], "status": "updated"}
    except Exception as e:
        log.warning("Gmail draft update failed: %s", e)
        return {"error": str(e)[:200]}


def gmail_send_draft(draft_id: str) -> dict:
    """Send an existing Gmail draft."""
    gmail = _build_service("gmail", "v1")
    if not gmail:
        return {"error": "Google not configured", "setup_required": True}

    try:
        result = gmail.users().drafts().send(
            userId="me", body={"id": draft_id},
        ).execute()

        return {"message_id": result["id"], "thread_id": result.get("threadId"), "status": "sent"}
    except Exception as e:
        log.warning("Gmail send draft failed: %s", e)
        return {"error": str(e)[:200]}


def gmail_delete_draft(draft_id: str) -> dict:
    """Delete a Gmail draft."""
    gmail = _build_service("gmail", "v1")
    if not gmail:
        return {"error": "Google not configured", "setup_required": True}

    try:
        gmail.users().drafts().delete(userId="me", id=draft_id).execute()
        return {"status": "deleted"}
    except Exception as e:
        log.warning("Gmail delete draft failed: %s", e)
        return {"error": str(e)[:200]}


def gmail_send(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> dict:
    """Send an email via Gmail."""
    gmail = _build_service("gmail", "v1")
    if not gmail:
        return {"error": "Google not configured", "setup_required": True}

    try:
        mime = MIMEText(body)
        mime["To"] = to
        mime["Subject"] = subject
        if cc:
            mime["Cc"] = cc
        if bcc:
            mime["Bcc"] = bcc

        encoded = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        result = gmail.users().messages().send(
            userId="me", body={"raw": encoded},
        ).execute()

        return {"message_id": result["id"], "thread_id": result.get("threadId"), "status": "sent"}
    except Exception as e:
        log.warning("Gmail send failed: %s", e)
        return {"error": str(e)[:200]}


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def gcal_list_events(days: int = 14, calendar_id: str = "primary", max_results: int = 50) -> dict:
    """List upcoming calendar events."""
    cal = _build_service("calendar", "v3")
    if not cal:
        return {"error": "Google not configured", "setup_required": True}

    try:
        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        from datetime import timedelta
        time_max = (now + timedelta(days=days)).isoformat()

        results = cal.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = []
        for ev in results.get("items", []):
            start = ev.get("start", {})
            end = ev.get("end", {})
            events.append({
                "id": ev["id"],
                "summary": ev.get("summary", "(No title)"),
                "start": start.get("dateTime") or start.get("date"),
                "end": end.get("dateTime") or end.get("date"),
                "location": ev.get("location"),
                "description": ev.get("description", "")[:200],
                "attendees": [a.get("email") for a in ev.get("attendees", [])],
                "status": ev.get("status"),
                "html_link": ev.get("htmlLink"),
            })

        return {"events": events, "count": len(events), "calendar_id": calendar_id}
    except Exception as e:
        log.warning("Calendar list failed: %s", e)
        return {"error": str(e)[:200]}


def gcal_create_event(
    summary: str, start_time: str, end_time: str,
    description: str = "", location: str = "",
    attendees: list = None, calendar_id: str = "primary",
) -> dict:
    """Create a calendar event."""
    cal = _build_service("calendar", "v3")
    if not cal:
        return {"error": "Google not configured", "setup_required": True}

    try:
        event = {
            "summary": summary,
            "start": {"dateTime": start_time, "timeZone": "UTC"},
            "end": {"dateTime": end_time, "timeZone": "UTC"},
        }
        if description:
            event["description"] = description
        if location:
            event["location"] = location
        if attendees:
            event["attendees"] = [{"email": e} for e in attendees]

        result = cal.events().insert(
            calendarId=calendar_id, body=event, sendUpdates="all",
        ).execute()

        return {
            "event_id": result["id"],
            "html_link": result.get("htmlLink"),
            "status": "created",
        }
    except Exception as e:
        log.warning("Calendar create failed: %s", e)
        return {"error": str(e)[:200]}


# ---------------------------------------------------------------------------
# Drive
# ---------------------------------------------------------------------------

def gdrive_list(query: str = "", max_results: int = 20) -> dict:
    """List or search Google Drive files."""
    drive = _build_service("drive", "v3")
    if not drive:
        return {"error": "Google not configured", "setup_required": True}

    try:
        params = {
            "pageSize": min(max_results, 100),
            "fields": "files(id, name, mimeType, modifiedTime, size, webViewLink)",
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
            "corpora": "user",
        }
        if query:
            params["q"] = query

        results = drive.files().list(**params).execute()
        files = results.get("files", [])

        return {"files": files, "count": len(files), "query": query}
    except Exception as e:
        log.warning("Drive list failed: %s", e)
        return {"error": str(e)[:200]}


def gdrive_upload(file_path: str, name: str = "", folder_id: str = "") -> dict:
    """Upload a file to Google Drive."""
    drive = _build_service("drive", "v3")
    if not drive:
        return {"error": "Google not configured", "setup_required": True}

    try:
        import os
        from googleapiclient.http import MediaFileUpload

        if not name:
            name = os.path.basename(file_path)

        metadata = {"name": name}
        if folder_id:
            metadata["parents"] = [folder_id]

        media = MediaFileUpload(file_path, resumable=True)
        result = drive.files().create(
            body=metadata, media_body=media, fields="id, name, webViewLink",
        ).execute()

        return {
            "file_id": result["id"],
            "name": result["name"],
            "web_link": result.get("webViewLink"),
            "status": "uploaded",
        }
    except Exception as e:
        log.warning("Drive upload failed: %s", e)
        return {"error": str(e)[:200]}


# ---------------------------------------------------------------------------
# People API (Google Contacts)
# ---------------------------------------------------------------------------

def contacts_list(page_size: int = 200, page_token: str = "") -> dict:
    """Fetch contacts from Google People API.

    Returns: {contacts: [{name, email, phone, company, title, linkedin_url}], next_page_token, total}
    """
    people = _build_service("people", "v1")
    if not people:
        return {"error": "Google not configured", "setup_required": True}

    try:
        results = people.people().connections().list(
            resourceName="people/me",
            pageSize=min(page_size, 1000),
            pageToken=page_token or None,
            personFields="names,emailAddresses,phoneNumbers,organizations,urls,biographies",
            sortOrder="LAST_MODIFIED_DESCENDING",
        ).execute()

        contacts = []
        for person in results.get("connections", []):
            names = person.get("names", [])
            emails = person.get("emailAddresses", [])
            phones = person.get("phoneNumbers", [])
            orgs = person.get("organizations", [])
            urls = person.get("urls", [])

            name = names[0].get("displayName", "") if names else ""
            if not name:
                continue

            all_emails = [e.get("value", "").strip().lower() for e in emails if e.get("value", "").strip()]
            email = all_emails[0] if all_emails else ""
            phone = phones[0].get("value", "") if phones else ""
            company = orgs[0].get("name", "") if orgs else ""
            title = orgs[0].get("title", "") if orgs else ""

            # Look for LinkedIn URL
            linkedin_url = ""
            for u in urls:
                val = u.get("value", "")
                if "linkedin.com" in val.lower():
                    linkedin_url = val
                    break

            contacts.append({
                "name": name,
                "email": email,
                "emails": all_emails,
                "phone": phone,
                "company": company,
                "title": title,
                "linkedin_url": linkedin_url,
                "google_resource": person.get("resourceName", ""),
            })

        return {
            "contacts": contacts,
            "next_page_token": results.get("nextPageToken", ""),
            "total": results.get("totalPeople", len(contacts)),
        }
    except Exception as e:
        log.warning("Google Contacts list failed: %s", e)
        return {"error": str(e)[:300]}
