"""
030_migrate_recipes_v2.py — Convert v1 flat-slot recipes to v2 array-based format.

Non-destructive: backs up original recipe JSON to recipe_v1_backup before converting.
Idempotent: skips recipes already at recipe_version=2 or with existing backup.

Usage:
    python code/db/migrations/030_migrate_recipes_v2.py
    python code/db/migrations/030_migrate_recipes_v2.py --dry-run
"""

import json
import re
import sys
import psycopg2
from collections import defaultdict

DB_CONFIG = {
    "host": "localhost",
    "port": 5555,
    "dbname": "supertroopers",
    "user": "supertroopers",
    "password": "WUHD8fBisb57FS4Q3bdvfuvgnim9fL1c",
}

DRY_RUN = "--dry-run" in sys.argv


# ---------------------------------------------------------------------------
# Ref conversion helpers
# ---------------------------------------------------------------------------

def convert_ref(val: dict) -> dict:
    """Convert a v1 ref value to v2 format.

    v1: {"table": "X", "id": N, "column": "Y"}  or  {"id": N, "slot": "Y", "table": "X"}
    v2: {"ref": "X", "id": N}

    v1: {"table": "X", "ids": [...], "column": "Y"}
    v2: {"ref": "X", "ids": [...]}

    v1: {"literal": "text"}
    v2: {"literal": "text"}  (unchanged)
    """
    if "literal" in val:
        return {"literal": val["literal"]}
    if "table" in val:
        out = {"ref": val["table"]}
        if "id" in val:
            out["id"] = val["id"]
        if "ids" in val:
            out["ids"] = val["ids"]
        return out
    # Unknown format — pass through
    return val


# ---------------------------------------------------------------------------
# Slot classification regex patterns
# ---------------------------------------------------------------------------

RE_HEADER = re.compile(r"^HEADER_(NAME|CONTACT)$")
RE_HIGHLIGHT = re.compile(r"^HIGHLIGHT_(\d+)$")
RE_HIGHLIGHTS_PLURAL = re.compile(r"^HIGHLIGHTS$")
RE_SUMMARY = re.compile(r"^SUMMARY$")
RE_HEADLINE = re.compile(r"^HEADLINE$")

RE_JOB_HEADER = re.compile(r"^JOB_(\d+)_HEADER$")
RE_JOB_TITLE = re.compile(r"^JOB_(\d+)_TITLE(?:_(\d+))?$")
RE_JOB_SUBTITLE = re.compile(r"^JOB_(\d+)_SUBTITLE(?:_(\d+))?$")
RE_JOB_INTRO = re.compile(r"^JOB_(\d+)_INTRO(?:_(\d+))?$")
RE_JOB_BULLET = re.compile(r"^JOB_(\d+)_BULLET_(\d+)$")
RE_JOB_BULLETS_PLURAL = re.compile(r"^JOB_(\d+)_BULLETS$")

RE_CERT = re.compile(r"^CERT_(\d+)$")
RE_EDUCATION = re.compile(r"^EDUCATION_(\d+)$")
RE_ADDL_EXP = re.compile(r"^ADDL_EXP_(\d+)$")

RE_TECH_SKILLS = re.compile(r"^TECH_SKILLS$")
RE_OTHER_SKILLS = re.compile(r"^OTHER_SKILLS_(\d+)$")
RE_KEYWORDS = re.compile(r"^KEYWORDS(?:_(\d+))?$")
RE_EXEC_KEYWORDS = re.compile(r"^EXEC_KEYWORDS$")
RE_TECH_KEYWORDS = re.compile(r"^TECH_KEYWORDS$")

RE_REF_SECTION = re.compile(r"^REF_")


def is_v1_flat(recipe: dict) -> bool:
    """Detect whether a recipe is v1 flat-slot format.

    v1 recipes have uppercase keys like HEADER_NAME, JOB_1_BULLET_1, etc.
    v2/starter recipes have lowercase keys like 'sections', 'role_type', 'bullet_ids'.
    """
    if not recipe:
        return False
    keys = set(recipe.keys())
    # If it has any of these v2/starter keys, it's not flat v1
    v2_keys = {"sections", "role_type", "bullet_ids", "auto_generated",
               "header", "experience", "highlights", "skills",
               "education", "certifications", "additional_experience", "custom"}
    if keys & v2_keys:
        return False
    # If it has uppercase keys typical of v1
    uppercase_keys = [k for k in keys if k == k.upper() and len(k) > 2]
    return len(uppercase_keys) > 0


def convert_v1_to_v2(recipe: dict) -> dict:
    """Convert a v1 flat-slot recipe dict to v2 array-based format."""
    v2 = {}

    # Accumulators
    header_refs = {}
    highlights = []
    experience_map = defaultdict(lambda: {
        "header": None, "titles": [], "subtitles": [], "intros": [], "bullets": []
    })
    certifications = []
    education = []
    additional_experience = []
    skills = []
    custom = {}

    for key, val in sorted(recipe.items()):
        # --- HEADER ---
        m = RE_HEADER.match(key)
        if m:
            header_refs[m.group(1).lower()] = val
            continue

        # --- HEADLINE ---
        if RE_HEADLINE.match(key):
            v2["headline"] = convert_ref(val)
            continue

        # --- SUMMARY ---
        if RE_SUMMARY.match(key):
            v2["summary"] = convert_ref(val)
            continue

        # --- HIGHLIGHTS (plural, recipe 10 style) ---
        if RE_HIGHLIGHTS_PLURAL.match(key):
            ref = convert_ref(val)
            if "ids" in ref:
                for bid in ref["ids"]:
                    highlights.append({"ref": ref.get("ref", "bullets"), "id": bid})
            else:
                highlights.append(ref)
            continue

        # --- HIGHLIGHT_N ---
        m = RE_HIGHLIGHT.match(key)
        if m:
            highlights.append((int(m.group(1)), convert_ref(val)))
            continue

        # --- JOB_N_HEADER ---
        m = RE_JOB_HEADER.match(key)
        if m:
            job_n = int(m.group(1))
            ref = convert_ref(val)
            experience_map[job_n]["header"] = ref
            continue

        # --- JOB_N_TITLE or JOB_N_TITLE_M ---
        m = RE_JOB_TITLE.match(key)
        if m:
            job_n = int(m.group(1))
            sub_n = int(m.group(2)) if m.group(2) else 1
            experience_map[job_n]["titles"].append((sub_n, convert_ref(val)))
            continue

        # --- JOB_N_SUBTITLE_M ---
        m = RE_JOB_SUBTITLE.match(key)
        if m:
            job_n = int(m.group(1))
            sub_n = int(m.group(2)) if m.group(2) else 1
            experience_map[job_n]["subtitles"].append((sub_n, convert_ref(val)))
            continue

        # --- JOB_N_INTRO or JOB_N_INTRO_M ---
        m = RE_JOB_INTRO.match(key)
        if m:
            job_n = int(m.group(1))
            sub_n = int(m.group(2)) if m.group(2) else 1
            experience_map[job_n]["intros"].append((sub_n, convert_ref(val)))
            continue

        # --- JOB_N_BULLET_M ---
        m = RE_JOB_BULLET.match(key)
        if m:
            job_n = int(m.group(1))
            bullet_n = int(m.group(2))
            experience_map[job_n]["bullets"].append((bullet_n, convert_ref(val)))
            continue

        # --- JOB_N_BULLETS (plural, recipe 10 style) ---
        m = RE_JOB_BULLETS_PLURAL.match(key)
        if m:
            job_n = int(m.group(1))
            ref = convert_ref(val)
            if "ids" in ref:
                for i, bid in enumerate(ref["ids"], 1):
                    experience_map[job_n]["bullets"].append(
                        (i, {"ref": ref.get("ref", "bullets"), "id": bid})
                    )
            else:
                experience_map[job_n]["bullets"].append((1, ref))
            continue

        # --- CERT_N ---
        m = RE_CERT.match(key)
        if m:
            certifications.append((int(m.group(1)), convert_ref(val)))
            continue

        # --- EDUCATION_N ---
        m = RE_EDUCATION.match(key)
        if m:
            education.append((int(m.group(1)), convert_ref(val)))
            continue

        # --- ADDL_EXP_N ---
        m = RE_ADDL_EXP.match(key)
        if m:
            additional_experience.append((int(m.group(1)), convert_ref(val)))
            continue

        # --- TECH_SKILLS ---
        if RE_TECH_SKILLS.match(key):
            skills.append(("0_TECH", convert_ref(val)))
            continue

        # --- OTHER_SKILLS_N ---
        m = RE_OTHER_SKILLS.match(key)
        if m:
            skills.append((f"1_OTHER_{m.group(1)}", convert_ref(val)))
            continue

        # --- KEYWORDS_N or KEYWORDS ---
        m = RE_KEYWORDS.match(key)
        if m:
            n = m.group(1) or "0"
            skills.append((f"2_KW_{n}", convert_ref(val)))
            continue

        # --- EXEC_KEYWORDS ---
        if RE_EXEC_KEYWORDS.match(key):
            skills.append(("3_EXEC_KW", convert_ref(val)))
            continue

        # --- TECH_KEYWORDS ---
        if RE_TECH_KEYWORDS.match(key):
            skills.append(("4_TECH_KW", convert_ref(val)))
            continue

        # --- REF_* and anything else → custom ---
        custom[key] = convert_ref(val)

    # -----------------------------------------------------------------------
    # Assemble v2 structure
    # -----------------------------------------------------------------------

    # Header — pick the resume_header ref, or create default
    if header_refs:
        # Prefer the one with table=resume_header
        for part, val in header_refs.items():
            if val.get("table") == "resume_header" or val.get("ref") == "resume_header":
                v2["header"] = convert_ref(val)
                break
        if "header" not in v2:
            # Just use the first one
            v2["header"] = convert_ref(list(header_refs.values())[0])
    else:
        v2["header"] = {"ref": "resume_header", "id": 1}

    # Headline — default if missing
    if "headline" not in v2:
        v2["headline"] = {"literal": ""}

    # Summary already set above if present

    # Highlights — sort by index, extract values
    if highlights:
        if all(isinstance(h, tuple) for h in highlights):
            v2["highlights"] = [h[1] for h in sorted(highlights, key=lambda x: x[0])]
        else:
            # Already flat refs (from HIGHLIGHTS plural)
            v2["highlights"] = highlights

    # Experience — sort by job number, build array
    if experience_map:
        exp_array = []
        for job_n in sorted(experience_map.keys()):
            job = experience_map[job_n]
            entry = {}

            # Header ref (career_history or literal)
            if job["header"]:
                entry["header"] = job["header"]

            # Titles
            if job["titles"]:
                titles_sorted = [t[1] for t in sorted(job["titles"], key=lambda x: x[0])]
                if len(titles_sorted) == 1:
                    entry["title"] = titles_sorted[0]
                else:
                    entry["titles"] = titles_sorted

            # Subtitles
            if job["subtitles"]:
                subs_sorted = [s[1] for s in sorted(job["subtitles"], key=lambda x: x[0])]
                if len(subs_sorted) == 1:
                    entry["subtitle"] = subs_sorted[0]
                else:
                    entry["subtitles"] = subs_sorted

            # Synopsis (intro)
            if job["intros"]:
                intros_sorted = [i[1] for i in sorted(job["intros"], key=lambda x: x[0])]
                if len(intros_sorted) == 1:
                    entry["synopsis"] = intros_sorted[0]
                else:
                    entry["synopsis"] = intros_sorted[0]
                    entry["additional_intros"] = intros_sorted[1:]

            # Bullets
            if job["bullets"]:
                entry["bullets"] = [b[1] for b in sorted(job["bullets"], key=lambda x: x[0])]

            exp_array.append(entry)

        v2["experience"] = exp_array

    # Skills — sort by category key
    if skills:
        v2["skills"] = [s[1] for s in sorted(skills, key=lambda x: x[0])]

    # Education
    if education:
        v2["education"] = [e[1] for e in sorted(education, key=lambda x: x[0])]

    # Certifications
    if certifications:
        v2["certifications"] = [c[1] for c in sorted(certifications, key=lambda x: x[0])]

    # Additional experience
    if additional_experience:
        v2["additional_experience"] = [a[1] for a in sorted(additional_experience, key=lambda x: x[0])]

    # Custom catch-all
    if custom:
        v2["custom"] = custom

    return v2


def convert_starter_to_v2(recipe: dict) -> dict:
    """Convert starter recipes (11-13) that have 'sections' key to v2 format.

    These already have a semi-structured format with sections.experience.entries,
    role_type, bullet_ids. Normalize them to match v2 spec.
    """
    v2 = {}

    sections = recipe.get("sections", {})

    # Header
    header = sections.get("header", {})
    if header:
        v2["header"] = convert_ref(header) if ("table" in header or "literal" in header) else header
    else:
        v2["header"] = {"ref": "resume_header", "id": 1}

    v2["headline"] = {"literal": ""}

    # Summary
    summary = sections.get("summary", {})
    if summary:
        v2["summary"] = convert_ref(summary) if ("table" in summary or "literal" in summary) else summary

    # Experience
    exp = sections.get("experience", {})
    entries = exp.get("entries", [])
    if entries:
        exp_array = []
        for entry in entries:
            v2_entry = {}
            if "career_history_id" in entry:
                v2_entry["header"] = {"ref": "career_history", "id": entry["career_history_id"]}
            if "title" in entry:
                v2_entry["title"] = {"literal": entry["title"]}
            if "employer" in entry:
                v2_entry["employer"] = {"literal": entry["employer"]}
            exp_array.append(v2_entry)
        v2["experience"] = exp_array

    # Highlights
    highlights = sections.get("highlights", {})
    if highlights:
        v2["highlights"] = convert_ref(highlights) if ("table" in highlights or "literal" in highlights) else highlights

    # Skills
    skills = sections.get("skills", {})
    if skills:
        v2["skills"] = convert_ref(skills) if ("table" in skills or "literal" in skills) else skills

    # Education
    edu = sections.get("education", {})
    if edu:
        v2["education"] = convert_ref(edu) if ("table" in edu or "literal" in edu) else edu

    # Certifications
    certs = sections.get("certifications", {})
    if certs:
        v2["certifications"] = convert_ref(certs) if ("table" in certs or "literal" in certs) else certs

    # Preserve extra metadata
    if "role_type" in recipe:
        v2["role_type"] = recipe["role_type"]
    if "bullet_ids" in recipe:
        v2["bullet_ids"] = recipe["bullet_ids"]
    if "auto_generated" in recipe:
        v2["auto_generated"] = recipe["auto_generated"]

    return v2


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Fetch all recipes
        cur.execute("""
            SELECT id, name, recipe, recipe_version, recipe_v1_backup
            FROM resume_recipes
            ORDER BY id
        """)
        rows = cur.fetchall()

        converted = 0
        skipped = 0
        errors = []

        for row in rows:
            rid, name, recipe_json, version, backup = row
            recipe = recipe_json if isinstance(recipe_json, dict) else json.loads(recipe_json) if recipe_json else {}

            # Skip if already v2
            if version == 2:
                print(f"  SKIP id={rid} '{name}' — already v2")
                skipped += 1
                continue

            # Skip empty recipes
            if not recipe:
                print(f"  SKIP id={rid} '{name}' — empty recipe")
                skipped += 1
                continue

            try:
                # Determine conversion strategy
                if is_v1_flat(recipe):
                    v2 = convert_v1_to_v2(recipe)
                    strategy = "flat→v2"
                elif "sections" in recipe:
                    v2 = convert_starter_to_v2(recipe)
                    strategy = "starter→v2"
                else:
                    print(f"  SKIP id={rid} '{name}' — unrecognized format, keys: {list(recipe.keys())[:5]}")
                    skipped += 1
                    continue

                if DRY_RUN:
                    print(f"  DRY-RUN id={rid} '{name}' ({strategy})")
                    print(f"    v2 sections: {list(v2.keys())}")
                    if "experience" in v2:
                        print(f"    experience entries: {len(v2['experience'])}")
                    converted += 1
                else:
                    # Backup and update
                    cur.execute("""
                        UPDATE resume_recipes
                        SET recipe_v1_backup = recipe,
                            recipe = %s,
                            recipe_version = 2,
                            updated_at = NOW()
                        WHERE id = %s AND (recipe_v1_backup IS NULL OR recipe_version = 1)
                    """, (json.dumps(v2), rid))

                    if cur.rowcount == 1:
                        print(f"  OK   id={rid} '{name}' ({strategy}) — {list(v2.keys())}")
                        converted += 1
                    else:
                        print(f"  SKIP id={rid} '{name}' — already backed up or no match")
                        skipped += 1

            except Exception as e:
                errors.append((rid, name, str(e)))
                print(f"  ERR  id={rid} '{name}' — {e}")

        if not DRY_RUN and not errors:
            conn.commit()
            print(f"\nCommitted. Converted: {converted}, Skipped: {skipped}")
        elif DRY_RUN:
            print(f"\nDry run complete. Would convert: {converted}, Would skip: {skipped}")
        else:
            conn.rollback()
            print(f"\nRolled back due to errors: {errors}")

    except Exception as e:
        conn.rollback()
        print(f"Fatal error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    print(f"{'DRY RUN — ' if DRY_RUN else ''}Migrating v1 recipes to v2...\n")
    main()
