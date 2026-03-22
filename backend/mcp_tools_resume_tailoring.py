"""MCP tool functions for Resume Tailoring — variants, ATS scoring, gap analysis.

These are standalone functions using `import db` for database access.
The orchestrator will integrate them into mcp_server.py.
"""

import json
import re
import db

# Common English stopwords for keyword extraction
_STOPWORDS = frozenset(
    "a an the and or but in on at to for of is it by with as from that this "
    "be are was were been have has had do does did will would shall should may "
    "might can could not no nor so if then than too very also about above after "
    "again all am any because before between both but each few further get got "
    "here how into just more most no only other our out over own same she some "
    "such their them there these they through under until up us we what when "
    "where which while who whom why you your able must need per via etc".split()
)


def _extract_keywords(text: str) -> list[dict]:
    """Extract keywords from text, returning [{keyword, count}] sorted by count desc."""
    words = re.findall(r"[a-zA-Z][a-zA-Z+#.\-]{1,}", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        w_clean = w.strip(".-")
        if w_clean and w_clean not in _STOPWORDS and len(w_clean) > 2:
            freq[w_clean] = freq.get(w_clean, 0) + 1
    return sorted(
        [{"keyword": k, "count": v} for k, v in freq.items()],
        key=lambda x: x["count"],
        reverse=True,
    )


def generate_resume_variant(
    role_type: str,
    application_id: int | None = None,
    saved_job_id: int | None = None,
) -> dict:
    """Generate a resume variant tailored to a specific role type.

    Pulls the matching summary variant, filters bullets by role_suitability,
    groups experience by employer, and stores the result in generated_materials.

    Args:
        role_type: CTO, VP Eng, Director, AI Architect, SW Architect, PM, Sr SWE, etc.
        application_id: optional application ID to link the variant to
        saved_job_id: optional saved job ID for context
    """
    if not role_type:
        return {"error": "role_type is required"}

    # Pull matching summary variant
    summary_row = db.query_one(
        "SELECT * FROM summary_variants WHERE role_type ILIKE %s LIMIT 1",
        (role_type,),
    )
    summary_text = summary_row["text"] if summary_row else None

    # Filter bullets where role_suitability contains the role_type
    bullets = db.query(
        """
        SELECT b.id, b.text, b.type, b.tags, b.metrics_json,
               ch.employer, ch.title
        FROM bullets b
        JOIN career_history ch ON b.career_history_id = ch.id
        WHERE b.role_suitability @> ARRAY[%s]::text[]
        ORDER BY b.id DESC
        """,
        (role_type,),
    )

    # Top 5 highlights
    highlights = [
        {"id": b["id"], "text": b["text"], "employer": b["employer"]}
        for b in bullets[:5]
    ]

    # Group bullets by employer
    experience: dict[str, dict] = {}
    for b in bullets:
        key = b["employer"]
        if key not in experience:
            experience[key] = {"employer": key, "title": b["title"], "bullets": []}
        experience[key]["bullets"].append(b["text"])

    # Pull skills
    skills = db.query(
        "SELECT name, category, proficiency FROM skills ORDER BY proficiency DESC"
    )
    keywords = [s["name"] for s in skills[:20]]

    # Pull career history
    career = db.query(
        "SELECT employer, title, start_date, end_date, intro_text FROM career_history ORDER BY start_date DESC"
    )

    variant = {
        "role_type": role_type,
        "summary": summary_text,
        "highlights": highlights,
        "experience": list(experience.values()),
        "keywords": keywords,
        "career_history": career,
        "bullet_count": len(bullets),
    }

    generation_context = {"role_type": role_type, "bullet_count": len(bullets)}
    if application_id:
        generation_context["application_id"] = application_id
    if saved_job_id:
        generation_context["saved_job_id"] = saved_job_id

    row = db.execute_returning(
        """
        INSERT INTO generated_materials
            (type, application_id, saved_job_id, content, content_format,
             voice_check_passed, generation_context, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            "resume_variant",
            application_id,
            saved_job_id,
            json.dumps(variant, default=str),
            "json",
            False,
            json.dumps(generation_context),
            "draft",
        ),
    )

    return {"material": row, "variant": variant}


def run_ats_score(
    jd_text: str,
    resume_text: str | None = None,
    application_id: int | None = None,
) -> dict:
    """Score a resume against a job description for ATS compatibility.

    Extracts keywords from the JD, checks keyword density in the resume,
    and returns an ATS compatibility score with detailed matches.

    Args:
        jd_text: the job description text to score against
        resume_text: optional resume text; if omitted pulls from latest generated_material
        application_id: optional application ID to pull resume from
    """
    if not jd_text:
        return {"error": "jd_text is required"}

    # If no resume_text, try generated_material
    if not resume_text and application_id:
        mat = db.query_one(
            """
            SELECT content FROM generated_materials
            WHERE application_id = %s AND type IN ('resume_variant', 'resume')
            ORDER BY generated_at DESC LIMIT 1
            """,
            (application_id,),
        )
        if mat:
            resume_text = mat["content"]

    if not resume_text:
        # Fall back: assemble from bullets + summary
        header = db.query_one("SELECT full_name, credentials FROM resume_header ORDER BY id LIMIT 1")
        summary = db.query_one("SELECT text FROM summary_variants ORDER BY id LIMIT 1")
        bullets_rows = db.query("SELECT text FROM bullets ORDER BY id DESC LIMIT 20")
        parts = []
        if header:
            parts.append(header.get("full_name", ""))
            parts.append(header.get("credentials", ""))
        if summary:
            parts.append(summary["text"])
        parts.extend(b["text"] for b in bullets_rows)
        resume_text = " ".join(filter(None, parts))

    if not resume_text:
        return {"error": "No resume text available. Provide resume_text or application_id."}

    # Extract JD keywords
    jd_keywords = _extract_keywords(jd_text)
    resume_lower = resume_text.lower()

    # Check each keyword
    keyword_matches = []
    found_count = 0
    for kw in jd_keywords[:50]:
        word = kw["keyword"]
        count_in_resume = len(re.findall(r"\b" + re.escape(word) + r"\b", resume_lower))
        matched = count_in_resume > 0
        if matched:
            found_count += 1
        keyword_matches.append({
            "keyword": word,
            "jd_count": kw["count"],
            "found": matched,
            "resume_count": count_in_resume,
        })

    total_checked = len(keyword_matches)
    match_percentage = round((found_count / total_checked * 100), 1) if total_checked else 0

    # Formatting flags
    formatting_flags = {"ats_safe": True, "issues": []}
    if "<table" in resume_text.lower():
        formatting_flags["ats_safe"] = False
        formatting_flags["issues"].append("Contains HTML tables")
    if "<img" in resume_text.lower():
        formatting_flags["ats_safe"] = False
        formatting_flags["issues"].append("Contains images")

    format_score = 100 if formatting_flags["ats_safe"] else 60
    ats_score_val = round(match_percentage * 0.8 + format_score * 0.2)

    return {
        "keyword_matches": keyword_matches,
        "match_percentage": match_percentage,
        "keywords_found": found_count,
        "keywords_checked": total_checked,
        "formatting_flags": formatting_flags,
        "ats_score": min(ats_score_val, 100),
    }


def run_gap_analysis(
    jd_text: str | None = None,
    saved_job_id: int | None = None,
    application_id: int | None = None,
) -> dict:
    """Run a simplified gap analysis comparing candidate skills/bullets against a JD.

    Classifies JD keywords into strong matches, partial matches, and gaps.
    Stores the result in gap_analyses table.

    Args:
        jd_text: the job description text (required if no saved_job_id with stored JD)
        saved_job_id: optional — pulls jd_text from saved_jobs table
        application_id: optional — links the analysis to an application
    """
    # Pull JD from saved job if needed
    if not jd_text and saved_job_id:
        job = db.query_one(
            "SELECT jd_text, title, company FROM saved_jobs WHERE id = %s",
            (saved_job_id,),
        )
        if job:
            jd_text = job.get("jd_text")

    if not jd_text:
        return {"error": "jd_text is required (or provide saved_job_id with JD stored)"}

    # Extract JD keywords
    jd_keywords = _extract_keywords(jd_text)

    # Pull candidate skills
    skills = db.query("SELECT name, category, proficiency FROM skills")
    skill_names_lower = {s["name"].lower(): s for s in skills}

    # Pull candidate bullets
    bullets = db.query("SELECT text, tags, role_suitability FROM bullets")
    bullet_text_combined = " ".join(b["text"] for b in bullets).lower()

    # Classify
    strong_matches = []
    partial_matches = []
    gaps = []

    for kw in jd_keywords[:40]:
        word = kw["keyword"]
        in_skills = word in skill_names_lower
        in_bullets = word in bullet_text_combined

        if in_skills and in_bullets:
            skill_info = skill_names_lower.get(word)
            strong_matches.append({
                "keyword": word,
                "source": "skills+bullets",
                "proficiency": skill_info["proficiency"] if skill_info else None,
            })
        elif in_skills or in_bullets:
            partial_matches.append({
                "keyword": word,
                "source": "skills" if in_skills else "bullets",
            })
        else:
            gaps.append({"keyword": word, "jd_frequency": kw["count"]})

    total = len(strong_matches) + len(partial_matches) + len(gaps)
    if total > 0:
        overall_score = round(
            (len(strong_matches) * 1.0 + len(partial_matches) * 0.5) / total * 100
        )
    else:
        overall_score = 0

    fit_scores = {
        "strong_match_pct": round(len(strong_matches) / total * 100) if total else 0,
        "partial_match_pct": round(len(partial_matches) / total * 100) if total else 0,
        "gap_pct": round(len(gaps) / total * 100) if total else 0,
    }

    recommendation = "Strong fit" if overall_score >= 70 else (
        "Moderate fit — address gaps in cover letter" if overall_score >= 45 else
        "Weak fit — significant skill gaps"
    )

    row = db.execute_returning(
        """
        INSERT INTO gap_analyses
            (application_id, saved_job_id, jd_text, strong_matches, partial_matches,
             gaps, fit_scores, overall_score, recommendation)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            application_id,
            saved_job_id,
            jd_text[:10000],
            json.dumps(strong_matches),
            json.dumps(partial_matches),
            json.dumps(gaps),
            json.dumps(fit_scores),
            overall_score,
            recommendation,
        ),
    )

    return row
