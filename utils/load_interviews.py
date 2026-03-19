"""
Interviews ETL loader for SuperTroopers.

Loads interview data into the interviews table from two sources:
  1. Notes/REJECTION_ANALYSIS.md (interview activity tables)
  2. Notes/APPLICATION_HISTORY.md (key interviews table)

Links each interview to an existing application by company+role match.
Creates a stub application if none exists. Deduplicates by
application_id + date for idempotency.

Mode 2 (Google Calendar MCP) is stubbed for future integration.

Usage:
    python load_interviews.py load [--dry-run]
    python load_interviews.py load --source rejection
    python load_interviews.py load --source application
    python load_interviews.py status
    python load_interviews.py calendar  (future -- placeholder)
"""

import argparse
import os
import re
import sys
from datetime import datetime
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
REJECTION_PATH = PROJECT_ROOT / "Notes" / "REJECTION_ANALYSIS.md"
APPLICATION_PATH = PROJECT_ROOT / "Notes" / "APPLICATION_HISTORY.md"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

from db_config import get_db_config


def get_db_connection():
    """Connect to the SuperTroopers PostgreSQL database."""
    return psycopg2.connect(**get_db_config())


def ensure_unique_constraint(cur):
    """Create a unique constraint on interviews(application_id, date) if missing.

    This enables true UPSERT via ON CONFLICT.
    """
    cur.execute("""
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_interviews_app_date'
    """)
    if not cur.fetchone():
        cur.execute("""
            ALTER TABLE interviews
            ADD CONSTRAINT uq_interviews_app_date
            UNIQUE (application_id, date)
        """)
        print("  Created unique constraint uq_interviews_app_date")


def find_application(cur, company_name, role=None):
    """Find an application by company name (and optionally role).

    Returns the application id or None.
    """
    if not company_name:
        return None

    # Clean up markdown bold markers
    company_clean = company_name.replace("**", "").strip()

    # Try exact match with role first
    if role and role not in ("Unknown", "Not specified", "TBD"):
        cur.execute(
            """SELECT id FROM applications
               WHERE LOWER(company_name) = LOWER(%s)
                 AND LOWER(role) = LOWER(%s)
               LIMIT 1""",
            (company_clean, role),
        )
        row = cur.fetchone()
        if row:
            return row[0]

    # Fall back to company-only match
    cur.execute(
        """SELECT id FROM applications
           WHERE LOWER(company_name) = LOWER(%s)
           ORDER BY date_applied DESC NULLS LAST
           LIMIT 1""",
        (company_clean,),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    return None


def ensure_application(cur, company_name, role, date_str=None, status=None):
    """Find or create an application for linking. Returns application id."""
    company_clean = company_name.replace("**", "").strip()
    role_clean = role if role and role not in ("Unknown", "Not specified", "TBD") else "Senior Engineering Leadership"

    app_id = find_application(cur, company_clean, role_clean)
    if app_id:
        return app_id

    # Also try without the role
    app_id = find_application(cur, company_clean)
    if app_id:
        return app_id

    # Ensure company exists
    cur.execute(
        "SELECT id FROM companies WHERE LOWER(name) = LOWER(%s)",
        (company_clean,),
    )
    company_row = cur.fetchone()
    if company_row:
        company_id = company_row[0]
    else:
        cur.execute(
            "INSERT INTO companies (name) VALUES (%s) RETURNING id",
            (company_clean,),
        )
        company_id = cur.fetchone()[0]

    cur.execute(
        """INSERT INTO applications
            (company_id, company_name, role, date_applied, status, notes, last_status_change)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        RETURNING id""",
        (
            company_id,
            company_clean,
            role_clean,
            date_str,
            status or "Interview",
            "Auto-created by interview loader",
        ),
    )
    return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def parse_date_flexible(text):
    """Parse a date string from various formats found in the markdown files.

    Returns a datetime or None. Handles:
      - "Mar 17, 2026"
      - "Feb 24 - Mar 18, 2026" (takes earliest)
      - "Mar 2024"
      - "Dec 2024 - Jun 2025" (takes earliest)
      - "Nov 18, 2024"
      - "Jun 2024"
    """
    if not text:
        return None

    text = text.strip()

    # Remove markdown bold
    text = text.replace("**", "")

    # Try full date formats first
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass

    # Range: take the first date from "X - Y" or "X to Y"
    range_match = re.match(r"(.+?)\s*[-–]\s*(.+)", text)
    if range_match:
        first_part = range_match.group(1).strip()
        second_part = range_match.group(2).strip()

        # Try parsing the first part as a full date
        for fmt in ("%b %d, %Y", "%B %d, %Y"):
            try:
                return datetime.strptime(first_part, fmt)
            except ValueError:
                pass

        # Try "Mon DD" without year, then grab year from the second part
        year_match = re.search(r"(\d{4})", second_part)
        if year_match:
            inferred_year = year_match.group(1)
            for fmt in ("%b %d, %Y", "%B %d, %Y"):
                try:
                    return datetime.strptime(f"{first_part}, {inferred_year}", fmt)
                except ValueError:
                    pass

        # Try "Mon YYYY - Mon YYYY" range
        for fmt in ("%b %Y", "%B %Y"):
            try:
                return datetime.strptime(first_part, fmt)
            except ValueError:
                pass

    # Month + Year only
    for fmt in ("%b %Y", "%B %Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass

    # Just a month name with a year somewhere
    month_year = re.match(r"(\w+)\s+(\d{4})", text)
    if month_year:
        for fmt in ("%b %Y", "%B %Y"):
            try:
                return datetime.strptime(f"{month_year.group(1)} {month_year.group(2)}", fmt)
            except ValueError:
                pass

    return None


# ---------------------------------------------------------------------------
# Interview type inference
# ---------------------------------------------------------------------------

def infer_interview_type(text):
    """Guess interview type from descriptive text.

    Returns one of: phone, video, onsite, technical, panel, AI, final, unknown.
    """
    if not text:
        return "unknown"
    t = text.lower()

    if "ai interview" in t or "ai stage" in t:
        return "AI"
    if "technical" in t or "coding" in t or "assessment" in t:
        return "technical"
    if "panel" in t:
        return "panel"
    if "phone screen" in t or "phone interview" in t or "phone" in t:
        return "phone"
    if "video" in t or "zoom" in t or "teams" in t or "microsoft teams" in t:
        return "video"
    if "onsite" in t or "on-site" in t or "in person" in t:
        return "onsite"
    if "final" in t:
        return "final"
    if "cto interview" in t or "director" in t or "multi-round" in t:
        return "video"

    return "unknown"


def infer_outcome(text):
    """Guess interview outcome from descriptive text.

    Returns one of: passed, failed, pending, ghosted, canceled, unknown.
    """
    if not text:
        return "unknown"
    t = text.lower()

    if "rejected" in t or "not moving forward" in t or "different direction" in t:
        return "failed"
    if "active" in t or "awaiting" in t or "scheduled" in t or "in progress" in t:
        return "pending"
    if "ghosted" in t or "trail goes cold" in t or "no response" in t or "silence" in t:
        return "ghosted"
    if "canceled" in t or "cancelled" in t or "no-show" in t or "removed" in t:
        return "canceled"
    if "positive" in t or "passed" in t or "moved forward" in t:
        return "passed"

    return "unknown"


def extract_interviewers(text):
    """Extract interviewer names from descriptive text.

    Looks for patterns like "with Name Name" or "Name Name (title)".
    Returns a list of name strings.
    """
    if not text:
        return []

    names = []

    # Pattern: "with FirstName LastName"
    with_matches = re.findall(
        r"(?:with|via)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", text
    )
    names.extend(with_matches)

    # Pattern: "FirstName LastName (Title)" or "FirstName LastName, Title"
    titled = re.findall(
        r"([A-Z][a-z]+\s+[A-Z][a-z]+)\s*(?:\(|,)\s*(?:CTO|CSO|VP|Director|Recruiter|CEO|COO|CFO|Manager)",
        text,
    )
    names.extend(titled)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for n in names:
        n_lower = n.lower()
        if n_lower not in seen:
            seen.add(n_lower)
            unique.append(n)

    return unique


# ---------------------------------------------------------------------------
# Markdown table parsing
# ---------------------------------------------------------------------------

def _extract_table_rows(lines, start_idx):
    """Extract data rows from a markdown table starting after the heading.

    Returns list of lists of column strings.
    """
    rows = []
    i = start_idx + 1
    while i < len(lines) and not lines[i].strip().startswith("|"):
        i += 1
    if i >= len(lines):
        return []
    # Skip header
    i += 1
    # Skip separator
    if i < len(lines) and re.match(r"\s*\|[-| :]+\|\s*$", lines[i]):
        i += 1
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith("|"):
            break
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if cols:
            rows.append(cols)
        i += 1
    return rows


# ---------------------------------------------------------------------------
# Source 1: REJECTION_ANALYSIS.md
# ---------------------------------------------------------------------------

def parse_rejection_analysis(path):
    """Parse interview records from REJECTION_ANALYSIS.md.

    Extracts from sections:
      - Section 1: Active/In Progress, Completed Interviews, Scheduling Gone Cold
      - Section 2: Formal Rejections Post-Interview
    """
    if not path.exists():
        print(f"  WARNING: File not found: {path}")
        return []

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    records = []

    # Build index of all headings (## and ###)
    headings = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("### "):
            headings.append((i, stripped))

    for idx, (line_num, heading) in enumerate(headings):
        heading_lower = heading.lower()

        # --- Active / In Progress ---
        if "active" in heading_lower and "in progress" in heading_lower:
            for cols in _extract_table_rows(lines, line_num):
                if len(cols) >= 5:
                    company = cols[0].replace("**", "").strip()
                    role = cols[1].strip()
                    dates_raw = cols[2].strip()
                    stage_detail = cols[3].strip()
                    status_raw = cols[4].replace("**", "").strip()

                    dt = parse_date_flexible(dates_raw)
                    interviewers = extract_interviewers(stage_detail)

                    # Multi-round: create an interview per round if detail describes them
                    round_dates = _extract_round_dates(stage_detail, dates_raw)
                    if round_dates:
                        for rd in round_dates:
                            records.append({
                                "company": company,
                                "role": role,
                                "date": rd["date"],
                                "type": rd.get("type", infer_interview_type(stage_detail)),
                                "interviewers": rd.get("interviewers", interviewers),
                                "outcome": infer_outcome(status_raw),
                                "feedback": None,
                                "notes": stage_detail,
                                "thank_you_sent": False,
                                "source_file": "REJECTION_ANALYSIS.md",
                            })
                    else:
                        records.append({
                            "company": company,
                            "role": role,
                            "date": dt,
                            "type": infer_interview_type(stage_detail),
                            "interviewers": interviewers,
                            "outcome": infer_outcome(status_raw),
                            "feedback": None,
                            "notes": stage_detail,
                            "thank_you_sent": False,
                            "source_file": "REJECTION_ANALYSIS.md",
                        })

        # --- Completed Interviews ---
        elif "completed interviews" in heading_lower:
            for cols in _extract_table_rows(lines, line_num):
                if len(cols) >= 5:
                    company = cols[0].replace("**", "").strip()
                    role = cols[1].strip()
                    dates_raw = cols[2].strip()
                    stage_detail = cols[3].strip()
                    outcome_raw = cols[4].replace("**", "").strip()

                    dt = parse_date_flexible(dates_raw)
                    interviewers = extract_interviewers(stage_detail)

                    # Extract feedback from outcome text
                    feedback = None
                    feedback_match = re.search(r'["\u201c](.+?)["\u201d]', outcome_raw)
                    if feedback_match:
                        feedback = feedback_match.group(1)

                    round_dates = _extract_round_dates(stage_detail, dates_raw)
                    if round_dates:
                        for rd in round_dates:
                            records.append({
                                "company": company,
                                "role": role,
                                "date": rd["date"],
                                "type": rd.get("type", infer_interview_type(stage_detail)),
                                "interviewers": rd.get("interviewers", interviewers),
                                "outcome": infer_outcome(outcome_raw),
                                "feedback": feedback,
                                "notes": f"{stage_detail} | {outcome_raw}",
                                "thank_you_sent": _has_thank_you(stage_detail + " " + outcome_raw),
                                "source_file": "REJECTION_ANALYSIS.md",
                            })
                    else:
                        records.append({
                            "company": company,
                            "role": role,
                            "date": dt,
                            "type": infer_interview_type(stage_detail),
                            "interviewers": interviewers,
                            "outcome": infer_outcome(outcome_raw),
                            "feedback": feedback,
                            "notes": f"{stage_detail} | {outcome_raw}",
                            "thank_you_sent": _has_thank_you(stage_detail + " " + outcome_raw),
                            "source_file": "REJECTION_ANALYSIS.md",
                        })

        # --- Scheduling Gone Cold ---
        elif "scheduling" in heading_lower and "cold" in heading_lower:
            for cols in _extract_table_rows(lines, line_num):
                if len(cols) >= 4:
                    company = cols[0].replace("**", "").strip()
                    role = cols[1].strip()
                    last_activity = cols[2].strip()
                    what_happened = cols[3].strip()

                    dt = parse_date_flexible(last_activity)

                    records.append({
                        "company": company,
                        "role": role,
                        "date": dt,
                        "type": infer_interview_type(what_happened),
                        "interviewers": extract_interviewers(what_happened),
                        "outcome": "ghosted",
                        "feedback": None,
                        "notes": what_happened,
                        "thank_you_sent": False,
                        "source_file": "REJECTION_ANALYSIS.md",
                    })

        # --- Formal Rejections Post-Interview (Section 2) ---
        elif "formal rejections post-interview" in heading_lower:
            for cols in _extract_table_rows(lines, line_num):
                if len(cols) >= 4:
                    company = cols[0].replace("**", "").strip()
                    role = cols[1].strip()
                    rejection_date = cols[2].strip()
                    feedback_text = cols[3].strip()

                    dt = parse_date_flexible(rejection_date)
                    feedback = None
                    fb_match = re.search(r'["\u201c](.+?)["\u201d]', feedback_text)
                    if fb_match:
                        feedback = fb_match.group(1)
                    elif feedback_text.lower() not in ("no", "no -- standard rejection", "no -- generic"):
                        feedback = feedback_text if feedback_text else None

                    # These are rejection confirmations, not separate interviews.
                    # We update existing records rather than creating new ones.
                    # But we still include them so the loader can merge.
                    records.append({
                        "company": company,
                        "role": role,
                        "date": dt,
                        "type": "unknown",
                        "interviewers": [],
                        "outcome": "failed",
                        "feedback": feedback,
                        "notes": f"Post-interview rejection. {feedback_text}",
                        "thank_you_sent": False,
                        "source_file": "REJECTION_ANALYSIS.md",
                        "_is_rejection_confirmation": True,
                    })

    return records


def _extract_round_dates(stage_detail, dates_raw):
    """Try to extract individual interview round dates from stage descriptions.

    Handles text like:
      "Phone screen with X, CTO interview with Y (Mar 6), 90-min technical (Mar 13)"
    Returns list of dicts with date, type, interviewers or empty list.
    """
    rounds = []

    # Look for "(Mon DD)" or "(Mon DD, YYYY)" patterns in the detail text
    date_paren = re.findall(
        r"([^,;]+?)\s*\((\w{3}\s+\d{1,2}(?:,?\s+\d{4})?)\)",
        stage_detail,
    )

    if not date_paren:
        return []

    # Try to infer the year from dates_raw
    year_match = re.search(r"(\d{4})", dates_raw)
    default_year = int(year_match.group(1)) if year_match else datetime.now().year

    for desc, date_str in date_paren:
        dt = parse_date_flexible(date_str)
        if dt and dt.year == 1900:
            dt = dt.replace(year=default_year)
        if not dt:
            # Try adding the year
            dt = parse_date_flexible(f"{date_str}, {default_year}")
        if dt:
            rounds.append({
                "date": dt,
                "type": infer_interview_type(desc),
                "interviewers": extract_interviewers(desc),
            })

    return rounds


def _has_thank_you(text):
    """Check if text mentions a thank-you was sent."""
    t = text.lower()
    return "thank you" in t or "thank-you" in t or "thanked" in t or "roi follow-up" in t


# ---------------------------------------------------------------------------
# Source 2: APPLICATION_HISTORY.md
# ---------------------------------------------------------------------------

def parse_application_history(path):
    """Parse interview records from APPLICATION_HISTORY.md Key Interviews table."""
    if not path.exists():
        print(f"  WARNING: File not found: {path}")
        return []

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    records = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## ") and "key interviews" in stripped.lower():
            for cols in _extract_table_rows(lines, i):
                if len(cols) >= 4:
                    date_str = cols[0].strip()
                    company = cols[1].strip()
                    role = cols[2].strip()
                    outcome_raw = cols[3].strip()

                    dt = parse_date_flexible(date_str)

                    feedback = None
                    fb_match = re.search(r"\((.+?)\)", outcome_raw)
                    if fb_match:
                        feedback = fb_match.group(1)

                    records.append({
                        "company": company,
                        "role": role if role != "Unknown" else "Senior Engineering Leadership",
                        "date": dt,
                        "type": infer_interview_type(outcome_raw),
                        "interviewers": extract_interviewers(outcome_raw),
                        "outcome": infer_outcome(outcome_raw),
                        "feedback": feedback,
                        "notes": outcome_raw,
                        "thank_you_sent": False,
                        "source_file": "APPLICATION_HISTORY.md",
                    })
            break

    return records


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate_interviews(records):
    """Deduplicate by (company, date).

    REJECTION_ANALYSIS.md records take priority because they have more detail.
    Rejection confirmations (_is_rejection_confirmation) are merged into
    existing records rather than creating new ones.
    """
    seen = {}
    for rec in records:
        company_key = rec["company"].lower().strip()
        date_key = rec["date"].strftime("%Y-%m-%d") if rec["date"] else "no-date"
        key = (company_key, date_key)

        is_confirmation = rec.get("_is_rejection_confirmation", False)

        if key in seen:
            existing = seen[key]
            # Merge: fill blanks from the new record
            if is_confirmation:
                # Only update feedback and outcome
                if rec.get("feedback") and not existing.get("feedback"):
                    existing["feedback"] = rec["feedback"]
                if existing["outcome"] == "unknown":
                    existing["outcome"] = rec["outcome"]
            else:
                # Prefer the record with more data
                if rec["source_file"] == "REJECTION_ANALYSIS.md" and existing["source_file"] != "REJECTION_ANALYSIS.md":
                    # Keep rejection analysis, merge in application history data
                    for field in ("feedback", "interviewers"):
                        if not rec.get(field) and existing.get(field):
                            rec[field] = existing[field]
                    seen[key] = rec
                else:
                    for field in ("feedback", "interviewers", "type"):
                        if not existing.get(field) and rec.get(field):
                            existing[field] = rec[field]
        else:
            if not is_confirmation:
                seen[key] = rec

    return list(seen.values())


# ---------------------------------------------------------------------------
# Database loading
# ---------------------------------------------------------------------------

def upsert_interview(cur, record, application_id):
    """Upsert an interview record using ON CONFLICT on (application_id, date)."""
    date_val = record["date"]
    interviewers = record.get("interviewers") or []

    cur.execute(
        """INSERT INTO interviews
            (application_id, date, type, interviewers, outcome, feedback,
             thank_you_sent, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (application_id, date)
        DO UPDATE SET
            type = COALESCE(EXCLUDED.type, interviews.type),
            interviewers = CASE
                WHEN EXCLUDED.interviewers IS NOT NULL AND array_length(EXCLUDED.interviewers, 1) > 0
                THEN EXCLUDED.interviewers
                ELSE interviews.interviewers
            END,
            outcome = COALESCE(EXCLUDED.outcome, interviews.outcome),
            feedback = COALESCE(EXCLUDED.feedback, interviews.feedback),
            thank_you_sent = EXCLUDED.thank_you_sent OR interviews.thank_you_sent,
            notes = COALESCE(EXCLUDED.notes, interviews.notes)
        RETURNING id, (xmax = 0) AS is_insert""",
        (
            application_id,
            date_val,
            record.get("type", "unknown"),
            interviewers if interviewers else None,
            record.get("outcome", "unknown"),
            record.get("feedback"),
            record.get("thank_you_sent", False),
            record.get("notes"),
        ),
    )
    row = cur.fetchone()
    return ("inserted" if row[1] else "updated"), row[0]


# ---------------------------------------------------------------------------
# Main commands
# ---------------------------------------------------------------------------

def load(dry_run=False, source_filter=None):
    """Main ETL load process."""
    all_records = []

    # --- Parse sources ---
    if source_filter in (None, "rejection"):
        print(f"Parsing: {REJECTION_PATH}")
        rejection_records = parse_rejection_analysis(REJECTION_PATH)
        print(f"  Found {len(rejection_records)} interview records")
        all_records.extend(rejection_records)

    if source_filter in (None, "application"):
        print(f"Parsing: {APPLICATION_PATH}")
        app_records = parse_application_history(APPLICATION_PATH)
        print(f"  Found {len(app_records)} interview records")
        all_records.extend(app_records)

    if not all_records:
        print("No interview records found. Nothing to load.")
        return

    # --- Deduplicate ---
    print(f"\nDeduplicating {len(all_records)} total records...")
    records = deduplicate_interviews(all_records)
    print(f"  {len(records)} unique records after dedup")

    if dry_run:
        print("\n--- DRY RUN (no database changes) ---")
        for rec in records:
            date_str = rec["date"].strftime("%Y-%m-%d") if rec["date"] else "no date"
            interviewers_str = ", ".join(rec.get("interviewers", [])) or "none"
            print(
                f"  {rec['company']:<25} {date_str:<12} "
                f"{rec['type']:<10} {rec['outcome']:<10} "
                f"interviewers=[{interviewers_str}]"
            )
        print(f"\nDry run complete. {len(records)} records would be loaded.")
        return

    # --- Load into database ---
    print("\nConnecting to database...")
    conn = get_db_connection()
    cur = conn.cursor()

    inserted = 0
    updated = 0
    apps_created = 0
    errors = []

    try:
        ensure_unique_constraint(cur)

        for rec in records:
            try:
                # Find or create the linked application
                app_id = find_application(cur, rec["company"], rec.get("role"))
                if not app_id:
                    app_id = ensure_application(
                        cur,
                        rec["company"],
                        rec.get("role", "Senior Engineering Leadership"),
                        date_str=rec["date"].strftime("%Y-%m-%d") if rec["date"] else None,
                        status="Interview",
                    )
                    apps_created += 1
                    print(f"  + app  {rec['company']:<25} (auto-created)")

                action, interview_id = upsert_interview(cur, rec, app_id)

                date_str = rec["date"].strftime("%Y-%m-%d") if rec["date"] else "no date"
                if action == "inserted":
                    inserted += 1
                    print(f"  + int  {rec['company']:<25} {date_str:<12} [{rec['type']}] -> {rec['outcome']}")
                else:
                    updated += 1
                    print(f"  ~ int  {rec['company']:<25} {date_str:<12} [{rec['type']}] -> {rec['outcome']}")

            except Exception as e:
                errors.append((rec["company"], str(e)))
                print(
                    f"  ! ERROR: {rec['company']}: {e}",
                    file=sys.stderr,
                )

        conn.commit()

        cur.execute("SELECT COUNT(*) FROM interviews")
        total_interviews = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM applications")
        total_apps = cur.fetchone()[0]

    finally:
        cur.close()
        conn.close()

    # --- Summary ---
    print(f"\n{'='*60}")
    print("Load complete.")
    print(f"  Interviews inserted:       {inserted}")
    print(f"  Interviews updated:        {updated}")
    print(f"  Applications auto-created: {apps_created}")
    print(f"  Errors:                    {len(errors)}")
    print(f"  Total interviews in DB:    {total_interviews}")
    print(f"  Total applications in DB:  {total_apps}")
    if errors:
        print("\nErrors:")
        for company, msg in errors:
            print(f"  - {company}: {msg}")


def status():
    """Show current interview counts in the database."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT COUNT(*) FROM interviews")
        total = cur.fetchone()[0]

        cur.execute(
            "SELECT type, COUNT(*) FROM interviews GROUP BY type ORDER BY COUNT(*) DESC"
        )
        types = cur.fetchall()

        cur.execute(
            "SELECT outcome, COUNT(*) FROM interviews GROUP BY outcome ORDER BY COUNT(*) DESC"
        )
        outcomes = cur.fetchall()

        cur.execute(
            "SELECT thank_you_sent, COUNT(*) FROM interviews GROUP BY thank_you_sent"
        )
        thank_yous = cur.fetchall()

        cur.execute("""
            SELECT a.company_name, i.date, i.type, i.outcome
            FROM interviews i
            JOIN applications a ON a.id = i.application_id
            ORDER BY i.date DESC NULLS LAST
            LIMIT 10
        """)
        recent = cur.fetchall()

        print(f"Total interviews: {total}")
        print(f"\nBy Type:")
        for t, c in types:
            print(f"  {t or 'NULL':<15} {c}")
        print(f"\nBy Outcome:")
        for o, c in outcomes:
            print(f"  {o or 'NULL':<15} {c}")
        print(f"\nThank-You Sent:")
        for sent, c in thank_yous:
            label = "Yes" if sent else "No"
            print(f"  {label:<15} {c}")
        print(f"\nMost Recent:")
        for company, date, itype, outcome in recent:
            date_str = date.strftime("%Y-%m-%d") if date else "no date"
            print(f"  {company or 'Unknown':<25} {date_str:<12} {itype or '?':<10} {outcome or '?'}")

    finally:
        cur.close()
        conn.close()


def calendar():
    """Placeholder for Google Calendar MCP integration.

    Future implementation would:
      1. Search calendar events for interview-related titles
         (e.g., "Interview", "Phone Screen", "Technical", company names)
      2. Extract event date, time, duration, and attendees
      3. Match attendees to interviewers
      4. Link to applications by company name matching
      5. Create interview records with calendar_event_id set

    Requires Google Calendar MCP tools:
      - gcal_list_events with date range and keyword filters
      - gcal_get_event for individual event details
    """
    print("Google Calendar interview loader is not yet implemented.")
    print()
    print("When ready, this mode will:")
    print("  1. Search calendar for events with interview-related titles")
    print("  2. Extract date, attendees, and meeting links")
    print("  3. Match to existing applications by company name")
    print("  4. Create interview records with calendar_event_id linked")
    print()
    print("To implement, connect the Google Calendar MCP and update this command.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser(prog=None):
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Load interview data into the SuperTroopers database",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    load_p = sub.add_parser("load", help="Parse markdown sources and load interviews")
    load_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and show records without writing to the database",
    )
    load_p.add_argument(
        "--source",
        choices=["rejection", "application"],
        default=None,
        help="Load from a single source only (default: both)",
    )

    sub.add_parser("status", help="Show current interview counts in the database")
    sub.add_parser("calendar", help="(Future) Load interviews from Google Calendar")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "load":
        load(dry_run=args.dry_run, source_filter=args.source)
    elif args.command == "status":
        status()
    elif args.command == "calendar":
        calendar()


if __name__ == "__main__":
    main()
