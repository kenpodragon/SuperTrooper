"""MCP tools for skills development & certification planning.

# Imports needed: from db import db / mcp already defined
"""

import json
from collections import Counter


@mcp.tool()
def get_skill_gaps() -> dict:
    """Analyse skill gaps across all stored gap analyses.

    Compares skills mentioned in gap_analyses.gaps against the user's
    skills table.  Categorises each gap as not_showcased, adjacent, or
    deep_gap.

    Returns:
        dict with gaps list and coverage_pct
    """
    gap_rows = db.query(
        "SELECT id, gaps FROM gap_analyses WHERE gaps IS NOT NULL"
    )
    user_rows = db.query("SELECT LOWER(name) AS name FROM skills")
    user_skills = {r["name"] for r in user_rows}

    gap_counter = Counter()
    for row in gap_rows:
        data = row["gaps"]
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                continue
        if isinstance(data, list):
            for item in data:
                name = item.get("skill") or item.get("name") or (item if isinstance(item, str) else "")
                if name:
                    gap_counter[name.strip()] += 1
        elif isinstance(data, dict):
            for name in data.keys():
                gap_counter[name.strip()] += 1

    def _cat(skill):
        sl = skill.lower()
        if sl in user_skills:
            return "not_showcased"
        for us in user_skills:
            if len(us) > 3 and (us in sl or sl in us):
                return "adjacent"
        return "deep_gap"

    rec_map = {
        "not_showcased": "Add to resume — you already have this skill",
        "adjacent": "Upskill — you have a related skill",
        "deep_gap": "Learning required — new skill area",
    }

    results = []
    for skill, count in gap_counter.most_common():
        cat = _cat(skill)
        results.append({
            "skill": skill, "category": cat,
            "jd_count": count, "recommendation": rec_map[cat],
        })

    total = len(gap_counter)
    covered = sum(1 for r in results if r["category"] == "not_showcased")
    pct = round(covered / total * 100, 1) if total else 0

    return {"gaps": results, "coverage_pct": pct}


@mcp.tool()
def get_skill_trends() -> dict:
    """Analyse skill demand trends across saved JDs and gap analyses.

    Returns:
        dict with trending skills, rising (unowned) skills, and user_coverage_pct
    """
    user_rows = db.query("SELECT LOWER(name) AS name FROM skills")
    user_skills = {r["name"] for r in user_rows}
    counter = Counter()

    # From gap analyses
    ga_rows = db.query("SELECT jd_parsed, gaps FROM gap_analyses")
    for row in ga_rows:
        for field in ("jd_parsed", "gaps"):
            data = row.get(field)
            if not data:
                continue
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(data, list):
                for item in data:
                    name = item.get("skill") or item.get("name") or (item if isinstance(item, str) else "")
                    if name:
                        counter[name.strip().lower()] += 1
            elif isinstance(data, dict):
                for k in data.keys():
                    counter[k.strip().lower()] += 1

    trending = []
    for skill, freq in counter.most_common(50):
        trending.append({
            "skill": skill, "frequency": freq,
            "have": skill in user_skills,
        })

    rising = [t for t in trending if not t["have"]][:15]
    total = len(trending)
    have_count = sum(1 for t in trending if t["have"])
    coverage = round(have_count / total * 100, 1) if total else 0

    return {"trending": trending, "rising": rising, "user_coverage_pct": coverage}


@mcp.tool()
def certification_roi(role_type: str | None = None) -> dict:
    """Analyse certification ROI based on JD frequency.

    Args:
        role_type: Optional role type filter (e.g. 'engineering manager')

    Returns:
        dict with recommendations list ranked by priority
    """
    cert_patterns = [
        "PMP", "AWS", "Azure", "GCP", "Kubernetes", "CKAD", "CKA",
        "Scrum", "CSM", "CSPO", "SAFe", "ITIL", "Six Sigma",
        "CISSP", "CISM", "CompTIA", "Security+", "TOGAF",
        "Google Cloud", "Terraform", "Docker", "CCNA", "CCNP",
        "PMI-ACP", "Prince2", "Lean", "Agile", "MBA", "PhD",
        "Certified", "Certification",
    ]

    if role_type:
        jd_rows = db.query(
            "SELECT jd_text, fit_score FROM saved_jobs WHERE jd_text IS NOT NULL AND LOWER(title) LIKE %s",
            (f"%{role_type.lower()}%",),
        )
    else:
        jd_rows = db.query(
            "SELECT jd_text, fit_score FROM saved_jobs WHERE jd_text IS NOT NULL"
        )

    cert_counter = Counter()
    for row in jd_rows:
        jd_lower = row["jd_text"].lower()
        for pat in cert_patterns:
            if pat.lower() in jd_lower:
                cert_counter[pat] += 1

    existing = db.query("SELECT LOWER(name) AS name FROM certifications WHERE is_active = TRUE")
    existing_names = {r["name"] for r in existing}

    recs = []
    for cert, freq in cert_counter.most_common():
        have = any(cert.lower() in en for en in existing_names)
        recs.append({
            "cert_name": cert, "jd_frequency": freq, "have": have,
            "estimated_unlock": freq if not have else 0,
            "priority": 1 if freq >= 5 and not have else (2 if freq >= 2 and not have else 3),
        })

    return {"recommendations": recs}


@mcp.tool()
def get_differentiator_analysis() -> dict:
    """Analyse user's unique skill combinations as competitive differentiators.

    Identifies cross-category expertise combinations and expert-level skills,
    plus the top skill gaps that would unlock the most JDs.

    Returns:
        dict with differentiators list and gaps_to_unlock list
    """
    user_skills_rows = db.query("SELECT name, category, proficiency FROM skills")
    user_skills = {r["name"].lower() for r in user_skills_rows}

    by_category = {}
    for r in user_skills_rows:
        by_category.setdefault(r.get("category", "other"), []).append(r["name"])

    differentiators = []
    categories = list(by_category.keys())
    for i, cat1 in enumerate(categories):
        for cat2 in categories[i + 1:]:
            combo_label = f"{cat1.title()} + {cat2.title()}"
            examples = by_category[cat1][:2] + by_category[cat2][:2]
            differentiators.append({
                "combo": combo_label, "skills": examples,
                "rarity_note": f"Cross-domain expertise in {cat1} and {cat2}",
            })

    experts = [r for r in user_skills_rows if r.get("proficiency") == "expert"]
    for e in experts:
        differentiators.append({
            "combo": f"Expert: {e['name']}", "skills": [e["name"]],
            "rarity_note": f"Expert-level {e.get('category', '')} skill",
        })

    gap_rows = db.query("SELECT gaps FROM gap_analyses WHERE gaps IS NOT NULL")
    gap_counter = Counter()
    for row in gap_rows:
        data = row["gaps"]
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                continue
        if isinstance(data, list):
            for item in data:
                name = item.get("skill") or item.get("name") or (item if isinstance(item, str) else "")
                if name and name.lower() not in user_skills:
                    gap_counter[name.strip()] += 1
        elif isinstance(data, dict):
            for name in data.keys():
                if name.lower() not in user_skills:
                    gap_counter[name.strip()] += 1

    gaps_to_unlock = [
        {"skill": s, "unlock_count": c}
        for s, c in gap_counter.most_common(10)
    ]

    return {"differentiators": differentiators[:15], "gaps_to_unlock": gaps_to_unlock}
