"""
Emails ETL loader for SuperTroopers.

Loads job-related email data into the emails table from two sources:
  1. JSON files exported from Gmail MCP search results
  2. (Future) Direct Gmail MCP integration

Supports 7,184+ job-related emails across Indeed, LinkedIn, Dice,
ZipRecruiter, Glassdoor, and direct ATS portals.

Auto-categorizes emails: application, rejection, interview, recruiter,
job_alert, status_update, reference.

Attempts to link emails to existing application records by matching
company names in from_address or subject lines.

Usage:
    python load_emails.py load <directory> [--dry-run]
    python load_emails.py load <directory> --category-only
    python load_emails.py load <directory> --link-only
    python load_emails.py status
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print(
        "ERROR: psycopg2-binary not installed. Run: pip install psycopg2-binary",
        file=sys.stderr,
    )
    sys.exit(1)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Batch size for bulk inserts
BATCH_SIZE = 500

# ---------------------------------------------------------------------------
# Known recruiter domains (partial matches against from_address)
# ---------------------------------------------------------------------------
RECRUITER_DOMAINS = [
    "roberthalf.com",
    "hays.com",
    "randstad.com",
    "adecco.com",
    "kforce.com",
    "teksystems.com",
    "insightglobal.com",
    "cybercoders.com",
    "motionrecruitment.com",
    "jeffersonwells.com",
    "spherion.com",
    "modis.com",
    "manpowergroup.com",
    "kellymitchell.com",
    "apexsystems.com",
    "collabera.com",
    "brooksource.com",
    "hirebridge.com",
    "recruitics.com",
    "bullhorn.com",
    "jobvite.com",
    "lever.co",
    "greenhouse.io",
    "icims.com",
    "workday.com",
    "smartrecruiters.com",
    "phenom.com",
]

RECRUITER_KEYWORDS = [
    "recruiter",
    "recruiting",
    "talent acquisition",
    "staffing",
    "headhunter",
    "placement",
]

# ---------------------------------------------------------------------------
# Job alert sender patterns
# ---------------------------------------------------------------------------
JOB_ALERT_SENDERS = [
    "indeedapply@indeed.com",
    "alert@indeed.com",
    "jobs-noreply@linkedin.com",
    "jobs-listings@linkedin.com",
    "invitations@linkedin.com",
    "messages-noreply@linkedin.com",
    "jobs@dice.com",
    "dice@connect.dice.com",
    "noreply@ziprecruiter.com",
    "notification@ziprecruiter.com",
    "jobs-alert@glassdoor.com",
    "glassdoor-apply@indeed.com",
    "noreply@glassdoor.com",
]

# ---------------------------------------------------------------------------
# Categorization patterns (checked against subject + snippet + body)
# ---------------------------------------------------------------------------
CATEGORY_PATTERNS = {
    "rejection": [
        r"not\s+moving\s+forward",
        r"other\s+candidates",
        r"position\s+has\s+been\s+filled",
        r"no\s+longer\s+being\s+considered",
        r"decided\s+not\s+to\s+proceed",
        r"will\s+not\s+be\s+moving\s+forward",
        r"unfortunately",
        r"not\s+selected",
        r"after\s+careful\s+consideration",
        r"we\s+have\s+decided\s+to\s+go",
        r"regret\s+to\s+inform",
        r"won'?t\s+be\s+advancing",
        r"not\s+a\s+match",
        r"position\s+(?:has\s+been\s+)?filled",
    ],
    "interview": [
        r"interview",
        r"schedule\s+(?:a\s+)?(?:call|meeting|chat|time)",
        r"phone\s+screen",
        r"technical\s+assessment",
        r"coding\s+challenge",
        r"meet\s+(?:the\s+)?team",
        r"next\s+step",
        r"panel\s+discussion",
        r"on-?site",
        r"video\s+call",
        r"zoom\s+meeting",
        r"teams\s+meeting",
        r"calendar\s+invite",
        r"availability",
    ],
    "application": [
        r"appli(?:ed|cation)\s+(?:received|submitted|confirmed)",
        r"thank\s+you\s+for\s+(?:your\s+)?appl(?:ying|ication)",
        r"application\s+(?:has\s+been\s+)?received",
        r"we\s+(?:have\s+)?received\s+your\s+application",
        r"successfully\s+(?:applied|submitted)",
        r"you\s+(?:have\s+)?applied",
        r"your\s+application\s+(?:for|to)",
    ],
    "status_update": [
        r"update\s+on\s+your\s+application",
        r"application\s+status",
        r"status\s+update",
        r"your\s+application\s+has\s+been",
        r"application\s+(?:is\s+)?under\s+review",
        r"reviewing\s+your\s+(?:application|resume)",
        r"profile\s+(?:is\s+)?being\s+reviewed",
    ],
}


from db_config import get_db_config


def get_db_connection():
    """Connect to the SuperTroopers PostgreSQL database."""
    return psycopg2.connect(**get_db_config())


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def parse_gmail_date(date_str):
    """Parse an email date string into a datetime object.

    Handles RFC 2822 dates, ISO 8601, and epoch milliseconds (Gmail API).
    """
    if date_str is None:
        return None

    # Epoch milliseconds (Gmail API internalDate)
    if isinstance(date_str, (int, float)):
        try:
            return datetime.utcfromtimestamp(date_str / 1000.0)
        except (ValueError, OSError):
            return None

    if isinstance(date_str, str) and date_str.isdigit():
        try:
            return datetime.utcfromtimestamp(int(date_str) / 1000.0)
        except (ValueError, OSError):
            return None

    # RFC 2822
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass

    # ISO 8601 variants
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def extract_header(headers, name):
    """Extract a header value from a list of Gmail API header dicts."""
    if not headers:
        return None
    name_lower = name.lower()
    for h in headers:
        if isinstance(h, dict) and h.get("name", "").lower() == name_lower:
            return h.get("value")
    return None


def parse_email_record(msg):
    """Parse a single Gmail API message dict into an email record.

    Supports multiple JSON shapes:
      - Full Gmail API message (payload.headers, internalDate, etc.)
      - Simplified/pre-parsed dict with top-level keys
      - Gmail MCP search result format
    """
    # --- Pre-parsed / simplified format ---
    if "gmail_id" in msg or "messageId" in msg:
        gmail_id = msg.get("gmail_id") or msg.get("messageId") or msg.get("id")
        thread_id = msg.get("thread_id") or msg.get("threadId")
        date = parse_gmail_date(
            msg.get("date") or msg.get("internalDate")
        )
        from_raw = msg.get("from_address") or msg.get("from") or ""
        from_name, from_address = parseaddr(from_raw) if "@" in from_raw else (from_raw, from_raw)
        if not from_name:
            from_name = msg.get("from_name")
        to_address = msg.get("to_address") or msg.get("to") or ""
        subject = msg.get("subject") or ""
        snippet = msg.get("snippet") or ""
        body = msg.get("body") or ""
        labels = msg.get("labels") or msg.get("labelIds") or []

        return {
            "gmail_id": str(gmail_id) if gmail_id else None,
            "thread_id": str(thread_id) if thread_id else None,
            "date": date,
            "from_address": from_address[:200] if from_address else None,
            "from_name": (from_name or "")[:200] or None,
            "to_address": to_address[:200] if to_address else None,
            "subject": subject,
            "snippet": snippet,
            "body": body,
            "labels": labels if isinstance(labels, list) else [],
        }

    # --- Full Gmail API format ---
    gmail_id = msg.get("id")
    thread_id = msg.get("threadId")

    # Date from internalDate (epoch ms) or headers
    date = parse_gmail_date(msg.get("internalDate"))

    # Headers
    headers = []
    payload = msg.get("payload") or {}
    if isinstance(payload, dict):
        headers = payload.get("headers") or []

    if date is None:
        date = parse_gmail_date(extract_header(headers, "Date"))

    from_raw = extract_header(headers, "From") or ""
    from_name, from_address = parseaddr(from_raw)
    to_address = extract_header(headers, "To") or ""
    subject = extract_header(headers, "Subject") or ""
    snippet = msg.get("snippet") or ""

    # Body extraction from payload
    body = _extract_body(payload)

    labels = msg.get("labelIds") or []

    return {
        "gmail_id": str(gmail_id) if gmail_id else None,
        "thread_id": str(thread_id) if thread_id else None,
        "date": date,
        "from_address": from_address[:200] if from_address else None,
        "from_name": (from_name or "")[:200] or None,
        "to_address": to_address[:200] if to_address else None,
        "subject": subject,
        "snippet": snippet,
        "body": body,
        "labels": labels if isinstance(labels, list) else [],
    }


def _extract_body(payload):
    """Recursively extract text body from Gmail API payload."""
    if not payload or not isinstance(payload, dict):
        return ""

    # Direct body data
    body_data = payload.get("body", {})
    if isinstance(body_data, dict) and body_data.get("data"):
        import base64
        try:
            return base64.urlsafe_b64decode(body_data["data"]).decode("utf-8", errors="replace")
        except Exception:
            pass

    # Check parts recursively... prefer text/plain
    parts = payload.get("parts") or []
    plain_text = ""
    html_text = ""

    for part in parts:
        mime = (part.get("mimeType") or "").lower()
        part_body = part.get("body", {})
        if isinstance(part_body, dict) and part_body.get("data"):
            import base64
            try:
                decoded = base64.urlsafe_b64decode(part_body["data"]).decode(
                    "utf-8", errors="replace"
                )
                if mime == "text/plain":
                    plain_text = decoded
                elif mime == "text/html":
                    html_text = decoded
            except Exception:
                pass

        # Nested multipart
        if part.get("parts"):
            nested = _extract_body(part)
            if nested and not plain_text:
                plain_text = nested

    if plain_text:
        return plain_text
    if html_text:
        # Strip HTML tags for a rough plaintext conversion
        return re.sub(r"<[^>]+>", " ", html_text)
    return ""


def load_json_files(directory):
    """Load and parse all JSON files in a directory.

    Each file can contain:
      - A JSON array of message objects
      - A JSON object with a "messages" key containing an array
      - A single message object
      - Newline-delimited JSON (one message per line)
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"ERROR: Directory not found: {directory}", file=sys.stderr)
        return []

    json_files = sorted(dir_path.glob("*.json"))
    if not json_files:
        print(f"WARNING: No JSON files found in {directory}")
        return []

    print(f"Found {len(json_files)} JSON files in {directory}")

    all_records = []
    for jf in json_files:
        print(f"  Parsing {jf.name}...", end=" ")
        try:
            content = jf.read_text(encoding="utf-8")
        except Exception as e:
            print(f"READ ERROR: {e}")
            continue

        messages = []

        # Try standard JSON parse first
        try:
            data = json.loads(content)

            # Unwrap MCP envelope: [{type: "text", text: "{...}"}]
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "type" in data[0] and "text" in data[0]:
                for item in data:
                    if item.get("type") == "text":
                        try:
                            inner = json.loads(item["text"])
                            if isinstance(inner, dict) and "messages" in inner:
                                messages = inner["messages"]
                            elif isinstance(inner, dict) and "results" in inner:
                                messages = inner["results"]
                            elif isinstance(inner, list):
                                messages = inner
                        except json.JSONDecodeError:
                            pass
                        break
            elif isinstance(data, list):
                messages = data
            elif isinstance(data, dict):
                # Gmail API list response: {"messages": [...], "nextPageToken": ...}
                if "messages" in data:
                    messages = data["messages"]
                # Gmail MCP result with "results" key
                elif "results" in data:
                    messages = data["results"]
                # Single message object
                elif "id" in data or "gmail_id" in data or "messageId" in data:
                    messages = [data]
                else:
                    # Try all list-type values
                    for v in data.values():
                        if isinstance(v, list) and len(v) > 0:
                            messages = v
                            break
        except json.JSONDecodeError:
            # Try newline-delimited JSON
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        messages.append(obj)
                except json.JSONDecodeError:
                    continue

        file_records = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            record = parse_email_record(msg)
            if record.get("gmail_id"):
                file_records.append(record)

        print(f"{len(file_records)} emails parsed")
        all_records.extend(file_records)

    return all_records


# ---------------------------------------------------------------------------
# Categorization
# ---------------------------------------------------------------------------

def categorize_email(record):
    """Classify an email into a category based on content analysis.

    Priority order: rejection > interview > application > status_update >
    recruiter > job_alert > other.

    Returns the category string.
    """
    from_addr = (record.get("from_address") or "").lower()
    from_name = (record.get("from_name") or "").lower()
    subject = (record.get("subject") or "").lower()
    snippet = (record.get("snippet") or "").lower()
    body = (record.get("body") or "").lower()

    # Combine searchable text (subject + snippet + first 2000 chars of body)
    searchable = f"{subject} {snippet} {body[:2000]}"

    # --- Job alerts (check sender first, before content) ---
    for sender in JOB_ALERT_SENDERS:
        if sender in from_addr:
            # But check if it's actually an application confirmation or rejection
            # before defaulting to job_alert
            is_app = any(
                re.search(p, searchable) for p in CATEGORY_PATTERNS["application"]
            )
            is_rejection = any(
                re.search(p, searchable) for p in CATEGORY_PATTERNS["rejection"]
            )
            is_interview = any(
                re.search(p, searchable) for p in CATEGORY_PATTERNS["interview"]
            )
            is_status = any(
                re.search(p, searchable) for p in CATEGORY_PATTERNS["status_update"]
            )

            if is_rejection:
                return "rejection"
            if is_interview:
                return "interview"
            if is_app:
                return "application"
            if is_status:
                return "status_update"
            return "job_alert"

    # --- Rejection (highest priority for non-alert senders) ---
    if any(re.search(p, searchable) for p in CATEGORY_PATTERNS["rejection"]):
        return "rejection"

    # --- Interview ---
    if any(re.search(p, searchable) for p in CATEGORY_PATTERNS["interview"]):
        return "interview"

    # --- Application confirmation ---
    if any(re.search(p, searchable) for p in CATEGORY_PATTERNS["application"]):
        return "application"

    # --- Status update ---
    if any(re.search(p, searchable) for p in CATEGORY_PATTERNS["status_update"]):
        return "status_update"

    # --- Recruiter ---
    for domain in RECRUITER_DOMAINS:
        if domain in from_addr:
            return "recruiter"
    if any(kw in from_name or kw in subject for kw in RECRUITER_KEYWORDS):
        return "recruiter"

    return "other"


# ---------------------------------------------------------------------------
# Application linking
# ---------------------------------------------------------------------------

def _build_company_index(cur):
    """Load all applications with company names for fuzzy matching.

    Returns a dict: lowercase_company_name -> application_id.
    """
    cur.execute(
        "SELECT id, LOWER(COALESCE(company_name, '')) FROM applications"
    )
    index = {}
    for app_id, name in cur.fetchall():
        if name:
            index[name] = app_id
    return index


def _normalize_company(text):
    """Extract a rough company name from an email address or domain."""
    if not text:
        return ""
    text = text.lower().strip()
    # Strip common suffixes
    text = re.sub(r"\.(com|org|net|io|co|ai)$", "", text)
    # Strip common prefixes
    text = re.sub(r"^(noreply|no-reply|careers|jobs|recruiting|talent|hr|apply|info|hello)[@.]", "", text)
    # Extract domain from email
    if "@" in text:
        text = text.split("@")[1]
        text = re.sub(r"\.(com|org|net|io|co|ai)$", "", text)
    return text


def link_to_application(record, company_index):
    """Try to link an email to an existing application by company name match.

    Checks from_address domain and subject line against known company names.
    Returns application_id or None.
    """
    from_addr = record.get("from_address") or ""
    subject = record.get("subject") or ""

    # Extract candidate company name from from_address domain
    from_company = _normalize_company(from_addr)

    # Check direct match on from_address domain
    for company_name, app_id in company_index.items():
        # Skip very short names that might false-match
        if len(company_name) < 3:
            continue

        # Check if company name appears in from domain
        if from_company and company_name in from_company:
            return app_id

        # Check if company name appears in subject
        if company_name in subject.lower():
            return app_id

    return None


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

def upsert_emails(cur, records, dry_run=False):
    """Batch upsert email records into the emails table.

    Uses gmail_id as the conflict key (UNIQUE constraint in schema).
    Returns (inserted_count, updated_count, error_count).
    """
    inserted = 0
    updated = 0
    errors = 0

    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]

        for rec in batch:
            try:
                if dry_run:
                    # Check if exists
                    cur.execute(
                        "SELECT 1 FROM emails WHERE gmail_id = %s",
                        (rec["gmail_id"],),
                    )
                    if cur.fetchone():
                        updated += 1
                    else:
                        inserted += 1
                    continue

                cur.execute(
                    """INSERT INTO emails
                        (gmail_id, thread_id, date, from_address, from_name,
                         to_address, subject, snippet, body, category,
                         application_id, labels)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (gmail_id) DO UPDATE SET
                        thread_id = COALESCE(EXCLUDED.thread_id, emails.thread_id),
                        date = COALESCE(EXCLUDED.date, emails.date),
                        from_address = COALESCE(EXCLUDED.from_address, emails.from_address),
                        from_name = COALESCE(EXCLUDED.from_name, emails.from_name),
                        to_address = COALESCE(EXCLUDED.to_address, emails.to_address),
                        subject = COALESCE(EXCLUDED.subject, emails.subject),
                        snippet = COALESCE(EXCLUDED.snippet, emails.snippet),
                        body = COALESCE(EXCLUDED.body, emails.body),
                        category = EXCLUDED.category,
                        application_id = COALESCE(EXCLUDED.application_id, emails.application_id),
                        labels = COALESCE(EXCLUDED.labels, emails.labels)
                    RETURNING (xmax = 0) AS is_insert""",
                    (
                        rec["gmail_id"],
                        rec.get("thread_id"),
                        rec.get("date"),
                        rec.get("from_address"),
                        rec.get("from_name"),
                        rec.get("to_address"),
                        rec.get("subject"),
                        rec.get("snippet"),
                        rec.get("body"),
                        rec.get("category"),
                        rec.get("application_id"),
                        rec.get("labels"),
                    ),
                )
                result = cur.fetchone()
                if result and result[0]:
                    inserted += 1
                else:
                    updated += 1

            except Exception as e:
                errors += 1
                gmail_id = rec.get("gmail_id", "?")
                print(
                    f"  ! ERROR on gmail_id={gmail_id}: {e}",
                    file=sys.stderr,
                )

        # Progress
        processed = min(i + BATCH_SIZE, len(records))
        print(
            f"  Progress: {processed}/{len(records)} "
            f"(+{inserted} new, ~{updated} updated, !{errors} errors)",
            end="\r",
        )

    print()  # newline after progress
    return inserted, updated, errors


def recategorize_existing(cur, dry_run=False):
    """Re-categorize all existing emails in the database.

    Returns count of emails updated.
    """
    cur.execute(
        "SELECT id, gmail_id, from_address, from_name, subject, snippet, body "
        "FROM emails"
    )
    rows = cur.fetchall()
    print(f"  Re-categorizing {len(rows)} existing emails...")

    changed = 0
    for row_id, gmail_id, from_addr, from_name, subject, snippet, body in rows:
        record = {
            "from_address": from_addr,
            "from_name": from_name,
            "subject": subject,
            "snippet": snippet,
            "body": body,
        }
        new_cat = categorize_email(record)

        if not dry_run:
            cur.execute(
                "UPDATE emails SET category = %s WHERE id = %s AND "
                "(category IS DISTINCT FROM %s)",
                (new_cat, row_id, new_cat),
            )
            if cur.rowcount > 0:
                changed += 1
        else:
            changed += 1  # count all in dry run

    return changed


def relink_existing(cur, dry_run=False):
    """Re-link all existing emails to applications.

    Returns count of emails linked.
    """
    company_index = _build_company_index(cur)
    if not company_index:
        print("  No applications in database to link against.")
        return 0

    cur.execute(
        "SELECT id, gmail_id, from_address, subject FROM emails"
    )
    rows = cur.fetchall()
    print(f"  Re-linking {len(rows)} emails against {len(company_index)} applications...")

    linked = 0
    for row_id, gmail_id, from_addr, subject in rows:
        record = {"from_address": from_addr, "subject": subject}
        app_id = link_to_application(record, company_index)

        if app_id is not None:
            if not dry_run:
                cur.execute(
                    "UPDATE emails SET application_id = %s WHERE id = %s AND "
                    "(application_id IS DISTINCT FROM %s)",
                    (app_id, row_id, app_id),
                )
                if cur.rowcount > 0:
                    linked += 1
            else:
                linked += 1

    return linked


# ---------------------------------------------------------------------------
# Main commands
# ---------------------------------------------------------------------------

def load(directory, dry_run=False, category_only=False, link_only=False):
    """Main ETL load process."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # --- Category-only mode: just re-categorize existing ---
        if category_only:
            print("Re-categorizing existing emails...")
            changed = recategorize_existing(cur, dry_run=dry_run)
            if not dry_run:
                conn.commit()
            print(f"\n  {'Would update' if dry_run else 'Updated'} {changed} email categories.")
            _print_category_counts(cur)
            return

        # --- Link-only mode: just re-link to applications ---
        if link_only:
            print("Re-linking existing emails to applications...")
            linked = relink_existing(cur, dry_run=dry_run)
            if not dry_run:
                conn.commit()
            print(f"\n  {'Would link' if dry_run else 'Linked'} {linked} emails to applications.")
            return

        # --- Full load from JSON files ---
        print(f"Loading emails from JSON files in: {directory}")
        records = load_json_files(directory)

        if not records:
            print("No email records found. Nothing to load.")
            return

        # Deduplicate by gmail_id (keep first occurrence)
        seen_ids = set()
        unique_records = []
        for rec in records:
            gid = rec.get("gmail_id")
            if gid and gid not in seen_ids:
                seen_ids.add(gid)
                unique_records.append(rec)

        print(f"\n{len(unique_records)} unique emails after dedup (from {len(records)} parsed)")

        # --- Categorize ---
        print("\nCategorizing emails...")
        category_counts = {}
        for rec in unique_records:
            cat = categorize_email(rec)
            rec["category"] = cat
            category_counts[cat] = category_counts.get(cat, 0) + 1

        print("  Category breakdown:")
        for cat in sorted(category_counts, key=category_counts.get, reverse=True):
            print(f"    {cat:<20} {category_counts[cat]:>6}")

        # --- Link to applications ---
        print("\nLinking emails to applications...")
        company_index = _build_company_index(cur)
        linked_count = 0
        for rec in unique_records:
            app_id = link_to_application(rec, company_index)
            rec["application_id"] = app_id
            if app_id is not None:
                linked_count += 1

        print(f"  Linked {linked_count}/{len(unique_records)} emails to existing applications")

        # --- Dry run preview ---
        if dry_run:
            print(f"\n--- DRY RUN (no database changes) ---")
            # Show sample of each category
            by_cat = {}
            for rec in unique_records:
                cat = rec["category"]
                if cat not in by_cat:
                    by_cat[cat] = []
                if len(by_cat[cat]) < 3:
                    by_cat[cat].append(rec)

            for cat in sorted(by_cat):
                print(f"\n  [{cat}] ({category_counts.get(cat, 0)} total)")
                for rec in by_cat[cat]:
                    date_str = rec["date"].strftime("%Y-%m-%d") if rec.get("date") else "no date"
                    subj = (rec.get("subject") or "")[:60]
                    print(f"    {date_str}  {rec.get('from_address', '')[:30]:<30}  {subj}")

            print(f"\nDry run complete. {len(unique_records)} emails would be loaded.")
            return

        # --- Upsert into database ---
        print(f"\nUpserting {len(unique_records)} emails into database...")
        inserted, updated, errors = upsert_emails(cur, unique_records)
        conn.commit()

        # --- Summary ---
        print(f"\n{'='*60}")
        print(f"Load complete.")
        print(f"  Inserted:     {inserted}")
        print(f"  Updated:      {updated}")
        print(f"  Errors:       {errors}")
        print(f"  Linked:       {linked_count}")
        _print_category_counts(cur)

    finally:
        cur.close()
        conn.close()


def _print_category_counts(cur):
    """Print category distribution from the database."""
    cur.execute(
        "SELECT COALESCE(category, 'uncategorized'), COUNT(*) "
        "FROM emails GROUP BY category ORDER BY COUNT(*) DESC"
    )
    rows = cur.fetchall()
    if rows:
        total = sum(c for _, c in rows)
        print(f"\n  Email categories in DB ({total} total):")
        for cat, count in rows:
            pct = count * 100.0 / total if total else 0
            print(f"    {cat:<20} {count:>6}  ({pct:5.1f}%)")


def status():
    """Show current email counts in the database."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT COUNT(*) FROM emails")
        total = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM emails WHERE application_id IS NOT NULL"
        )
        linked = cur.fetchone()[0]

        print(f"Emails in database: {total}")
        print(f"Linked to applications: {linked}")

        _print_category_counts(cur)

        # Date range
        cur.execute("SELECT MIN(date), MAX(date) FROM emails WHERE date IS NOT NULL")
        min_date, max_date = cur.fetchone()
        if min_date:
            print(f"\n  Date range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")

        # Top senders
        cur.execute(
            "SELECT from_address, COUNT(*) FROM emails "
            "GROUP BY from_address ORDER BY COUNT(*) DESC LIMIT 10"
        )
        senders = cur.fetchall()
        if senders:
            print(f"\n  Top senders:")
            for addr, count in senders:
                print(f"    {addr or 'NULL':<50} {count}")

    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser(prog=None):
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Load email data into SuperTroopers database",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    load_p = sub.add_parser("load", help="Parse JSON files and load into database")
    load_p.add_argument(
        "directory",
        help="Directory containing JSON files with Gmail search results",
    )
    load_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and categorize but don't write to the database",
    )
    load_p.add_argument(
        "--category-only",
        action="store_true",
        help="Only re-categorize existing emails in the database (ignores directory)",
    )
    load_p.add_argument(
        "--link-only",
        action="store_true",
        help="Only re-link existing emails to applications (ignores directory)",
    )

    sub.add_parser("status", help="Show current email counts in the database")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "load":
        load(
            directory=args.directory,
            dry_run=args.dry_run,
            category_only=args.category_only,
            link_only=args.link_only,
        )
    elif args.command == "status":
        status()


if __name__ == "__main__":
    main()
