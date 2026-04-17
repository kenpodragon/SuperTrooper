"""recipe_converter.py — Convert numbered-slot recipes to section-based format.

Used by:
  - onboard.py — to convert freshly-built numbered slot recipe before saving
  - db/migrations/037_migrate_to_sections.py — backfill on existing v1 recipes

Numbered keys (CERT_1, JOB_N_BULLET_M, etc.) are positional anchors that
belong in template_map only. The recipe should reference DB rows by section
(CERTIFICATIONS, EXPERIENCE, etc.) so the same content can render into
multiple template layouts.

Section output shape (consumed by section_resolver.py):
  HEADER:        {table, id}
  HEADLINE:      {literal} or {table, id}
  SUMMARY:       {table, id}
  HIGHLIGHTS:    {table, ids[]}
  CERTIFICATIONS:{table, ids[]}
  EDUCATION:     {table, ids[]}
  SKILLS:        {table, ids[]}
  ADDITIONAL_EXPERIENCE: {table, ids[]}
  EXPERIENCE:    [{table, id, jobs:[{table, id, synopsis, bullets}]}]
  CUSTOM:        {<unmapped slot keys>}
"""

import re
from collections import defaultdict


# ---------------------------------------------------------------------------
# Slot-key regexes
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

# Section-format detection
SECTION_KEYS_LOWER = {
    "header", "experience", "highlights", "skills",
    "education", "certifications", "additional_experience",
    "headline", "summary", "custom", "sections", "role_type",
}
SECTION_KEYS_UPPER = {k.upper() for k in SECTION_KEYS_LOWER}


def _extract_id(val: dict):
    return val.get("id") if isinstance(val, dict) else None


def _extract_table(val: dict, fallback: str):
    return val.get("table", fallback) if isinstance(val, dict) else fallback


def is_section_format(recipe: dict) -> bool:
    """True if recipe already has section-format keys."""
    if not recipe:
        return False
    keys = set(recipe.keys())
    # Either lowercase keys (frontend shape) or uppercase section keys without numbered slots
    if keys & SECTION_KEYS_LOWER:
        return True
    if keys & SECTION_KEYS_UPPER and not _has_numbered_slots(recipe):
        return True
    return False


def _has_numbered_slots(recipe: dict) -> bool:
    """True if recipe has v1-style numbered slot keys."""
    if not recipe:
        return False
    return any(
        RE_CERT.match(k) or RE_EDUCATION.match(k) or RE_HIGHLIGHT.match(k)
        or RE_JOB_HEADER.match(k) or RE_JOB_BULLET.match(k)
        or RE_HEADER_NAME.match(k) or RE_HEADER_CONTACT.match(k)
        for k in recipe
    )


# ---------------------------------------------------------------------------
# Main conversion
# ---------------------------------------------------------------------------

def convert_to_sections(recipe: dict, ch_lookup_fn=None) -> dict:
    """
    Convert a numbered-slot recipe to section-based format.

    Args:
      recipe: dict with v1 numbered keys (CERT_1, JOB_N_BULLET_M, etc.)
      ch_lookup_fn: optional callable(career_history_ids: list[int]) -> dict
        Returns {ch_id: {employer, is_company_entry}} so EXPERIENCE can be
        grouped by employer. If None, EXPERIENCE jobs are not grouped (each
        job becomes its own company entry).

    Returns: dict in section format (see module docstring).

    Behavior:
      - Already-section recipes pass through unchanged.
      - Literal values (no 'id' key) become CUSTOM entries (preserved, not lost).
      - Empty recipes return {}.
    """
    if not recipe:
        return {}
    if is_section_format(recipe):
        return recipe

    # Accumulators
    header_ref = None
    header_name_literal = None
    header_contact_literals = []  # ordered (n, text)
    headline_val = None
    summary_val = None

    highlight_ids = []
    highlight_table = "bullets"

    cert_slots = []        # (n, id, table)
    education_slots = []
    addl_exp_slots = []
    skill_refs = []        # (sort_key, val_dict)

    # job_n -> {header_id, header_table, bullet_ids, intro_ids, ...}
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
        # If any header slot is a DB ref, prefer it. Otherwise accumulate
        # the literal name + contact lines so neither is lost.
        if RE_HEADER_NAME.match(key):
            if isinstance(val, dict) and "id" in val:
                if header_ref is None:
                    header_ref = {"table": _extract_table(val, "resume_header"), "id": val["id"]}
            elif isinstance(val, dict) and "literal" in val:
                header_name_literal = val["literal"]
            continue
        if RE_HEADER_CONTACT.match(key):
            if isinstance(val, dict) and "id" in val:
                if header_ref is None:
                    header_ref = {"table": _extract_table(val, "resume_header"), "id": val["id"]}
            elif isinstance(val, dict) and "literal" in val:
                # Preserve order: HEADER_CONTACT, HEADER_CONTACT_1, HEADER_CONTACT_2, ...
                m_n = re.match(r"^HEADER_CONTACT(?:_(\d+))?$", key)
                idx = int(m_n.group(1)) if m_n and m_n.group(1) else 0
                header_contact_literals.append((idx, val["literal"]))
            continue

        # --- HEADLINE ---
        if RE_HEADLINE.match(key):
            headline_val = val
            continue

        # --- SUMMARY ---
        if RE_SUMMARY.match(key):
            if summary_val is None:
                summary_val = val
            continue

        # --- HIGHLIGHTS ---
        if RE_HIGHLIGHTS.match(key):
            if "ids" in val:
                highlight_ids.extend(val["ids"])
                highlight_table = _extract_table(val, "bullets")
            elif "id" in val:
                highlight_ids.append(val["id"])
                highlight_table = _extract_table(val, "bullets")
            continue
        m = RE_HIGHLIGHT.match(key)
        if m:
            bid = _extract_id(val)
            if bid is not None:
                highlight_ids.append((int(m.group(1)), bid))
                highlight_table = _extract_table(val, "bullets")
            continue

        # --- CERTIFICATIONS ---
        m = RE_CERT.match(key)
        if m:
            bid = _extract_id(val)
            if bid is not None:
                cert_slots.append((int(m.group(1)), bid, _extract_table(val, "certifications")))
            continue

        # --- EDUCATION ---
        m = RE_EDUCATION.match(key)
        if m:
            bid = _extract_id(val)
            if bid is not None:
                education_slots.append((int(m.group(1)), bid, _extract_table(val, "education")))
            continue

        # --- ADDITIONAL EXPERIENCE ---
        m = RE_ADDL_EXP.match(key)
        if m:
            n = int(m.group(1) or m.group(2))
            bid = _extract_id(val)
            if bid is not None:
                addl_exp_slots.append((n, bid, _extract_table(val, "career_history")))
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
            job_map[jn]["header_id"] = _extract_id(val)
            job_map[jn]["header_table"] = _extract_table(val, "career_history")
            continue

        m = RE_JOB_TITLE.match(key)
        if m:
            jn = int(m.group(1))
            bid = _extract_id(val)
            if bid is not None:
                sn = int(m.group(2)) if m.group(2) else 1
                job_map[jn]["title_ids"].append((sn, bid))
            continue

        m = RE_JOB_SUBTITLE.match(key)
        if m:
            jn = int(m.group(1))
            bid = _extract_id(val)
            if bid is not None:
                sn = int(m.group(2)) if m.group(2) else 1
                job_map[jn]["subtitle_ids"].append((sn, bid))
            continue

        m = RE_JOB_INTRO.match(key)
        if m:
            jn = int(m.group(1))
            bid = _extract_id(val)
            if bid is not None:
                sn = int(m.group(2)) if m.group(2) else 1
                job_map[jn]["intro_ids"].append((sn, bid))
            continue

        m = RE_JOB_BULLET.match(key)
        if m:
            jn = int(m.group(1))
            bn = int(m.group(2))
            bid = _extract_id(val)
            tbl = _extract_table(val, "bullets")
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
                job_map[jn]["bullet_table"] = _extract_table(val, "bullets")
            elif "id" in val:
                job_map[jn]["bullet_ids"].append((1, val["id"]))
                job_map[jn]["bullet_table"] = _extract_table(val, "bullets")
            continue

        # --- Catch-all: literal slot or unrecognized ---
        custom[key] = val

    # -----------------------------------------------------------------------
    # Build the section-based output
    # -----------------------------------------------------------------------
    out = {}

    if header_ref is not None:
        out["HEADER"] = header_ref
    elif header_name_literal or header_contact_literals:
        contact_text = " • ".join(
            t for _, t in sorted(header_contact_literals, key=lambda x: x[0]) if t
        )
        # Preserve both pieces for the resolver to consume.
        lit = {}
        if header_name_literal:
            lit["full_name"] = header_name_literal
        if contact_text:
            lit["literal"] = contact_text
        out["HEADER"] = lit

    if headline_val is not None:
        out["HEADLINE"] = headline_val

    if summary_val is not None:
        out["SUMMARY"] = summary_val

    if highlight_ids:
        if highlight_ids and isinstance(highlight_ids[0], tuple):
            sorted_ids = [x[1] for x in sorted(highlight_ids, key=lambda x: x[0])]
        else:
            sorted_ids = highlight_ids
        out["HIGHLIGHTS"] = {"table": highlight_table, "ids": sorted_ids}

    if cert_slots:
        sorted_certs = sorted(cert_slots, key=lambda x: x[0])
        tbl = sorted_certs[0][2]
        out["CERTIFICATIONS"] = {"table": tbl, "ids": [c[1] for c in sorted_certs]}

    if education_slots:
        sorted_edu = sorted(education_slots, key=lambda x: x[0])
        tbl = sorted_edu[0][2]
        out["EDUCATION"] = {"table": tbl, "ids": [e[1] for e in sorted_edu]}

    if skill_refs:
        sorted_skills = sorted(skill_refs, key=lambda x: x[0])
        skill_ids = []
        skill_table = "skills"
        for _, sv in sorted_skills:
            if isinstance(sv, dict):
                if "ids" in sv:
                    skill_ids.extend(sv["ids"])
                    skill_table = sv.get("table", skill_table)
                elif "id" in sv:
                    skill_ids.append(sv["id"])
                    skill_table = sv.get("table", skill_table)
        if skill_ids:
            out["SKILLS"] = {"table": skill_table, "ids": skill_ids}

    if addl_exp_slots:
        sorted_addl = sorted(addl_exp_slots, key=lambda x: x[0])
        tbl = sorted_addl[0][2]
        out["ADDITIONAL_EXPERIENCE"] = {"table": tbl, "ids": [a[1] for a in sorted_addl]}

    if job_map:
        out["EXPERIENCE"] = _build_experience(job_map, ch_lookup_fn)

    if custom:
        out["CUSTOM"] = custom

    return out


def _build_experience(job_map: dict, ch_lookup_fn=None) -> list:
    """
    Build EXPERIENCE section from job_map. If ch_lookup_fn is provided,
    groups jobs by employer using DB lookup; otherwise each job becomes
    its own company entry.
    """
    all_job_ids = [jdata["header_id"] for jdata in job_map.values()
                   if jdata["header_id"] is not None]
    if not all_job_ids:
        return []

    if ch_lookup_fn is None:
        # No grouping — each job is its own entry
        experience = []
        for jn in sorted(job_map.keys()):
            jdata = job_map[jn]
            jid = jdata["header_id"]
            if jid is None:
                continue
            bullet_ids = [b[1] for b in sorted(jdata["bullet_ids"], key=lambda x: x[0])]
            entry = {"table": "career_history", "id": jid}
            if bullet_ids:
                entry["jobs"] = [{
                    "table": "career_history",
                    "id": jid,
                    "bullets": {"table": jdata.get("bullet_table", "bullets"), "ids": bullet_ids},
                }]
            experience.append(entry)
        return experience

    # Group by employer using lookup
    ch_rows = ch_lookup_fn(all_job_ids)
    # Map employer -> ids of company entries
    employers = list({row["employer"] for row in ch_rows.values() if row.get("employer")})
    company_entry_map = {}
    if employers:
        # Caller should populate this map but ch_lookup_fn returns it merged
        # Subset: rows where is_company_entry=True
        for cid, row in ch_rows.items():
            if row.get("is_company_entry") and row.get("employer"):
                company_entry_map.setdefault(row["employer"], cid)

    # Group jobs by employer
    employer_jobs = defaultdict(list)
    employer_order = []
    seen = set()
    for jn in sorted(job_map.keys()):
        jdata = job_map[jn]
        jid = jdata["header_id"]
        if jid is None:
            continue
        ch = ch_rows.get(jid, {})
        employer = ch.get("employer", f"__unknown__{jn}")
        employer_jobs[employer].append((jn, jid, jdata))
        if employer not in seen:
            seen.add(employer)
            employer_order.append(employer)

    experience = []
    for employer in employer_order:
        jobs_for_employer = employer_jobs[employer]
        company_id = company_entry_map.get(employer)

        company_entry = {"table": "career_history"}
        if company_id is not None:
            company_entry["id"] = company_id
        else:
            company_entry["id"] = jobs_for_employer[0][1]

        # Merge multiple slots referencing the same career_history.id into one
        # job entry. Template_map produces both a company-line slot and a title
        # slot for each job, both resolving to the same row.
        jobs_by_id = {}  # jid -> merged job entry
        order = []
        for jn, jid, jdata in jobs_for_employer:
            if jid not in jobs_by_id:
                jobs_by_id[jid] = {
                    "table": "career_history", "id": jid,
                    "_bullet_ids": [], "_intro_ids": [],
                    "_bullet_table": "bullets",
                }
                order.append(jid)
            jobs_by_id[jid]["_bullet_ids"].extend(jdata.get("bullet_ids", []))
            jobs_by_id[jid]["_intro_ids"].extend(jdata.get("intro_ids", []))
            if jdata.get("bullet_table"):
                jobs_by_id[jid]["_bullet_table"] = jdata["bullet_table"]

        jobs_list = []
        for jid in order:
            entry = jobs_by_id[jid]
            bullet_ids = [b[1] for b in sorted(entry.pop("_bullet_ids"), key=lambda x: x[0])]
            intro_ids = entry.pop("_intro_ids")
            bullet_table = entry.pop("_bullet_table")
            if intro_ids:
                first_intro_id = sorted(intro_ids, key=lambda x: x[0])[0][1]
                entry["synopsis"] = {"table": "bullets", "id": first_intro_id}
            if bullet_ids:
                entry["bullets"] = {"table": bullet_table, "ids": bullet_ids}
            jobs_list.append(entry)

        company_entry["jobs"] = jobs_list
        experience.append(company_entry)

    return experience
