"""
037_migrate_to_sections.py — Convert v1 numbered-slot recipes to section-based format.

Groups flat slot keys (CERT_1, JOB_1_BULLET_2, etc.) into section-level structures:
  CERTIFICATIONS: {table, ids: [...]}
  EDUCATION: {table, ids: [...]}
  HIGHLIGHTS: {table, ids: [...]}
  SKILLS: {table, ids: [...]}
  HEADER: {table, id}
  HEADLINE / SUMMARY: pass-through
  EXPERIENCE: [{table, id (company), jobs: [{table, id, synopsis, bullets: {ids}}]}]

Non-destructive:
  - Backs up original recipe to recipe_v1_backup (if not already set)
  - Sets recipe_version = 2 after conversion
  - Skips recipes already in section format (has lowercase section keys)
  - Idempotent: safe to re-run

Usage:
    python db/migrations/037_migrate_to_sections.py --dry-run   # preview only
    python db/migrations/037_migrate_to_sections.py             # execute
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
# Regex patterns for v1 slot keys
# ---------------------------------------------------------------------------

RE_HEADER_NAME    = re.compile(r"^HEADER_NAME$")
RE_HEADER_CONTACT = re.compile(r"^HEADER_CONTACT(?:_\d+)?$")
RE_HEADLINE       = re.compile(r"^HEADLINE$")
RE_SUMMARY        = re.compile(r"^SUMMARY(?:_\d+)?$")

RE_HIGHLIGHT      = re.compile(r"^HIGHLIGHT_(\d+)$")
RE_HIGHLIGHTS     = re.compile(r"^HIGHLIGHTS$")

RE_CERT           = re.compile(r"^CERT(?:IFICATION)?_(\d+)$")
RE_EDUCATION      = re.compile(r"^EDUCATION_(\d+)$")
RE_ADDL_EXP       = re.compile(r"^ADDL_EXP_(\d+)$|^ADDITIONAL_(\d+)$")

RE_TECH_SKILLS    = re.compile(r"^TECH_SKILLS$")
RE_OTHER_SKILLS   = re.compile(r"^OTHER_SKILLS_(\d+)$")
RE_KEYWORDS       = re.compile(r"^KEYWORDS(?:_(\d+))?$")
RE_EXEC_KEYWORDS  = re.compile(r"^EXEC_KEYWORDS$")
RE_TECH_KEYWORDS  = re.compile(r"^TECH_KEYWORDS$")
RE_SKILL_N        = re.compile(r"^SKILLS?_(\d+)$")

RE_JOB_HEADER     = re.compile(r"^JOB_(\d+)_HEADER$")
RE_JOB_TITLE      = re.compile(r"^JOB_(\d+)_TITLE(?:_(\d+))?$")
RE_JOB_SUBTITLE   = re.compile(r"^JOB_(\d+)_SUBTITLE(?:_(\d+))?$")
RE_JOB_INTRO      = re.compile(r"^JOB_(\d+)_INTRO(?:_(\d+))?$")
RE_JOB_BULLET     = re.compile(r"^JOB_(\d+)_BULLET_(\d+)$")
RE_JOB_BULLETS    = re.compile(r"^JOB_(\d+)_BULLETS$")

# Section-format detection: lowercase structural keys
SECTION_KEYS = {
    "header", "experience", "highlights", "skills",
    "education", "certifications", "additional_experience",
    "headline", "summary", "custom", "sections", "role_type",
}


def extract_id(val: dict) -> int | None:
    """Pull id from a slot value dict."""
    return val.get("id")


def extract_table(val: dict, fallback: str = "bullets") -> str:
    """Pull table from a slot value dict."""
    return val.get("table", fallback)


def is_section_format(recipe: dict) -> bool:
    """Return True if recipe already has section-format (lowercase) keys."""
    if not recipe:
        return False
    return bool(set(recipe.keys()) & SECTION_KEYS)


def has_uppercase_slots(recipe: dict) -> bool:
    """Return True if recipe has v1-style uppercase slot keys."""
    if not recipe:
        return False
    return any(k == k.upper() and len(k) > 2 for k in recipe.keys())


# ---------------------------------------------------------------------------
# Main conversion logic
# ---------------------------------------------------------------------------

def convert_recipe(recipe: dict, conn_cur) -> dict:
    """
    Convert a v1 flat-slot recipe to section-based format.

    Returns the new section-based recipe dict.
    """
    cur = conn_cur

    # Accumulators
    header_id = None
    header_table = "resume_header"
    headline_val = None
    summary_val = None

    highlight_ids = []
    highlight_table = "bullets"

    cert_slots = []       # list of (n, id, table)
    education_slots = []  # list of (n, id, table)
    addl_exp_slots = []   # list of (n, id, table)
    skill_refs = []       # list of (sort_key, val_dict)

    # job_n -> {header_id, header_table, bullet_ids, bullet_table}
    job_map = defaultdict(lambda: {
        "header_id": None, "header_table": "career_history",
        "bullet_ids": [], "bullet_table": "bullets",
        "intro_ids": [], "title_ids": [], "subtitle_ids": [],
    })

    custom = {}

    for key, val in sorted(recipe.items()):
        if not isinstance(val, dict):
            custom[key] = val
            continue

        # --- HEADER ---
        if RE_HEADER_NAME.match(key):
            header_id = extract_id(val)
            header_table = extract_table(val, "resume_header")
            continue
        if RE_HEADER_CONTACT.match(key):
            # multiple contact refs — keep first id as header
            if header_id is None:
                header_id = extract_id(val)
                header_table = extract_table(val, "resume_header")
            continue

        # --- HEADLINE ---
        if RE_HEADLINE.match(key):
            headline_val = val
            continue

        # --- SUMMARY (take first only) ---
        if RE_SUMMARY.match(key):
            if summary_val is None:
                summary_val = val
            continue

        # --- HIGHLIGHTS ---
        if RE_HIGHLIGHTS.match(key):
            # val may have ids array
            if "ids" in val:
                highlight_ids.extend(val["ids"])
                highlight_table = extract_table(val, "bullets")
            elif "id" in val:
                highlight_ids.append(val["id"])
                highlight_table = extract_table(val, "bullets")
            continue
        m = RE_HIGHLIGHT.match(key)
        if m:
            bid = extract_id(val)
            if bid is not None:
                highlight_ids.append((int(m.group(1)), bid))
                highlight_table = extract_table(val, "bullets")
            continue

        # --- CERTIFICATIONS ---
        m = RE_CERT.match(key)
        if m:
            bid = extract_id(val)
            if bid is not None:
                cert_slots.append((int(m.group(1)), bid, extract_table(val, "certifications")))
            continue

        # --- EDUCATION ---
        m = RE_EDUCATION.match(key)
        if m:
            bid = extract_id(val)
            if bid is not None:
                education_slots.append((int(m.group(1)), bid, extract_table(val, "education")))
            continue

        # --- ADDITIONAL EXPERIENCE ---
        m = RE_ADDL_EXP.match(key)
        if m:
            n = int(m.group(1) or m.group(2))
            bid = extract_id(val)
            if bid is not None:
                addl_exp_slots.append((n, bid, extract_table(val, "career_history")))
            continue

        # --- SKILLS (various forms) ---
        if RE_TECH_SKILLS.match(key):
            skill_refs.append(("0_TECH", val))
            continue
        m = RE_SKILL_N.match(key)
        if m:
            skill_refs.append((f"0_SKILL_{m.group(1)}", val))
            continue
        m = RE_OTHER_SKILLS.match(key)
        if m:
            skill_refs.append((f"1_OTHER_{m.group(1)}", val))
            continue
        m = RE_KEYWORDS.match(key)
        if m:
            n = m.group(1) or "0"
            skill_refs.append((f"2_KW_{n}", val))
            continue
        if RE_EXEC_KEYWORDS.match(key):
            skill_refs.append(("3_EXEC_KW", val))
            continue
        if RE_TECH_KEYWORDS.match(key):
            skill_refs.append(("4_TECH_KW", val))
            continue

        # --- JOBS ---
        m = RE_JOB_HEADER.match(key)
        if m:
            jn = int(m.group(1))
            job_map[jn]["header_id"] = extract_id(val)
            job_map[jn]["header_table"] = extract_table(val, "career_history")
            continue

        m = RE_JOB_TITLE.match(key)
        if m:
            jn = int(m.group(1))
            bid = extract_id(val)
            if bid is not None:
                sn = int(m.group(2)) if m.group(2) else 1
                job_map[jn]["title_ids"].append((sn, bid))
            continue

        m = RE_JOB_SUBTITLE.match(key)
        if m:
            jn = int(m.group(1))
            bid = extract_id(val)
            if bid is not None:
                sn = int(m.group(2)) if m.group(2) else 1
                job_map[jn]["subtitle_ids"].append((sn, bid))
            continue

        m = RE_JOB_INTRO.match(key)
        if m:
            jn = int(m.group(1))
            bid = extract_id(val)
            if bid is not None:
                sn = int(m.group(2)) if m.group(2) else 1
                job_map[jn]["intro_ids"].append((sn, bid))
            continue

        m = RE_JOB_BULLET.match(key)
        if m:
            jn = int(m.group(1))
            bn = int(m.group(2))
            bid = extract_id(val)
            tbl = extract_table(val, "bullets")
            if bid is not None:
                job_map[jn]["bullet_ids"].append((bn, bid))
                job_map[jn]["bullet_table"] = tbl
            continue

        m = RE_JOB_BULLETS.match(key)
        if m:
            jn = int(m.group(1))
            if "ids" in val:
                for i, bid in enumerate(val["ids"], 1):
                    job_map[jn]["bullet_ids"].append((i, bid))
                job_map[jn]["bullet_table"] = extract_table(val, "bullets")
            elif "id" in val:
                job_map[jn]["bullet_ids"].append((1, val["id"]))
                job_map[jn]["bullet_table"] = extract_table(val, "bullets")
            continue

        # --- Catch-all ---
        custom[key] = val

    # -----------------------------------------------------------------------
    # Build the section-based output
    # -----------------------------------------------------------------------
    out = {}

    # HEADER
    if header_id is not None:
        out["HEADER"] = {"table": header_table, "id": header_id}
    else:
        out["HEADER"] = {"table": "resume_header", "id": 1}

    # HEADLINE
    if headline_val is not None:
        out["HEADLINE"] = headline_val

    # SUMMARY
    if summary_val is not None:
        out["SUMMARY"] = summary_val

    # HIGHLIGHTS
    if highlight_ids:
        # May be list of (n, id) tuples or plain ints
        if highlight_ids and isinstance(highlight_ids[0], tuple):
            sorted_ids = [x[1] for x in sorted(highlight_ids, key=lambda x: x[0])]
        else:
            sorted_ids = highlight_ids
        out["HIGHLIGHTS"] = {"table": highlight_table, "ids": sorted_ids}

    # CERTIFICATIONS
    if cert_slots:
        sorted_certs = sorted(cert_slots, key=lambda x: x[0])
        tbl = sorted_certs[0][2]
        out["CERTIFICATIONS"] = {"table": tbl, "ids": [c[1] for c in sorted_certs]}

    # EDUCATION
    if education_slots:
        sorted_edu = sorted(education_slots, key=lambda x: x[0])
        tbl = sorted_edu[0][2]
        out["EDUCATION"] = {"table": tbl, "ids": [e[1] for e in sorted_edu]}

    # SKILLS — collect all ids from skill refs
    if skill_refs:
        sorted_skills = sorted(skill_refs, key=lambda x: x[0])
        skill_ids = []
        skill_table = "bullets"
        for _, sv in sorted_skills:
            if "ids" in sv:
                skill_ids.extend(sv["ids"])
                skill_table = sv.get("table", skill_table)
            elif "id" in sv:
                skill_ids.append(sv["id"])
                skill_table = sv.get("table", skill_table)
        if skill_ids:
            out["SKILLS"] = {"table": skill_table, "ids": skill_ids}

    # ADDITIONAL EXPERIENCE
    if addl_exp_slots:
        sorted_addl = sorted(addl_exp_slots, key=lambda x: x[0])
        tbl = sorted_addl[0][2]
        out["ADDITIONAL_EXPERIENCE"] = {"table": tbl, "ids": [a[1] for a in sorted_addl]}

    # EXPERIENCE — group jobs by employer using DB lookup
    if job_map:
        out["EXPERIENCE"] = _build_experience(job_map, cur)

    # CUSTOM catch-all
    if custom:
        out["CUSTOM"] = custom

    return out


def _build_experience(job_map: dict, cur) -> list:
    """
    Build the EXPERIENCE section from job_map.

    Groups jobs by employer (via career_history lookup).
    Returns list of company entries, each with nested jobs list.
    """
    # Fetch all referenced career_history rows in one query
    all_job_ids = [jdata["header_id"] for jdata in job_map.values()
                   if jdata["header_id"] is not None]
    if not all_job_ids:
        return []

    cur.execute(
        "SELECT id, employer, is_company_entry FROM career_history WHERE id = ANY(%s)",
        (all_job_ids,)
    )
    ch_rows = {row[0]: {"employer": row[1], "is_company_entry": row[2]}
               for row in cur.fetchall()}

    # Fetch company entries (is_company_entry=true) for each unique employer
    employers = list({row["employer"] for row in ch_rows.values() if row["employer"]})
    company_entry_map = {}  # employer -> id
    if employers:
        cur.execute(
            "SELECT id, employer FROM career_history WHERE is_company_entry = true AND employer = ANY(%s)",
            (employers,)
        )
        for row in cur.fetchall():
            company_entry_map[row[1]] = row[0]

    # Fetch default synopsis bullets for each job id
    cur.execute(
        """SELECT career_history_id, id
           FROM bullets
           WHERE career_history_id = ANY(%s)
             AND type = 'synopsis'
             AND is_default = true
           ORDER BY career_history_id, id""",
        (all_job_ids,)
    )
    synopsis_map = {}  # career_history_id -> bullet id (first default synopsis)
    for row in cur.fetchall():
        if row[0] not in synopsis_map:
            synopsis_map[row[0]] = row[1]

    # Group jobs by employer
    employer_jobs = defaultdict(list)  # employer -> [(job_n, job_id, jdata)]
    for jn in sorted(job_map.keys()):
        jdata = job_map[jn]
        jid = jdata["header_id"]
        if jid is None:
            continue
        ch = ch_rows.get(jid, {})
        employer = ch.get("employer", f"__unknown__{jn}")
        employer_jobs[employer].append((jn, jid, jdata))

    # Build experience array — one entry per unique employer
    # Preserve order by the first job_n in each employer group
    employer_order = []
    seen = set()
    for jn in sorted(job_map.keys()):
        jdata = job_map[jn]
        jid = jdata["header_id"]
        if jid is None:
            continue
        ch = ch_rows.get(jid, {})
        employer = ch.get("employer", f"__unknown__{jn}")
        if employer not in seen:
            seen.add(employer)
            employer_order.append(employer)

    experience = []
    for employer in employer_order:
        jobs_for_employer = employer_jobs[employer]
        company_id = company_entry_map.get(employer)

        company_entry = {
            "table": "career_history",
        }
        if company_id is not None:
            company_entry["id"] = company_id
        else:
            # No company-level entry — use first job id as fallback
            company_entry["id"] = jobs_for_employer[0][1]

        jobs_list = []
        for jn, jid, jdata in jobs_for_employer:
            bullet_table = jdata.get("bullet_table", "bullets")
            bullet_ids = [b[1] for b in sorted(jdata["bullet_ids"], key=lambda x: x[0])]

            job_entry = {
                "table": "career_history",
                "id": jid,
            }

            # Synopsis
            synopsis_id = synopsis_map.get(jid)
            if synopsis_id is not None:
                job_entry["synopsis"] = {"table": "bullets", "id": synopsis_id}

            # Bullets
            if bullet_ids:
                job_entry["bullets"] = {"table": bullet_table, "ids": bullet_ids}

            jobs_list.append(job_entry)

        company_entry["jobs"] = jobs_list
        experience.append(company_entry)

    return experience


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
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
            recipe = recipe_json if isinstance(recipe_json, dict) else (
                json.loads(recipe_json) if recipe_json else {}
            )

            # Already section format
            if version == 2 or is_section_format(recipe):
                print(f"  SKIP id={rid} '{name}' — already section format (v{version})")
                skipped += 1
                continue

            # Empty recipe
            if not recipe:
                print(f"  SKIP id={rid} '{name}' — empty recipe")
                skipped += 1
                continue

            # Must have v1 uppercase slots to convert
            if not has_uppercase_slots(recipe):
                print(f"  SKIP id={rid} '{name}' — no v1 slots detected, keys: {list(recipe.keys())[:5]}")
                skipped += 1
                continue

            try:
                new_recipe = convert_recipe(recipe, cur)

                if DRY_RUN:
                    print(f"  DRY-RUN id={rid} '{name}'")
                    print(f"    sections: {list(new_recipe.keys())}")
                    if "EXPERIENCE" in new_recipe:
                        n_companies = len(new_recipe["EXPERIENCE"])
                        n_jobs = sum(len(e.get("jobs", [])) for e in new_recipe["EXPERIENCE"])
                        print(f"    EXPERIENCE: {n_companies} companies, {n_jobs} jobs")
                    for sec in ("CERTIFICATIONS", "EDUCATION", "HIGHLIGHTS", "SKILLS",
                                "ADDITIONAL_EXPERIENCE"):
                        if sec in new_recipe:
                            ids = new_recipe[sec].get("ids", [])
                            print(f"    {sec}: {len(ids)} items")
                    converted += 1
                else:
                    cur.execute("""
                        UPDATE resume_recipes
                        SET recipe_v1_backup = COALESCE(recipe_v1_backup, recipe),
                            recipe = %s,
                            recipe_version = 2,
                            updated_at = NOW()
                        WHERE id = %s
                    """, (json.dumps(new_recipe), rid))

                    print(f"  OK   id={rid} '{name}' — sections: {list(new_recipe.keys())}")
                    converted += 1

            except Exception as e:
                errors.append((rid, name, str(e)))
                print(f"  ERR  id={rid} '{name}' — {e}")
                import traceback
                traceback.print_exc()

        if DRY_RUN:
            print(f"\nDry run complete. Would convert: {converted}, Would skip: {skipped}")
        elif not errors:
            conn.commit()
            print(f"\nCommitted. Converted: {converted}, Skipped: {skipped}")
        else:
            conn.rollback()
            print(f"\nRolled back due to {len(errors)} error(s): {errors}")

    except Exception as e:
        conn.rollback()
        print(f"Fatal error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    print(f"{'DRY RUN — ' if DRY_RUN else ''}Migrating v1 numbered-slot recipes to section format...\n")
    main()
