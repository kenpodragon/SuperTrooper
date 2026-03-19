"""
Content sections ETL loader for SuperTroopers.

Parses markdown documents into structured content_sections rows.
Handles: CANDIDATE_PROFILE.md, REJECTION_ANALYSIS.md, APPLICATION_HISTORY.md, EMAIL_SCAN_DEEP.md

Each document is split by ## and ### headers into sections/subsections.
Full document reconstruction: SELECT content FROM content_sections
    WHERE source_document = 'X' ORDER BY sort_order

Usage:
    python load_content_sections.py [--file PATH] [--doc NAME] [--dry-run]
    python load_content_sections.py --all

Source:
    Notes/*.md files
"""

import argparse
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

from db_config import get_db_config

# Map of document names to file paths (relative to project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOCUMENT_MAP = {
    "candidate_profile": PROJECT_ROOT / "Notes" / "CANDIDATE_PROFILE.md",
    "rejection_analysis": PROJECT_ROOT / "Notes" / "REJECTION_ANALYSIS.md",
    "application_history": PROJECT_ROOT / "Notes" / "APPLICATION_HISTORY.md",
    "email_scan_deep": PROJECT_ROOT / "Notes" / "EMAIL_SCAN_DEEP.md",
    "salary_research": PROJECT_ROOT / "Notes" / "SALARY_RESEARCH.md",
    "voice_guide": PROJECT_ROOT / "Notes" / "VOICE_GUIDE.md",
}

# Also check Archived/Notes/ as fallback
ARCHIVE_MAP = {
    k: PROJECT_ROOT / "Archived" / "Notes" / v.name
    for k, v in DOCUMENT_MAP.items()
}


def parse_markdown_sections(text: str) -> list[dict]:
    """Parse markdown into sections by ## and ### headers.

    Returns list of dicts with:
        section: the ## header text
        subsection: the ### header text (or None)
        content: everything under that header until the next header
        sort_order: sequential order for reconstruction
    """
    sections = []
    current_section = "Preamble"
    current_subsection = None
    current_content = []
    sort_order = 0

    def flush():
        nonlocal sort_order
        content = "\n".join(current_content).strip()
        if content:
            sections.append({
                "section": current_section,
                "subsection": current_subsection,
                "content": content,
                "sort_order": sort_order,
            })
            sort_order += 1

    for line in text.splitlines():
        # ## Section header
        if re.match(r"^## ", line):
            flush()
            current_section = line.lstrip("# ").strip()
            current_subsection = None
            current_content = []
        # ### Subsection header
        elif re.match(r"^### ", line):
            flush()
            current_subsection = line.lstrip("# ").strip()
            current_content = []
        else:
            current_content.append(line)

    flush()  # final section
    return sections


def load_document(conn, doc_name: str, file_path: Path, dry_run: bool = False):
    """Parse a markdown file and load into content_sections."""
    if not file_path.exists():
        print(f"  SKIP: {file_path} not found")
        return 0

    text = file_path.read_text(encoding="utf-8")
    sections = parse_markdown_sections(text)

    if dry_run:
        print(f"  DRY RUN: {doc_name} -> {len(sections)} sections")
        for s in sections[:5]:
            sub = f" > {s['subsection']}" if s['subsection'] else ""
            print(f"    [{s['sort_order']}] {s['section']}{sub} ({len(s['content'])} chars)")
        if len(sections) > 5:
            print(f"    ... and {len(sections) - 5} more")
        return len(sections)

    cur = conn.cursor()

    # Clear existing rows for this document
    cur.execute("DELETE FROM content_sections WHERE source_document = %s", (doc_name,))
    deleted = cur.rowcount
    if deleted:
        print(f"  Cleared {deleted} existing rows for {doc_name}")

    # Insert new sections
    for s in sections:
        # Detect content format
        content_format = "markdown"
        if "|" in s["content"] and "---" in s["content"]:
            content_format = "table"
        elif s["content"].startswith("- ") or s["content"].startswith("1. "):
            content_format = "list"

        cur.execute(
            """
            INSERT INTO content_sections
                (source_document, section, subsection, sort_order, content, content_format)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (doc_name, s["section"], s["subsection"], s["sort_order"],
             s["content"], content_format),
        )

    conn.commit()
    print(f"  Loaded {len(sections)} sections for {doc_name}")
    return len(sections)


def main():
    parser = argparse.ArgumentParser(description="Load markdown documents into content_sections")
    parser.add_argument("--file", help="Path to a specific markdown file")
    parser.add_argument("--doc", help="Document name (candidate_profile, rejection_analysis, etc.)")
    parser.add_argument("--all", action="store_true", help="Load all known documents")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, don't write to DB")
    args = parser.parse_args()

    if not args.all and not args.doc and not args.file:
        args.all = True  # default to loading all

    config = get_db_config()
    conn = psycopg2.connect(**config)
    total = 0

    try:
        if args.all:
            print("Loading all content documents...")
            for doc_name, file_path in DOCUMENT_MAP.items():
                # Try primary path first, then archived
                if not file_path.exists() and doc_name in ARCHIVE_MAP:
                    file_path = ARCHIVE_MAP[doc_name]
                print(f"\n{doc_name}:")
                total += load_document(conn, doc_name, file_path, args.dry_run)
        elif args.file and args.doc:
            total = load_document(conn, args.doc, Path(args.file), args.dry_run)
        elif args.doc and args.doc in DOCUMENT_MAP:
            total = load_document(conn, args.doc, DOCUMENT_MAP[args.doc], args.dry_run)
        else:
            print(f"Unknown document: {args.doc}")
            print(f"Known documents: {', '.join(DOCUMENT_MAP.keys())}")
            sys.exit(1)

        print(f"\nTotal: {total} sections loaded")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
