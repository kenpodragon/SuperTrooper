"""
Knowledge Base ETL loader for SuperTroopers.

Parses Notes/KNOWLEDGE_BASE.md and loads structured data into PostgreSQL:
  - career_history (employer records)
  - bullets (core, alternate, deep_cut)
  - skills (technologies by category)
  - summary_variants (professional summary by role type)

Usage:
    python load_knowledge_base.py load [--dry-run] [--kb PATH]
    python load_knowledge_base.py clear

Idempotent: uses UPSERT (ON CONFLICT) patterns so re-runs are safe.
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import psycopg2
import psycopg2.extras


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_KB_PATH = str(
    Path(__file__).resolve().parent.parent.parent / "Notes" / "KNOWLEDGE_BASE.md"
)

from db_config import get_db_config

# ---------------------------------------------------------------------------
# Role and industry tag vocabularies (used for classifying inline tags)
# ---------------------------------------------------------------------------

ROLE_TAGS = {
    "CTO", "VP-Eng", "Director", "Architect", "PM", "SWE",
}

# Everything else on a bullet's backtick-tag line is treated as industry/domain.

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _read_kb(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _parse_date(text: str):
    """Best-effort parse of a date string like 'August 2021', 'June 2024',
    '2011', 'February 2026', 'Present'.  Returns a date or None."""
    text = text.strip()
    if not text or text.lower() == "present":
        return None
    # Try "Month Year"
    for fmt in ("%B %Y", "%b %Y", "%Y"):
        try:
            from datetime import datetime
            dt = datetime.strptime(text, fmt)
            return dt.date()
        except ValueError:
            continue
    return None


def _extract_tags_from_line(line: str):
    """Given a line like '  `CTO` `VP-Eng` `Director` `Architect` `manufacturing`',
    return (role_tags, industry_tags) as sorted lists."""
    tags = re.findall(r"`([^`]+)`", line)
    roles = sorted({t for t in tags if t in ROLE_TAGS})
    industries = sorted({t for t in tags if t not in ROLE_TAGS})
    return roles, industries


def _extract_metrics(text: str):
    """Pull dollar amounts, percentages, and before/after numbers from bullet
    text.  Returns a list of dicts suitable for metrics_json."""
    metrics = []
    # Dollar amounts
    for m in re.finditer(r"\$[\d,.]+[BMK]?", text):
        metrics.append({"metric": m.group(), "type": "dollar"})
    # Percentages
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*%", text):
        metrics.append({"metric": f"{m.group(1)}%", "type": "percentage"})
    # Before/after patterns like "from X to Y"
    for m in re.finditer(
        r"from\s+([\d,.]+\s*\w*)\s+to\s+([\d,.]+\s*\w*)", text, re.IGNORECASE
    ):
        metrics.append({
            "type": "before_after",
            "before": m.group(1).strip(),
            "after": m.group(2).strip(),
        })
    return metrics if metrics else None


def _parse_team_size(text: str):
    """Extract a team size integer from header metadata."""
    if not text:
        return None
    nums = re.findall(r"(\d+)", text.replace(",", ""))
    if nums:
        return max(int(n) for n in nums)
    return None


def _parse_budget(text: str):
    """Extract numeric budget in USD from header metadata."""
    if not text:
        return None
    m = re.search(r"\$\s*([\d,.]+)\s*([BMK])?", text)
    if m:
        val = float(m.group(1).replace(",", ""))
        suffix = (m.group(2) or "").upper()
        if suffix == "B":
            val *= 1_000_000_000
        elif suffix == "M":
            val *= 1_000_000
        elif suffix == "K":
            val *= 1_000
        return val
    return None


# ---------------------------------------------------------------------------
# Section parsers
# ---------------------------------------------------------------------------


def parse_summary_variants(text: str):
    """Return list of {role_type, text} dicts from the Professional Summary
    Variants section."""
    # Find the section
    sec_match = re.search(
        r"^## Professional Summary Variants\s*\n(.*?)(?=\n^## |\n^---\s*\n## )",
        text, re.MULTILINE | re.DOTALL,
    )
    if not sec_match:
        return []

    section = sec_match.group(1)
    variants = []
    # Split on ### headers
    parts = re.split(r"^### (.+)$", section, flags=re.MULTILINE)
    # parts[0] is preamble, then alternating title/body
    for i in range(1, len(parts), 2):
        role_type = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if body:
            variants.append({"role_type": role_type, "text": body})

    return variants


def parse_employers(text: str):
    """Return list of employer dicts parsed from Employment History."""
    # Find the Employment History section
    sec_match = re.search(
        r"^## Employment History\s*\n(.*?)(?=\n^## [A-Z])",
        text, re.MULTILINE | re.DOTALL,
    )
    if not sec_match:
        return []

    section = sec_match.group(1)
    employers = []

    # Split on "### Employer -- Title" headers
    emp_splits = re.split(r"^### (.+)$", section, flags=re.MULTILINE)

    for i in range(1, len(emp_splits), 2):
        header = emp_splits[i].strip()
        body = emp_splits[i + 1] if i + 1 < len(emp_splits) else ""

        # Parse header: "Employer -- Title"
        if " -- " in header:
            employer_name, title = header.split(" -- ", 1)
        elif " - " in header:
            employer_name, title = header.split(" - ", 1)
        else:
            employer_name = header
            title = ""
        employer_name = employer_name.strip()
        title = title.strip()

        # Skip non-employer sections (Early Career / Origin Story, etc.)
        if employer_name.startswith("Early Career"):
            continue

        # Parse metadata from the body
        dates_match = re.search(r"\*\*Dates:\*\*\s*(.+?)(?:\||$)", body)
        industry_match = re.search(r"\*\*Industry:\*\*\s*(.+?)(?:\||$)", body)
        location_match = re.search(r"\*\*Location:\*\*\s*(.+?)(?:\||$)", body)
        team_match = re.search(r"\*\*Team:\*\*\s*(.+?)(?:\||$)", body)
        budget_match = re.search(r"\*\*Budget:\*\*\s*(.+?)(?:\||$)", body)
        revenue_match = re.search(r"\*\*Revenue impact:\*\*\s*(.+?)(?:\||$)", body)

        # Parse dates
        start_date = None
        end_date = None
        is_current = False
        if dates_match:
            date_text = dates_match.group(1).strip()
            # Handle parenthetical notes like "(Volunteer...)"
            date_text = re.sub(r"\(.*?\)", "", date_text).strip()
            # Split on " - " or " -- "
            date_parts = re.split(r"\s*[-–]\s*", date_text, maxsplit=1)
            if date_parts:
                start_date = _parse_date(date_parts[0])
            if len(date_parts) > 1:
                if "present" in date_parts[1].lower():
                    is_current = True
                else:
                    end_date = _parse_date(date_parts[1])

        industry = industry_match.group(1).strip() if industry_match else None
        location = location_match.group(1).strip() if location_match else None
        team_size = _parse_team_size(team_match.group(1)) if team_match else None
        budget_usd = _parse_budget(budget_match.group(1)) if budget_match else None
        revenue_impact = revenue_match.group(1).strip() if revenue_match else None

        # Parse section tags
        tags_match = re.search(r"^#### Tags\s*\n(.+?)(?:\n####|\n---|\Z)", body, re.MULTILINE | re.DOTALL)
        employer_tags = []
        if tags_match:
            employer_tags = re.findall(r"`([^`]+)`", tags_match.group(1))

        # Parse technologies
        tech_match = re.search(r"^#### Technologies\s*\n(.+?)(?:\n####|\n---|\Z)", body, re.MULTILINE | re.DOTALL)
        technologies = []
        if tech_match:
            tech_text = tech_match.group(1).strip()
            for line in tech_text.split("\n"):
                line = line.strip().lstrip("- ")
                if line and not line.startswith("**"):
                    technologies.extend([t.strip() for t in line.split(",") if t.strip()])

        # Parse bullets by type
        bullets = []

        # Core Bullets
        for core_match in re.finditer(
            r"^#### Core Bullets.*?\n(.*?)(?=\n#### |\n---|\Z)",
            body, re.MULTILINE | re.DOTALL
        ):
            _parse_bullet_block(core_match.group(1), "core", bullets)

        # Alternate Phrasings
        alt_match = re.search(
            r"^#### Alternate Phrasings\s*\n(.*?)(?=\n#### |\n---|\Z)",
            body, re.MULTILINE | re.DOTALL,
        )
        if alt_match:
            _parse_bullet_block(alt_match.group(1), "alternate", bullets)

        # Deep Cut Stories
        deep_match = re.search(
            r"^#### Deep Cut Stories.*?\n(.*?)(?=\n#### |\n---|\Z)",
            body, re.MULTILINE | re.DOTALL,
        )
        if deep_match:
            _parse_bullet_block(deep_match.group(1), "deep_cut", bullets)

        employers.append({
            "employer": employer_name,
            "title": title,
            "start_date": start_date,
            "end_date": end_date,
            "is_current": is_current,
            "location": location,
            "industry": industry,
            "team_size": team_size,
            "budget_usd": budget_usd,
            "revenue_impact": revenue_impact,
            "tags": employer_tags,
            "technologies": technologies,
            "bullets": bullets,
        })

    return employers


def _parse_bullet_block(block_text: str, bullet_type: str, bullets_list: list):
    """Parse a block of markdown bullet lines into bullet dicts.

    Handles multi-line bullets where continuation lines are indented.
    Handles sub-headers within alternate phrasings blocks.
    """
    lines = block_text.split("\n")
    current_bullet = None
    current_tags_line = None
    current_source = None
    current_detail_recall = "high"
    sub_context = None  # e.g. "As Enterprise AI Platform Architect:"

    for line in lines:
        stripped = line.strip()

        # Sub-header within alternates like **As Senior Software Architect:**
        if stripped.startswith("**") and stripped.endswith("**"):
            # Context header
            sub_context = stripped.strip("*").strip(":").strip()
            continue

        # Detect a new bullet line
        if stripped.startswith("- ") and not stripped.startswith("- **"):
            # Save previous bullet if any
            if current_bullet is not None:
                _finalize_bullet(
                    current_bullet, current_tags_line, current_source,
                    current_detail_recall, bullet_type, sub_context, bullets_list,
                )

            bullet_text = stripped[2:].strip()
            # Check for strikethrough (removed bullets)
            if bullet_text.startswith("~~"):
                current_bullet = None
                current_tags_line = None
                current_source = None
                current_detail_recall = "high"
                continue

            current_bullet = bullet_text
            current_tags_line = None
            current_source = None
            current_detail_recall = "high"

            # Check for low detail recall flag in the bullet itself
            if "LOW DETAIL RECALL" in current_bullet.upper() or "low detail recall" in current_bullet:
                current_detail_recall = "low"

        elif stripped.startswith("`") and current_bullet is not None:
            # Tag line
            current_tags_line = stripped

        elif stripped.startswith("*Source:") and current_bullet is not None:
            current_source = stripped.strip("*").replace("Source:", "").strip()

        elif stripped and current_bullet is not None and not stripped.startswith("-"):
            # Continuation of current bullet
            # Check if it's a source line
            if stripped.startswith("*Source:"):
                current_source = stripped.strip("*").replace("Source:", "").strip()
            elif stripped.startswith("`"):
                current_tags_line = stripped
            elif not stripped.startswith("**") and not stripped.startswith("#"):
                current_bullet += " " + stripped

    # Final bullet
    if current_bullet is not None:
        _finalize_bullet(
            current_bullet, current_tags_line, current_source,
            current_detail_recall, bullet_type, sub_context, bullets_list,
        )


def _finalize_bullet(text, tags_line, source, detail_recall, bullet_type, sub_context, bullets_list):
    """Clean up and append a bullet dict."""
    if not text:
        return

    # Remove trailing source references embedded in text
    text = re.sub(r"\*Source:.*?\*", "", text).strip()
    # Remove any remaining backtick tags from the text itself
    clean_text = re.sub(r"\s*`[^`]+`", "", text).strip()
    # Remove *(low detail recall)* markers
    clean_text = re.sub(r"\s*\*\(low detail recall\)\*", "", clean_text, flags=re.IGNORECASE).strip()
    # Remove **[LOW DETAIL RECALL...]** markers
    clean_text = re.sub(r"\s*\*\*\[LOW DETAIL RECALL.*?\]\*\*", "", clean_text, flags=re.IGNORECASE).strip()

    if not clean_text:
        return

    roles, industries = ([], [])
    if tags_line:
        roles, industries = _extract_tags_from_line(tags_line)

    # Also extract inline tags from the text itself
    inline_tags = re.findall(r"`([^`]+)`", text)
    for t in inline_tags:
        if t in ROLE_TAGS and t not in roles:
            roles.append(t)
        elif t not in ROLE_TAGS and t not in industries:
            industries.append(t)

    metrics = _extract_metrics(clean_text)

    bullets_list.append({
        "text": clean_text,
        "type": bullet_type,
        "role_suitability": sorted(set(roles)),
        "industry_suitability": sorted(set(industries)),
        "tags": sorted(set(roles + industries)),
        "metrics_json": metrics,
        "detail_recall": detail_recall,
        "source_file": source,
        "sub_context": sub_context,
    })


def parse_skills(text: str):
    """Parse the Technologies -- Comprehensive Master List section into
    skill records with categories."""
    sec_match = re.search(
        r"^## Technologies -- Comprehensive Master List\s*\n(.*?)(?=\n^## |\Z)",
        text, re.MULTILINE | re.DOTALL,
    )
    if not sec_match:
        return []

    section = sec_match.group(1)
    skills = []
    current_category = None

    for line in section.split("\n"):
        stripped = line.strip()
        if stripped.startswith("### "):
            current_category = stripped[4:].strip()
        elif stripped and current_category and not stripped.startswith("---"):
            items = [s.strip() for s in stripped.split(",") if s.strip()]
            for item in items:
                # Clean up parentheticals but keep them as part of the name
                skills.append({
                    "name": item,
                    "category": current_category,
                })

    return skills


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------


def get_connection():
    return psycopg2.connect(**get_db_config())


def upsert_summary_variants(cur, variants, dry_run=False):
    """Insert or update summary_variants rows."""
    print(f"\n--- Summary Variants: {len(variants)} found ---")

    for v in variants:
        # Map verbose headers to short role_type values
        short_type = ROLE_TYPE_MAP.get(v["role_type"], v["role_type"])
        row = {"role_type": short_type, "text": v["text"]}

        if dry_run:
            print(f"  [DRY RUN] {short_type}: {v['text'][:80]}...")
            continue

        cur.execute("""
            INSERT INTO summary_variants (role_type, text)
            VALUES (%(role_type)s, %(text)s)
            ON CONFLICT (role_type) DO UPDATE
                SET text = EXCLUDED.text,
                    updated_at = NOW()
        """, row)
        print(f"  Upserted: {short_type}")


def upsert_career_history(cur, employers, dry_run=False):
    """Insert or update career_history rows. Returns a dict mapping
    employer name to career_history ID."""
    print(f"\n--- Career History: {len(employers)} employers found ---")
    employer_id_map = {}

    for emp in employers:
        if dry_run:
            print(f"  [DRY RUN] {emp['employer']} -- {emp['title']}")
            employer_id_map[emp["employer"]] = None
            continue

        cur.execute("""
            INSERT INTO career_history
                (employer, title, start_date, end_date, location, industry,
                 team_size, budget_usd, revenue_impact, is_current)
            VALUES
                (%(employer)s, %(title)s, %(start_date)s, %(end_date)s,
                 %(location)s, %(industry)s, %(team_size)s, %(budget_usd)s,
                 %(revenue_impact)s, %(is_current)s)
            ON CONFLICT ON CONSTRAINT career_history_employer_title_key
            DO UPDATE SET
                start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date,
                location = EXCLUDED.location,
                industry = EXCLUDED.industry,
                team_size = EXCLUDED.team_size,
                budget_usd = EXCLUDED.budget_usd,
                revenue_impact = EXCLUDED.revenue_impact,
                is_current = EXCLUDED.is_current,
                updated_at = NOW()
            RETURNING id
        """, {
            "employer": emp["employer"],
            "title": emp["title"],
            "start_date": emp["start_date"],
            "end_date": emp["end_date"],
            "location": emp["location"],
            "industry": emp["industry"],
            "team_size": emp["team_size"],
            "budget_usd": emp["budget_usd"],
            "revenue_impact": emp["revenue_impact"],
            "is_current": emp["is_current"],
        })
        row = cur.fetchone()
        emp_id = row[0]
        employer_id_map[emp["employer"]] = emp_id
        print(f"  Upserted: {emp['employer']} (id={emp_id})")

    return employer_id_map


def upsert_bullets(cur, employers, employer_id_map, dry_run=False):
    """Insert or update bullet rows linked to career_history."""
    total = sum(len(e["bullets"]) for e in employers)
    print(f"\n--- Bullets: {total} total across all employers ---")
    count = 0

    for emp in employers:
        career_id = employer_id_map.get(emp["employer"])
        for b in emp["bullets"]:
            count += 1
            if dry_run:
                print(f"  [DRY RUN] [{b['type']}] {b['text'][:70]}...")
                continue

            metrics = json.dumps(b["metrics_json"]) if b["metrics_json"] else None

            cur.execute("""
                INSERT INTO bullets
                    (career_history_id, text, type, tags, role_suitability,
                     industry_suitability, metrics_json, detail_recall, source_file)
                VALUES
                    (%(career_history_id)s, %(text)s, %(type)s, %(tags)s,
                     %(role_suitability)s, %(industry_suitability)s,
                     %(metrics_json)s, %(detail_recall)s, %(source_file)s)
                ON CONFLICT (career_history_id, type, md5(text))
                DO UPDATE SET
                    tags = EXCLUDED.tags,
                    role_suitability = EXCLUDED.role_suitability,
                    industry_suitability = EXCLUDED.industry_suitability,
                    metrics_json = EXCLUDED.metrics_json,
                    detail_recall = EXCLUDED.detail_recall,
                    source_file = EXCLUDED.source_file
            """, {
                "career_history_id": career_id,
                "text": b["text"],
                "type": b["type"],
                "tags": b["tags"] or None,
                "role_suitability": b["role_suitability"] or None,
                "industry_suitability": b["industry_suitability"] or None,
                "metrics_json": metrics,
                "detail_recall": b["detail_recall"],
                "source_file": b["source_file"],
            })

    print(f"  Upserted {count} bullets")


def upsert_skills(cur, skills, dry_run=False):
    """Insert or update skill rows."""
    print(f"\n--- Skills: {len(skills)} found ---")

    for s in skills:
        if dry_run:
            print(f"  [DRY RUN] {s['category']}: {s['name']}")
            continue

        cur.execute("""
            INSERT INTO skills (name, category)
            VALUES (%(name)s, %(category)s)
            ON CONFLICT ON CONSTRAINT skills_name_category_key
            DO UPDATE SET
                category = EXCLUDED.category
        """, s)

    print(f"  Upserted {len(skills)} skills")


# ---------------------------------------------------------------------------
# Schema helpers: ensure unique constraints exist for upsert
# ---------------------------------------------------------------------------

# Map verbose KB role type headers to shorter names that fit VARCHAR(50)
ROLE_TYPE_MAP = {
    "CTO / Chief Technology Officer": "CTO",
    "VP of Engineering / VP of Software Engineering": "VP Eng",
    "Director of Engineering": "Director",
    "Enterprise AI / Platform Architect": "AI Architect",
    "Senior Software Architect / Principal Software Engineer": "SW Architect",
    "Technical Program Manager": "PM",
    "Senior Software Engineer": "Sr SWE",
}

CONSTRAINT_DDLS = [
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'career_history_employer_title_key'
        ) THEN
            ALTER TABLE career_history
                ADD CONSTRAINT career_history_employer_title_key UNIQUE (employer, title);
        END IF;
    END $$;
    """,
    # bullets: use a unique index on (career_history_id, type, md5(text))
    # since md5() is a function and can't be in a plain UNIQUE constraint
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_bullets_text_type_career_key
        ON bullets (career_history_id, type, md5(text));
    """,
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'skills_name_category_key'
        ) THEN
            ALTER TABLE skills
                ADD CONSTRAINT skills_name_category_key UNIQUE (name, category);
        END IF;
    END $$;
    """,
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'summary_variants_role_type_key'
        ) THEN
            ALTER TABLE summary_variants
                ADD CONSTRAINT summary_variants_role_type_key UNIQUE (role_type);
        END IF;
    END $$;
    """,
]


def ensure_constraints(cur):
    """Create unique constraints needed for upsert if they don't exist."""
    print("\n--- Ensuring unique constraints for upsert ---")
    for ddl in CONSTRAINT_DDLS:
        cur.execute(ddl)
    print("  Constraints verified")


# ---------------------------------------------------------------------------
# Main commands
# ---------------------------------------------------------------------------


def cmd_load(kb_path: str, dry_run: bool = False):
    """Parse the Knowledge Base and load into the database."""
    print(f"Reading Knowledge Base from: {kb_path}")
    kb_text = _read_kb(kb_path)
    print(f"  {len(kb_text):,} characters read")

    # Parse all sections
    variants = parse_summary_variants(kb_text)
    employers = parse_employers(kb_text)
    skills = parse_skills(kb_text)

    print(f"\nParsed: {len(variants)} summary variants, "
          f"{len(employers)} employers, "
          f"{sum(len(e['bullets']) for e in employers)} bullets, "
          f"{len(skills)} skills")

    if dry_run:
        print("\n=== DRY RUN MODE (no database writes) ===")
        upsert_summary_variants(None, variants, dry_run=True)
        upsert_career_history(None, employers, dry_run=True)
        upsert_bullets(None, employers, {e["employer"]: None for e in employers}, dry_run=True)
        upsert_skills(None, skills, dry_run=True)
        print("\n=== DRY RUN COMPLETE ===")
        return

    print("\nConnecting to database...")
    conn = get_connection()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        ensure_constraints(cur)
        upsert_summary_variants(cur, variants)
        employer_id_map = upsert_career_history(cur, employers)
        upsert_bullets(cur, employers, employer_id_map)
        upsert_skills(cur, skills)
        conn.commit()
        print("\n=== LOAD COMPLETE (committed) ===")
    except Exception:
        conn.rollback()
        print("\n!!! ERROR -- transaction rolled back !!!", file=sys.stderr)
        raise
    finally:
        cur.close()
        conn.close()


def cmd_clear():
    """Delete all ETL-loaded data (bullets, career_history, skills,
    summary_variants).  Asks for confirmation."""
    print("This will DELETE all data from: bullets, career_history, skills, summary_variants")
    answer = input("Type 'yes' to confirm: ")
    if answer.strip().lower() != "yes":
        print("Aborted.")
        return

    conn = get_connection()
    cur = conn.cursor()
    try:
        for table in ("bullets", "career_history", "skills", "summary_variants"):
            cur.execute(f"DELETE FROM {table}")
            print(f"  Cleared {table}: {cur.rowcount} rows deleted")
        conn.commit()
        print("Done.")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser(prog=None):
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Knowledge Base ETL loader for SuperTroopers",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    load_p = sub.add_parser("load", help="Parse KNOWLEDGE_BASE.md and load into DB")
    load_p.add_argument(
        "--kb", default=DEFAULT_KB_PATH,
        help="Path to KNOWLEDGE_BASE.md (default: auto-detected)",
    )
    load_p.add_argument(
        "--dry-run", action="store_true",
        help="Parse and print but do not write to DB",
    )

    sub.add_parser("clear", help="Delete all ETL-loaded data from the DB")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "load":
        cmd_load(args.kb, args.dry_run)
    elif args.command == "clear":
        cmd_clear()


if __name__ == "__main__":
    main()
