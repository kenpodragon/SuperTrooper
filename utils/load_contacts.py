"""
Contacts ETL loader for SuperTroopers.

Parses reference/contact data from CANDIDATE_PROFILE.md and upserts into
the contacts table in PostgreSQL.

Usage:
    python load_contacts.py [--dry-run] [--profile PATH]

Source: Notes/CANDIDATE_PROFILE.md (References section)
"""

import argparse
import os
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras


DEFAULT_PROFILE = str(
    Path(__file__).resolve().parent.parent.parent / "Notes" / "CANDIDATE_PROFILE.md"
)

from db_config import get_db_config


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _strip_bold(text: str) -> str:
    """Remove markdown bold markers."""
    return text.replace("**", "").strip()


def _extract_email(text: str) -> str | None:
    """Pull the first email address from a string."""
    m = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
    return m.group(0) if m else None


def _extract_phone(text: str) -> str | None:
    """Pull the first phone number from a string."""
    m = re.search(r"[\d+().\- ]{7,}", text)
    return m.group(0).strip(" ,") if m else None


def _extract_linkedin(text: str) -> str | None:
    """Pull the first LinkedIn URL from a string."""
    m = re.search(r"https?://(?:www\.)?linkedin\.com/in/[\w-]+/?", text)
    return m.group(0) if m else None


def _classify_strength(section: str, status_text: str) -> str:
    """Determine relationship_strength from section header and status column.

    Rules:
        - Ready to Use + ACTIVE            -> strong
        - Have Letters + Warm/reconnect     -> warm
        - Historical with letter            -> warm
        - Potential (Need to Ask) HIGH      -> warm
        - No Letter / Stale / dead email    -> cold
        - Potential LOW                     -> cold
    """
    status_lower = status_text.lower()

    if section == "ready":
        return "strong"

    if section == "letters":
        if "warm" in status_lower:
            return "warm"
        if "stale" in status_lower:
            return "cold"
        return "warm"  # letters on file = warm default

    if section == "no_letter":
        if "warm" in status_lower:
            return "warm"
        return "cold"

    if section == "potential":
        if "high" in status_lower:
            return "warm"
        if "medium" in status_lower:
            return "warm"
        return "cold"

    return "cold"


def _classify_relationship(rel_text: str) -> str:
    """Map the free-text relationship column to the contacts.relationship enum values.

    Schema comment says: recruiter, hiring_manager, peer, referral, reference, connection.
    """
    r = rel_text.lower()
    if "direct manager" in r or "manager" in r and "managed" not in r:
        return "reference"
    if "direct report" in r or "managed worker" in r or "managed" in r:
        return "reference"
    if "peer" in r or "co-worker" in r:
        return "peer"
    if "administrative" in r:
        return "connection"
    return "reference"


# ---------------------------------------------------------------------------
# Markdown table parsing
# ---------------------------------------------------------------------------

def _parse_table_rows(lines: list[str]) -> list[list[str]]:
    """Parse markdown table lines into a list of cell lists.

    Skips the header row and the separator row (---|---).
    """
    rows = []
    seen_header = False
    seen_separator = False

    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            if seen_header:
                break  # end of table
            continue

        cells = [c.strip() for c in line.split("|")[1:-1]]  # drop empty first/last

        if not seen_header:
            seen_header = True
            continue
        if not seen_separator:
            seen_separator = True
            continue

        rows.append(cells)

    return rows


def parse_references(md_text: str) -> list[dict]:
    """Parse all reference sections from CANDIDATE_PROFILE.md.

    Returns a list of contact dicts ready for DB insertion.
    """
    contacts = []

    # Split into sections by ### headers
    section_pattern = re.compile(
        r"^### References -- (.+)$", re.MULTILINE
    )
    matches = list(section_pattern.finditer(md_text))

    for i, match in enumerate(matches):
        header = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        section_text = md_text[start:end]

        # Determine section category
        if "Ready to Use" in header:
            section_key = "ready"
        elif "Have Letters" in header:
            section_key = "letters"
        elif "No Letter" in header:
            section_key = "no_letter"
        elif "Potential" in header:
            section_key = "potential"
        else:
            continue

        # Find all table lines in this section
        table_lines = [l for l in section_text.split("\n") if l.strip().startswith("|")]
        rows = _parse_table_rows(table_lines)

        for cells in rows:
            contact = _parse_row(cells, section_key)
            if contact:
                contacts.append(contact)

    return contacts


def _parse_row(cells: list[str], section_key: str) -> dict | None:
    """Parse a single markdown table row into a contact dict.

    Handles varying column counts across the four reference tables.
    """
    if len(cells) < 5:
        return None

    if section_key == "ready":
        # Columns: #, Name, Title, Company, Relationship, Contact, What They Can Speak To, Last Used, Status
        if len(cells) < 8:
            return None
        name = _strip_bold(cells[1])
        title = cells[2].strip()
        company = cells[3].strip()
        relationship_raw = cells[4].strip()
        contact_info = cells[5].strip()
        notes_parts = [cells[6].strip()]  # What They Can Speak To
        status = cells[8].strip() if len(cells) > 8 else ""
        last_used = cells[7].strip() if len(cells) > 7 else ""
        if last_used:
            notes_parts.append(f"Last used: {last_used}")
        if status:
            notes_parts.append(f"Status: {_strip_bold(status)}")

    elif section_key == "letters":
        # Columns: #, Name, Title, Company, Relationship, Contact (Last Known), What They Can Speak To, Letter Date, Status
        if len(cells) < 8:
            return None
        name = _strip_bold(cells[1])
        title = cells[2].strip()
        company = cells[3].strip()
        relationship_raw = cells[4].strip()
        contact_info = cells[5].strip()
        notes_parts = [cells[6].strip()]
        letter_date = cells[7].strip() if len(cells) > 7 else ""
        status = cells[8].strip() if len(cells) > 8 else ""
        if letter_date:
            notes_parts.append(f"Letter date: {letter_date}")
        if status:
            notes_parts.append(f"Status: {_strip_bold(status)}")

    elif section_key == "no_letter":
        # Columns: #, Name, Title, Company, Relationship, Contact (Last Known), Best Use Case, Status
        if len(cells) < 7:
            return None
        name = _strip_bold(cells[1])
        title = cells[2].strip()
        company = cells[3].strip()
        relationship_raw = cells[4].strip()
        contact_info = cells[5].strip()
        notes_parts = [cells[6].strip()]  # Best Use Case
        status = cells[7].strip() if len(cells) > 7 else ""
        if status:
            notes_parts.append(f"Status: {_strip_bold(status)}")

    elif section_key == "potential":
        # Columns: #, Name, Context, Company, Relationship, Evidence, Why They Would Be Strong, Priority
        if len(cells) < 7:
            return None
        name = _strip_bold(cells[1])
        title = cells[2].strip()  # Context column used as title
        company = cells[3].strip()
        relationship_raw = cells[4].strip()
        contact_info = ""  # No contact column in this table
        evidence = cells[5].strip()
        why_strong = cells[6].strip()
        status = cells[7].strip() if len(cells) > 7 else ""
        notes_parts = []
        if evidence:
            notes_parts.append(f"Evidence: {evidence}")
        if why_strong:
            notes_parts.append(f"Why strong: {why_strong}")
        if status:
            notes_parts.append(f"Priority: {_strip_bold(status)}")

    else:
        return None

    # Extract structured fields from contact info
    email = _extract_email(contact_info)
    phone = _extract_phone(contact_info)
    linkedin_url = _extract_linkedin(contact_info)

    # Flag likely-dead emails in notes
    if "likely dead" in contact_info.lower() and email:
        notes_parts.append(f"Email may be dead: {email}")

    strength = _classify_strength(section_key, status)
    relationship = _classify_relationship(relationship_raw)

    # Extract company name from parenthetical dates if present
    company_clean = re.sub(r"\s*\([\d\-present]+\)\s*", "", company).strip()

    return {
        "name": name,
        "company": company_clean,
        "title": title,
        "relationship": relationship,
        "email": email,
        "phone": phone,
        "linkedin_url": linkedin_url,
        "relationship_strength": strength,
        "source": "candidate_profile",
        "notes": " | ".join(notes_parts) if notes_parts else None,
    }


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

UPSERT_SQL = """
INSERT INTO contacts (
    name, company, title, relationship, email, phone,
    linkedin_url, relationship_strength, source, notes
)
VALUES (
    %(name)s, %(company)s, %(title)s, %(relationship)s, %(email)s, %(phone)s,
    %(linkedin_url)s, %(relationship_strength)s, %(source)s, %(notes)s
)
ON CONFLICT (name, company)
    DO UPDATE SET
        title                = EXCLUDED.title,
        relationship         = EXCLUDED.relationship,
        email                = COALESCE(EXCLUDED.email, contacts.email),
        phone                = COALESCE(EXCLUDED.phone, contacts.phone),
        linkedin_url         = COALESCE(EXCLUDED.linkedin_url, contacts.linkedin_url),
        relationship_strength = EXCLUDED.relationship_strength,
        source               = EXCLUDED.source,
        notes                = EXCLUDED.notes,
        updated_at           = NOW()
RETURNING id, (xmax = 0) AS inserted;
"""


def ensure_unique_constraint(conn) -> None:
    """Create the unique constraint on (name, company) if it doesn't exist yet."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uq_contacts_name_company'
        """)
        if not cur.fetchone():
            print("  Creating unique constraint uq_contacts_name_company...")
            cur.execute("""
                ALTER TABLE contacts
                ADD CONSTRAINT uq_contacts_name_company
                UNIQUE (name, company);
            """)
            conn.commit()
            print("  Constraint created.")


def load_contacts(contacts: list[dict], dry_run: bool = False) -> dict:
    """Insert/update contacts in the database.

    Returns a summary dict with inserted, updated, and error counts.
    """
    summary = {"inserted": 0, "updated": 0, "errors": 0}

    if dry_run:
        print("\n[DRY RUN] Would load the following contacts:\n")
        for c in contacts:
            strength_tag = f"[{c['relationship_strength']}]"
            print(f"  {strength_tag:<8} {c['name']:<25} {c['company'] or '(none)':<30} {c['relationship']}")
        print(f"\n[DRY RUN] Total: {len(contacts)} contacts")
        return summary

    conn = psycopg2.connect(**get_db_config())
    try:
        ensure_unique_constraint(conn)

        with conn.cursor() as cur:
            for c in contacts:
                try:
                    cur.execute(UPSERT_SQL, c)
                    row = cur.fetchone()
                    row_id, was_insert = row
                    if was_insert:
                        summary["inserted"] += 1
                        print(f"  + INSERT [{c['relationship_strength']}] {c['name']} @ {c['company'] or '(none)'} (id={row_id})")
                    else:
                        summary["updated"] += 1
                        print(f"  ~ UPDATE [{c['relationship_strength']}] {c['name']} @ {c['company'] or '(none)'} (id={row_id})")
                except Exception as e:
                    summary["errors"] += 1
                    print(f"  ! ERROR  {c['name']}: {e}", file=sys.stderr)
                    conn.rollback()
                    continue

        conn.commit()
    finally:
        conn.close()

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser(prog=None):
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Load contacts/references from CANDIDATE_PROFILE.md into SuperTroopers DB",
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help="Path to CANDIDATE_PROFILE.md (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and display contacts without writing to DB",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    profile_path = Path(args.profile)
    if not profile_path.exists():
        print(f"ERROR: Profile not found: {profile_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {profile_path}...")
    md_text = profile_path.read_text(encoding="utf-8")

    print("Parsing references...")
    contacts = parse_references(md_text)
    print(f"Found {len(contacts)} contacts across all reference sections.\n")

    if not contacts:
        print("No contacts found. Check the markdown format.")
        sys.exit(1)

    print("Loading into database..." if not args.dry_run else "Dry run mode:")
    summary = load_contacts(contacts, dry_run=args.dry_run)

    if not args.dry_run:
        print(f"\nDone. Inserted: {summary['inserted']}, "
              f"Updated: {summary['updated']}, "
              f"Errors: {summary['errors']}")


if __name__ == "__main__":
    main()
