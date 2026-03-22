"""Routes for Resume Tailoring — variants, ATS scoring, gap analysis."""

import json
import re
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("resume_tailoring", __name__)

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


# ---------------------------------------------------------------------------
# GET /api/resume/variants — list available role types
# ---------------------------------------------------------------------------

@bp.route("/api/resume/variants", methods=["GET"])
def list_variants():
    """List available role types with summary previews from summary_variants."""
    rows = db.query("SELECT id, role_type, text FROM summary_variants ORDER BY id")
    result = [
        {
            "id": r["id"],
            "role_type": r["role_type"],
            "summary_preview": (r["text"] or "")[:100],
        }
        for r in rows
    ]
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# POST /api/resume/variant — generate a role-type variant
# ---------------------------------------------------------------------------

@bp.route("/api/resume/variant", methods=["POST"])
def generate_variant():
    """Generate a resume variant for a specific role type.

    Body (JSON):
        role_type (required): CTO, VP Eng, Director, AI Architect, etc.
        application_id: optional application ID
        saved_job_id: optional saved job ID
    """
    data = request.get_json(force=True)
    role_type = data.get("role_type")
    if not role_type:
        return jsonify({"error": "role_type is required"}), 400

    application_id = data.get("application_id")
    saved_job_id = data.get("saved_job_id")

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

    # Group bullets by employer for experience section
    experience: dict[str, dict] = {}
    for b in bullets:
        key = b["employer"]
        if key not in experience:
            experience[key] = {"employer": key, "title": b["title"], "bullets": []}
        experience[key]["bullets"].append(b["text"])

    # Pull skills matching role type
    skills = db.query(
        "SELECT name, category, proficiency FROM skills ORDER BY proficiency DESC"
    )
    keywords = [s["name"] for s in skills[:20]]

    # Pull career history entries
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

    return jsonify({"material": row, "variant": variant}), 201


# ---------------------------------------------------------------------------
# POST /api/resume/ats-score — ATS compatibility scoring
# ---------------------------------------------------------------------------

@bp.route("/api/resume/ats-score", methods=["POST"])
def ats_score():
    """Score a resume against a JD for ATS compatibility.

    Body (JSON):
        jd_text (required unless application_id): the job description text
        resume_text: optional resume text to score
        application_id: optional — pulls latest generated_material for resume
    """
    data = request.get_json(force=True)
    jd_text = data.get("jd_text")
    resume_text = data.get("resume_text")
    application_id = data.get("application_id")

    if not jd_text:
        return jsonify({"error": "jd_text is required"}), 400

    # If no resume_text, try to pull from latest generated_material
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
        return jsonify({"error": "No resume text available. Provide resume_text or application_id."}), 400

    # Extract keywords from JD
    jd_keywords = _extract_keywords(jd_text)
    resume_lower = resume_text.lower()

    # Check each JD keyword against resume
    keyword_matches = []
    found_count = 0
    for kw in jd_keywords[:50]:  # top 50 JD keywords
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

    # Formatting flags (text-based checks)
    formatting_flags = {
        "ats_safe": True,
        "issues": [],
    }
    if "<table" in resume_text.lower():
        formatting_flags["ats_safe"] = False
        formatting_flags["issues"].append("Contains HTML tables — may confuse ATS parsers")
    if "<img" in resume_text.lower():
        formatting_flags["ats_safe"] = False
        formatting_flags["issues"].append("Contains images — ATS cannot parse images")

    # Calculate ATS score (weighted: 80% keyword match, 20% formatting)
    format_score = 100 if formatting_flags["ats_safe"] else 60
    ats_score_val = round(match_percentage * 0.8 + format_score * 0.2)

    result = {
        "keyword_matches": keyword_matches,
        "match_percentage": match_percentage,
        "keywords_found": found_count,
        "keywords_checked": total_checked,
        "formatting_flags": formatting_flags,
        "ats_score": min(ats_score_val, 100),
    }

    return jsonify(result), 200


# ---------------------------------------------------------------------------
# POST /api/gap-analysis/run — run a simplified gap analysis
# ---------------------------------------------------------------------------

@bp.route("/api/gap-analysis/run", methods=["POST"])
def run_gap_analysis():
    """Run a simplified gap analysis from JD text or saved job.

    Body (JSON):
        jd_text: the job description text (required if no saved_job_id)
        saved_job_id: optional — pulls jd_text from saved_jobs
        application_id: optional — links analysis to application
    """
    data = request.get_json(force=True)
    jd_text = data.get("jd_text")
    saved_job_id = data.get("saved_job_id")
    application_id = data.get("application_id")

    # Pull JD from saved job if needed
    if not jd_text and saved_job_id:
        job = db.query_one(
            "SELECT jd_text, title, company FROM saved_jobs WHERE id = %s",
            (saved_job_id,),
        )
        if job:
            jd_text = job.get("jd_text")

    if not jd_text:
        return jsonify({"error": "jd_text is required (or provide saved_job_id with JD stored)"}), 400

    # Extract JD keywords
    jd_keywords = _extract_keywords(jd_text)
    jd_keyword_set = {kw["keyword"] for kw in jd_keywords[:40]}

    # Pull candidate skills
    skills = db.query("SELECT name, category, proficiency FROM skills")
    skill_names_lower = {s["name"].lower(): s for s in skills}

    # Pull candidate bullets
    bullets = db.query("SELECT text, tags, role_suitability FROM bullets")
    bullet_text_combined = " ".join(b["text"] for b in bullets).lower()

    # Classify matches
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
        strong_pct = round(len(strong_matches) / total * 100)
        partial_pct = round(len(partial_matches) / total * 100)
        gap_pct = round(len(gaps) / total * 100)
        overall_score = round(
            (len(strong_matches) * 1.0 + len(partial_matches) * 0.5) / total * 100
        )
    else:
        strong_pct = partial_pct = gap_pct = overall_score = 0

    fit_scores = {
        "strong_match_pct": strong_pct,
        "partial_match_pct": partial_pct,
        "gap_pct": gap_pct,
    }

    recommendation = "Strong fit" if overall_score >= 70 else (
        "Moderate fit — address gaps in cover letter" if overall_score >= 45 else
        "Weak fit — significant skill gaps"
    )

    # Store in gap_analyses
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
            jd_text[:10000],  # cap stored JD text
            json.dumps(strong_matches),
            json.dumps(partial_matches),
            json.dumps(gaps),
            json.dumps(fit_scores),
            overall_score,
            recommendation,
        ),
    )

    return jsonify(row), 201


# ---------------------------------------------------------------------------
# POST /api/applications/<id>/link-materials — link materials to application
# ---------------------------------------------------------------------------

@bp.route("/api/applications/<int:app_id>/link-materials", methods=["POST"])
def link_materials(app_id):
    """Link generated materials to an application.

    Body (JSON):
        material_ids (required): array of generated_materials IDs to link
    """
    data = request.get_json(force=True)
    material_ids = data.get("material_ids")
    if not material_ids or not isinstance(material_ids, list):
        return jsonify({"error": "material_ids array is required"}), 400

    # Verify application exists
    app = db.query_one("SELECT id FROM applications WHERE id = %s", (app_id,))
    if not app:
        return jsonify({"error": "Application not found"}), 404

    updated = []
    for mid in material_ids:
        row = db.execute_returning(
            """
            UPDATE generated_materials
            SET application_id = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (app_id, mid),
        )
        if row:
            updated.append(row)

    return jsonify({"count": len(updated), "materials": updated}), 200


# ---------------------------------------------------------------------------
# POST /api/resume/validate — content validation (sections, placeholders, metrics, voice)
# ---------------------------------------------------------------------------

@bp.route("/api/resume/validate", methods=["POST"])
def validate_resume():
    """Validate resume content for completeness, quality, and voice compliance.

    Body (JSON):
        resume_text (required): full resume text to validate
        application_id: optional — pulls latest generated_material if resume_text omitted

    Returns:
        {
          "valid": bool,
          "issues": [{"section": str, "issue": str, "severity": "error"|"warning"}],
          "summary": {"errors": int, "warnings": int}
        }
    """
    data = request.get_json(force=True)
    resume_text = data.get("resume_text", "").strip()
    application_id = data.get("application_id")

    # Pull from generated_materials if no text supplied
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
            resume_text = (mat.get("content") or "").strip()

    if not resume_text:
        return jsonify({"error": "resume_text is required (or provide application_id with a saved material)"}), 400

    issues = []
    text_lower = resume_text.lower()

    # ------------------------------------------------------------------
    # 1. Required sections present
    # ------------------------------------------------------------------
    section_checks = [
        ("summary",    ["summary", "professional summary", "profile", "objective"]),
        ("experience", ["experience", "work history", "employment", "career history"]),
        ("education",  ["education", "academic"]),
        ("skills",     ["skills", "competencies", "technical skills", "core competencies"]),
    ]
    for section_name, keywords in section_checks:
        if not any(kw in text_lower for kw in keywords):
            issues.append({
                "section": section_name,
                "issue": f"Required section '{section_name}' not detected",
                "severity": "error",
            })

    # ------------------------------------------------------------------
    # 2. Placeholder / draft text
    # ------------------------------------------------------------------
    placeholder_patterns = [
        (r"\[.*?\]",            "Contains bracket placeholder text"),
        (r"\bTODO\b",           "Contains TODO marker"),
        (r"\bINSERT\b",         "Contains INSERT placeholder"),
        (r"\bTBD\b",            "Contains TBD placeholder"),
        (r"\bXXX\b",            "Contains XXX placeholder"),
        (r"\bLOREM\b",          "Contains lorem ipsum text"),
        (r"\bYOUR NAME\b",      "Contains 'YOUR NAME' placeholder"),
        (r"\bCOMPANY NAME\b",   "Contains 'COMPANY NAME' placeholder"),
    ]
    for pattern, msg in placeholder_patterns:
        if re.search(pattern, resume_text, re.IGNORECASE):
            issues.append({
                "section": "content",
                "issue": msg,
                "severity": "error",
            })

    # ------------------------------------------------------------------
    # 3. Bullets have metrics / numbers
    # ------------------------------------------------------------------
    # Split into lines that look like bullets (start with -, *, •, or are indented)
    bullet_lines = [
        ln.strip() for ln in resume_text.splitlines()
        if re.match(r"^[\-\*\•\u2022]\s+", ln.strip()) or re.match(r"^\s{2,}[^\s]", ln)
    ]
    if bullet_lines:
        metric_pattern = re.compile(r"\d+[%\+xX]?|\$[\d,]+|\d+[\.,]\d+")
        bullets_without_metrics = [ln for ln in bullet_lines if not metric_pattern.search(ln)]
        ratio = len(bullets_without_metrics) / len(bullet_lines)
        if ratio > 0.5:
            issues.append({
                "section": "experience",
                "issue": (
                    f"{len(bullets_without_metrics)} of {len(bullet_lines)} bullets lack "
                    "quantified metrics or numbers (>50% threshold exceeded)"
                ),
                "severity": "warning",
            })
        elif bullets_without_metrics:
            issues.append({
                "section": "experience",
                "issue": (
                    f"{len(bullets_without_metrics)} bullet(s) may benefit from "
                    "quantified metrics or measurable outcomes"
                ),
                "severity": "warning",
            })
    else:
        issues.append({
            "section": "experience",
            "issue": "No bullet-point lines detected — unable to verify metric coverage",
            "severity": "warning",
        })

    # ------------------------------------------------------------------
    # 4. Voice rules — banned words / patterns
    # ------------------------------------------------------------------
    banned_words = []
    try:
        voice_rows = db.query(
            "SELECT rule_text FROM voice_rules WHERE category = 'banned_word' AND active = TRUE"
        )
        banned_words = [r["rule_text"].lower().strip() for r in voice_rows if r.get("rule_text")]
    except Exception:
        pass  # voice table may not exist in all envs

    banned_found = []
    for word in banned_words:
        if re.search(r"\b" + re.escape(word) + r"\b", text_lower):
            banned_found.append(word)

    if banned_found:
        issues.append({
            "section": "voice",
            "issue": f"Banned words/phrases detected: {', '.join(banned_found[:10])}",
            "severity": "error",
        })

    # Also flag common corporate buzzword soup patterns even if no DB rules loaded
    generic_buzzwords = [
        "synergy", "leverage", "utilize", "utilize", "paradigm", "ecosystem",
        "holistic", "thought leader", "robust solution", "best-in-class",
        "results-driven", "detail-oriented", "go-getter", "team player",
    ]
    found_generic = [w for w in generic_buzzwords if re.search(r"\b" + re.escape(w) + r"\b", text_lower)]
    if found_generic:
        issues.append({
            "section": "voice",
            "issue": f"Generic/buzzword language detected: {', '.join(found_generic[:8])}",
            "severity": "warning",
        })

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------
    errors = sum(1 for i in issues if i["severity"] == "error")
    warnings = sum(1 for i in issues if i["severity"] == "warning")
    valid = errors == 0

    return jsonify({
        "valid": valid,
        "issues": issues,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "total_issues": len(issues),
        },
    }), 200


# ---------------------------------------------------------------------------
# POST /api/resume/reorder-bullets — AI-driven bullet reordering by JD relevance
# ---------------------------------------------------------------------------

def _python_reorder_bullets(context: dict) -> dict:
    """Rule-based bullet reordering using keyword overlap scoring."""
    bullets = context["bullets"]
    jd_text = context["jd_text"]
    jd_keywords = {kw["keyword"] for kw in _extract_keywords(jd_text)[:40]}

    scored = []
    for b in bullets:
        text_lower = b["text"].lower()
        overlap = sum(1 for kw in jd_keywords if kw in text_lower)
        scored.append({**b, "_score": overlap})

    scored.sort(key=lambda x: x["_score"], reverse=True)
    for item in scored:
        item.pop("_score", None)
    return {"reordered_bullets": scored}


def _ai_reorder_bullets(context: dict) -> dict:
    """AI-enhanced bullet reordering via provider."""
    from ai_providers import get_provider
    provider = get_provider()
    bullets_text = "\n".join(f"- {b['text']}" for b in context["bullets"])
    prompt = (
        f"Given this job description:\n{context['jd_text'][:3000]}\n\n"
        f"Reorder these resume bullets from most to least relevant:\n{bullets_text}\n\n"
        "Return a JSON array of bullet IDs in order of relevance: [id1, id2, ...]"
    )
    result = provider._run_cli(prompt, expect_json=True)
    if isinstance(result, list):
        id_order = result
    elif isinstance(result, dict) and "order" in result:
        id_order = result["order"]
    else:
        return _python_reorder_bullets(context)

    bullet_map = {b["id"]: b for b in context["bullets"]}
    reordered = [bullet_map[bid] for bid in id_order if bid in bullet_map]
    # Append any bullets not in the AI response
    seen = set(id_order)
    for b in context["bullets"]:
        if b["id"] not in seen:
            reordered.append(b)
    return {"reordered_bullets": reordered}


@bp.route("/api/resume/reorder-bullets", methods=["POST"])
def reorder_bullets():
    """Reorder bullets by JD relevance. Uses AI if available, keyword fallback otherwise.

    Body (JSON):
        recipe_id (required): recipe to pull bullets from
        jd_text (required): job description text
    """
    data = request.get_json(force=True)
    recipe_id = data.get("recipe_id")
    jd_text = data.get("jd_text")

    if not recipe_id or not jd_text:
        return jsonify({"error": "recipe_id and jd_text are required"}), 400

    # Pull recipe to get bullet IDs
    recipe_row = db.query_one("SELECT recipe FROM resume_recipes WHERE id = %s", (recipe_id,))
    if not recipe_row:
        return jsonify({"error": f"Recipe {recipe_id} not found"}), 404

    recipe_json = recipe_row["recipe"]
    if isinstance(recipe_json, str):
        recipe_json = json.loads(recipe_json)

    # Collect bullet IDs from recipe slots
    bullet_ids = []
    for slot_name, ref in recipe_json.items():
        if ref.get("table") == "bullets" and "ids" in ref:
            bullet_ids.extend(ref["ids"])

    if not bullet_ids:
        # Fall back to all bullets
        bullets = db.query("SELECT id, text, type, tags FROM bullets ORDER BY id DESC LIMIT 30")
    else:
        bullets = db.query(
            "SELECT id, text, type, tags FROM bullets WHERE id = ANY(%s)",
            (bullet_ids,),
        )

    if not bullets:
        return jsonify({"error": "No bullets found for this recipe"}), 404

    context = {"bullets": bullets, "jd_text": jd_text}

    from ai_providers.router import route_inference
    result = route_inference(
        task="reorder_bullets",
        context=context,
        python_fallback=_python_reorder_bullets,
        ai_handler=_ai_reorder_bullets,
    )
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# POST /api/resume/rewrite-summary — AI-driven summary rewrite for target role
# ---------------------------------------------------------------------------

def _python_rewrite_summary(context: dict) -> dict:
    """Template-based summary using existing summary_variants."""
    role_type = context["role_type"]
    summary_row = db.query_one(
        "SELECT text FROM summary_variants WHERE role_type ILIKE %s LIMIT 1",
        (role_type,),
    )
    if summary_row:
        return {"summary": summary_row["text"], "source": "summary_variants"}
    # Fall back to first available summary
    fallback = db.query_one("SELECT text, role_type FROM summary_variants ORDER BY id LIMIT 1")
    if fallback:
        return {"summary": fallback["text"], "source": f"fallback ({fallback['role_type']})"}
    return {"summary": "", "source": "none", "error": "No summary variants found"}


def _ai_rewrite_summary(context: dict) -> dict:
    """AI-enhanced summary rewrite."""
    from ai_providers import get_provider
    provider = get_provider()

    # Pull base summary for context
    base = db.query_one(
        "SELECT text FROM summary_variants WHERE role_type ILIKE %s LIMIT 1",
        (context["role_type"],),
    )
    base_text = base["text"] if base else ""

    # Pull candidate profile for grounding
    profile = db.query_one("SELECT full_name, credentials FROM resume_header ORDER BY id LIMIT 1")
    name = profile["full_name"] if profile else "the candidate"

    prompt = (
        f"Rewrite this professional summary for a {context['role_type']} role.\n\n"
        f"Candidate: {name}\n"
        f"Base summary: {base_text}\n\n"
        f"Job description:\n{context['jd_text'][:3000]}\n\n"
        "Write a 3-4 sentence professional summary that:\n"
        "- Opens with years of experience and domain\n"
        "- Highlights 2-3 relevant achievements with metrics\n"
        "- Matches the JD's language and priorities\n"
        "- Uses conversational, direct tone (no buzzwords)\n\n"
        'Return JSON: {"summary": "..."}'
    )
    result = provider._run_cli(prompt, expect_json=True)
    if isinstance(result, dict) and "summary" in result:
        return {"summary": result["summary"], "source": "ai"}
    return _python_rewrite_summary(context)


@bp.route("/api/resume/rewrite-summary", methods=["POST"])
def rewrite_summary():
    """Rewrite professional summary for a target role type using AI or template fallback.

    Body (JSON):
        role_type (required): target role type (CTO, VP Eng, etc.)
        jd_text (optional): job description for contextual rewriting
    """
    data = request.get_json(force=True)
    role_type = data.get("role_type")
    jd_text = data.get("jd_text", "")

    if not role_type:
        return jsonify({"error": "role_type is required"}), 400

    context = {"role_type": role_type, "jd_text": jd_text}

    from ai_providers.router import route_inference
    result = route_inference(
        task="rewrite_summary",
        context=context,
        python_fallback=_python_rewrite_summary,
        ai_handler=_ai_rewrite_summary if jd_text else None,
    )
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# POST /api/resume/keyword-adjust — AI-driven keyword mirroring
# ---------------------------------------------------------------------------

# Common synonym mappings for rule-based fallback
_SYNONYM_MAP = {
    "managed": ["led", "directed", "oversaw", "supervised"],
    "developed": ["built", "created", "designed", "engineered"],
    "improved": ["enhanced", "optimized", "streamlined", "upgraded"],
    "implemented": ["deployed", "launched", "rolled out", "delivered"],
    "team": ["group", "squad", "unit", "cross-functional team"],
    "project": ["initiative", "program", "effort"],
    "software": ["application", "platform", "system", "solution"],
    "data": ["analytics", "metrics", "insights"],
    "cloud": ["AWS", "Azure", "GCP", "cloud infrastructure"],
    "agile": ["scrum", "kanban", "sprint-based", "iterative"],
}


def _python_keyword_adjust(context: dict) -> dict:
    """Rule-based keyword adjustment using synonym mappings."""
    resume_text = context["resume_text"]
    jd_text = context["jd_text"]
    jd_keywords = {kw["keyword"] for kw in _extract_keywords(jd_text)[:30]}

    adjustments = []
    adjusted_text = resume_text
    for jd_kw in jd_keywords:
        jd_lower = jd_kw.lower()
        # Check if any synonym of the JD keyword appears in resume
        for base_word, synonyms in _SYNONYM_MAP.items():
            all_forms = [base_word] + synonyms
            if jd_lower in [s.lower() for s in all_forms]:
                # Find which synonym is in the resume that could be replaced
                for syn in all_forms:
                    if syn.lower() != jd_lower and syn.lower() in resume_text.lower():
                        # Replace first occurrence (case-insensitive)
                        pattern = re.compile(re.escape(syn), re.IGNORECASE)
                        new_text = pattern.sub(jd_kw, adjusted_text, count=1)
                        if new_text != adjusted_text:
                            adjustments.append({
                                "original": syn,
                                "replacement": jd_kw,
                                "reason": "JD keyword mirror",
                            })
                            adjusted_text = new_text
                        break

    return {
        "adjusted_text": adjusted_text,
        "adjustments": adjustments,
        "adjustment_count": len(adjustments),
    }


def _ai_keyword_adjust(context: dict) -> dict:
    """AI-enhanced keyword adjustment."""
    from ai_providers import get_provider
    provider = get_provider()

    prompt = (
        f"Given this job description:\n{context['jd_text'][:3000]}\n\n"
        f"And this resume text:\n{context['resume_text'][:3000]}\n\n"
        "Adjust the resume text to mirror the JD's language and keywords. Rules:\n"
        "- Replace synonyms with the exact terms used in the JD\n"
        "- Do NOT change meaning or add false claims\n"
        "- Do NOT change metrics or numbers\n"
        "- Keep the same sentence structure\n\n"
        'Return JSON: {"adjusted_text": "...", "adjustments": [{"original": "...", "replacement": "...", "reason": "..."}]}'
    )
    result = provider._run_cli(prompt, expect_json=True)
    if isinstance(result, dict) and "adjusted_text" in result:
        result["adjustment_count"] = len(result.get("adjustments", []))
        return result
    return _python_keyword_adjust(context)


@bp.route("/api/resume/keyword-adjust", methods=["POST"])
def keyword_adjust():
    """Adjust resume keywords to mirror JD language. AI-driven with rule-based fallback.

    Body (JSON):
        resume_text (required): resume text to adjust
        jd_text (required): job description text
    """
    data = request.get_json(force=True)
    resume_text = data.get("resume_text")
    jd_text = data.get("jd_text")

    if not resume_text or not jd_text:
        return jsonify({"error": "resume_text and jd_text are required"}), 400

    context = {"resume_text": resume_text, "jd_text": jd_text}

    from ai_providers.router import route_inference
    result = route_inference(
        task="keyword_adjust",
        context=context,
        python_fallback=_python_keyword_adjust,
        ai_handler=_ai_keyword_adjust,
    )
    return jsonify(result), 200
