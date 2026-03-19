"""
Voice rules ETL loader for SuperTroopers.

Parses VOICE_GUIDE.md into structured voice_rules rows.
Each banned word, construction, pattern, and check item becomes its own row.

Usage:
    python load_voice_rules.py [--file PATH] [--dry-run]

Source:
    Notes/VOICE_GUIDE.md (8 parts, ~580 lines)
"""

import argparse
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

from db_config import get_db_config

DEFAULT_FILE = str(
    Path(__file__).resolve().parent.parent.parent / "Notes" / "VOICE_GUIDE.md"
)


def parse_voice_guide(text: str) -> list[dict]:
    """Parse the Voice Guide into individual rules."""
    rules = []
    sort_order = 0

    # --- PART 1: Banned Vocabulary ---
    part1_banned = _extract_between(text, "### Never Use (Hard Ban)", "### Extreme Caution")
    if part1_banned:
        # Parse each category block
        for label, subcat in [
            ("Buzzword Verbs:", "buzzword_verb"),
            ("Buzzword Adjectives:", "buzzword_adjective"),
            ("Buzzword Nouns/Phrases:", "buzzword_noun"),
            ("Resume Filler:", "resume_filler"),
        ]:
            block = _extract_between(part1_banned, f"**{label}**", "**")
            if block:
                words = [w.strip().strip('"').strip("'") for w in re.split(r'[,\n]', block) if w.strip() and not w.strip().startswith("**")]
                for word in words:
                    if word and len(word) > 1:
                        rules.append({
                            "part": 1, "part_title": "Banned Vocabulary",
                            "category": "banned_word", "subcategory": subcat,
                            "rule_text": word, "explanation": None,
                            "examples_bad": None, "examples_good": None,
                            "sort_order": sort_order,
                        })
                        sort_order += 1

    # Caution words
    caution = _extract_between(text, "### Extreme Caution", "---")
    if caution:
        for line in caution.splitlines():
            m = re.match(r"^- \*\*(\w+(?:/\w+)*)\*\*\s*--?\s*(.*)", line)
            if m:
                rules.append({
                    "part": 1, "part_title": "Banned Vocabulary",
                    "category": "caution_word", "subcategory": None,
                    "rule_text": m.group(1),
                    "explanation": m.group(2).strip(),
                    "examples_bad": None, "examples_good": None,
                    "sort_order": sort_order,
                })
                sort_order += 1

    # --- PART 2: Banned Constructions ---
    part2_sections = [
        ("False Authority Claims", "false_authority"),
        ("Vague Impact Statements", "vague_impact"),
        ("Responsibility Lists (Not Achievement Lists)", "responsibility_list"),
        ("AI Fiction Crutches (in Cover Letters/Outreach)", "ai_fiction_crutch"),
        ("Dramatic Pivots (in Cover Letters)", "dramatic_pivot"),
    ]
    for title, subcat in part2_sections:
        block = _extract_section_by_header(text, f"### {title}")
        if not block:
            continue
        never_items = re.findall(r'^- "([^"]+)"', block, re.MULTILINE)
        why = _extract_between(block, "**Why they fail:**", "\n\n")
        bad_examples = re.findall(r'Bad:\s*"([^"]+)"', block)
        good_examples = re.findall(r'Good:\s*"([^"]+)"', block)

        for item in never_items:
            rules.append({
                "part": 2, "part_title": "Banned Constructions",
                "category": "banned_construction", "subcategory": subcat,
                "rule_text": item,
                "explanation": why.strip() if why else None,
                "examples_bad": bad_examples if bad_examples else None,
                "examples_good": good_examples if good_examples else None,
                "sort_order": sort_order,
            })
            sort_order += 1

    # --- PART 3: Structural Tells ---
    part3_sections = [
        ("The Generic Summary Trap", "generic_summary"),
        ("Bullet Point Uniformity", "bullet_uniformity"),
        ("Keyword Stuffing", "keyword_stuffing"),
        ("The Perfect Narrative", "perfect_narrative"),
    ]
    for title, subcat in part3_sections:
        block = _extract_section_by_header(text, f"### {title}")
        if block:
            rules.append({
                "part": 3, "part_title": "Structural Tells",
                "category": "structural_tell", "subcategory": subcat,
                "rule_text": title,
                "explanation": _clean_block(block),
                "examples_bad": None, "examples_good": None,
                "sort_order": sort_order,
            })
            sort_order += 1

    # --- PART 4: Resume-Specific Rules ---
    part4_sections = [
        ("STAR Format Enforcement", "star_format"),
        ("Metrics Integrity Rules", "metrics_integrity"),
        ("Concrete Detail Requirements", "concrete_details"),
        ("What NOT to Include", "exclusions"),
    ]
    for title, subcat in part4_sections:
        block = _extract_section_by_header(text, f"### {title}")
        if block:
            rules.append({
                "part": 4, "part_title": "Resume-Specific Rules",
                "category": "resume_rule", "subcategory": subcat,
                "rule_text": title,
                "explanation": _clean_block(block),
                "examples_bad": None, "examples_good": None,
                "sort_order": sort_order,
            })
            sort_order += 1

    # --- PART 5: Cover Letter & Outreach Rules ---
    part5_sections = [
        ("Stephen's Voice", "voice_profile"),
        ("Structure", "cover_structure"),
        ("Anti-AI Patterns", "anti_ai_cover"),
    ]
    for title, subcat in part5_sections:
        block = _extract_section_by_header(text, f"### {title}")
        if block:
            rules.append({
                "part": 5, "part_title": "Cover Letter & Outreach Rules",
                "category": "cover_letter_rule", "subcategory": subcat,
                "rule_text": title,
                "explanation": _clean_block(block),
                "examples_bad": None, "examples_good": None,
                "sort_order": sort_order,
            })
            sort_order += 1

    # --- PART 6: Final Check (items 1-9) ---
    final_check_block = _extract_between(text, "## PART 6: THE FINAL CHECK", "## Quick Reference")
    if final_check_block:
        checks = re.findall(
            r'(\d+)\.\s+\*\*([^*]+)\*\*\s*(.*?)(?=\n\d+\.|\Z)',
            final_check_block, re.DOTALL
        )
        for num, name, desc in checks:
            rules.append({
                "part": 6, "part_title": "The Final Check",
                "category": "final_check", "subcategory": None,
                "rule_text": f"{num}. {name.strip()}",
                "explanation": desc.strip(),
                "examples_bad": None, "examples_good": None,
                "sort_order": sort_order,
            })
            sort_order += 1

    # --- Quick Reference table ---
    qr_block = _extract_between(text, "## Quick Reference:", "## PART 6B")
    if qr_block:
        rows = re.findall(r'\|\s*"([^"]+)"\s*\|\s*([^|]+)\|', qr_block)
        for bad, good in rows:
            rules.append({
                "part": 6, "part_title": "Quick Reference",
                "category": "quick_reference", "subcategory": None,
                "rule_text": bad.strip(),
                "explanation": None,
                "examples_bad": [bad.strip()],
                "examples_good": [good.strip()],
                "sort_order": sort_order,
            })
            sort_order += 1

    # --- PART 6B: LinkedIn-Specific ---
    part6b_sections = [
        ("1. LinkedIn-Specific Banned Phrases", "linkedin_banned"),
        ("2. Engagement Bait Patterns to Avoid", "engagement_bait"),
        ("3. LinkedIn Post Structure Tells", "post_structure"),
        ("4. Comment and Engagement Patterns", "comment_pattern"),
        ("5. Profile Section Anti-Patterns", "profile_antipattern"),
    ]
    for title, subcat in part6b_sections:
        block = _extract_section_by_header(text, f"### {title}")
        if block:
            never_items = re.findall(r'^- "([^"]+)"', block, re.MULTILINE)
            if never_items:
                for item in never_items:
                    rules.append({
                        "part": 6, "part_title": "LinkedIn-Specific Anti-AI Patterns",
                        "category": "linkedin_pattern", "subcategory": subcat,
                        "rule_text": item,
                        "explanation": None,
                        "examples_bad": None, "examples_good": None,
                        "sort_order": sort_order,
                    })
                    sort_order += 1
            else:
                rules.append({
                    "part": 6, "part_title": "LinkedIn-Specific Anti-AI Patterns",
                    "category": "linkedin_pattern", "subcategory": subcat,
                    "rule_text": title,
                    "explanation": _clean_block(block),
                    "examples_bad": None, "examples_good": None,
                    "sort_order": sort_order,
                })
                sort_order += 1

    # --- PART 7: Stephen-isms ---
    part7_sections = [
        ("Signature Constructions", "signature_construction"),
        ("Rhythm & Structure", "rhythm_structure"),
        ("Punctuation DNA", "punctuation"),
        ("Openings", "openings"),
        ("Closings", "closings"),
        ("Tone Markers", "tone_markers"),
        ("What Stephen Would Never Say", "never_say"),
        ("The Voice in One Paragraph", "voice_summary"),
    ]
    for title, subcat in part7_sections:
        block = _extract_section_by_header(text, f"### {title}")
        if block:
            rules.append({
                "part": 7, "part_title": "Stephen-isms",
                "category": "stephen_ism", "subcategory": subcat,
                "rule_text": title,
                "explanation": _clean_block(block),
                "examples_bad": None, "examples_good": None,
                "sort_order": sort_order,
            })
            sort_order += 1

    # --- PART 8: Context-Specific Patterns ---
    part8_sections = [
        ("Thank-You Notes", "thank_you"),
        ("Networking / Outreach Messages", "networking"),
        ("Interview Answers", "interview_answers"),
    ]
    for title, subcat in part8_sections:
        block = _extract_section_by_header(text, f"### {title}")
        if block:
            rules.append({
                "part": 8, "part_title": "Context-Specific Patterns",
                "category": "context_pattern", "subcategory": subcat,
                "rule_text": title,
                "explanation": _clean_block(block),
                "examples_bad": None, "examples_good": None,
                "sort_order": sort_order,
            })
            sort_order += 1

    return rules


def _extract_between(text: str, start: str, end: str) -> str | None:
    """Extract text between two markers."""
    idx1 = text.find(start)
    if idx1 < 0:
        return None
    idx1 += len(start)
    idx2 = text.find(end, idx1)
    if idx2 < 0:
        return text[idx1:]
    return text[idx1:idx2]


def _extract_section_by_header(text: str, header: str) -> str | None:
    """Extract content under a ### header until the next ### or ## header."""
    pattern = re.escape(header) + r"\n(.*?)(?=\n### |\n## |\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else None


def _clean_block(text: str) -> str:
    """Clean a block of text for storage."""
    # Remove excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def load_rules(conn, rules: list[dict], dry_run: bool = False):
    """Insert voice rules into the database."""
    if dry_run:
        print(f"DRY RUN: {len(rules)} rules parsed")
        cats = {}
        for r in rules:
            cats[r["category"]] = cats.get(r["category"], 0) + 1
        for cat, count in sorted(cats.items()):
            print(f"  {cat}: {count}")
        return

    cur = conn.cursor()

    # Clear existing
    cur.execute("DELETE FROM voice_rules")
    deleted = cur.rowcount
    if deleted:
        print(f"Cleared {deleted} existing rules")

    for r in rules:
        cur.execute(
            """
            INSERT INTO voice_rules
                (part, part_title, category, subcategory, rule_text, explanation,
                 examples_bad, examples_good, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (r["part"], r["part_title"], r["category"], r["subcategory"],
             r["rule_text"], r["explanation"],
             r["examples_bad"], r["examples_good"], r["sort_order"]),
        )

    conn.commit()
    print(f"Loaded {len(rules)} voice rules")


def main():
    parser = argparse.ArgumentParser(description="Load voice guide rules into voice_rules table")
    parser.add_argument("--file", default=DEFAULT_FILE, help="Path to VOICE_GUIDE.md")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, don't write to DB")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    text = file_path.read_text(encoding="utf-8")
    rules = parse_voice_guide(text)

    config = get_db_config()
    conn = psycopg2.connect(**config)

    try:
        load_rules(conn, rules, args.dry_run)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
