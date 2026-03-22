"""Routes for gap_analyses (persisted gap analysis results) and JD parsing."""

import json
import re
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("gap_analysis", __name__)


@bp.route("/api/gap-analyses", methods=["GET"])
def list_gap_analyses():
    """List gap analyses with optional filters."""
    application_id = request.args.get("application_id")
    saved_job_id = request.args.get("saved_job_id")
    recommendation = request.args.get("recommendation")
    min_score = request.args.get("min_score")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if application_id:
        clauses.append("g.application_id = %s")
        params.append(int(application_id))
    if saved_job_id:
        clauses.append("g.saved_job_id = %s")
        params.append(int(saved_job_id))
    if recommendation:
        clauses.append("g.recommendation = %s")
        params.append(recommendation)
    if min_score:
        clauses.append("g.overall_score >= %s")
        params.append(float(min_score))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT g.id, g.application_id, g.saved_job_id, g.overall_score,
               g.recommendation, g.notes, g.created_at, g.updated_at,
               a.company_name, a.role AS app_role,
               sj.title AS job_title, sj.company AS job_company
        FROM gap_analyses g
        LEFT JOIN applications a ON a.id = g.application_id
        LEFT JOIN saved_jobs sj ON sj.id = g.saved_job_id
        {where}
        ORDER BY g.created_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/gap-analyses/<int:gap_id>", methods=["GET"])
def get_gap_analysis(gap_id):
    """Single gap analysis with full details."""
    row = db.query_one(
        """
        SELECT g.*, a.company_name, a.role AS app_role,
               sj.title AS job_title, sj.company AS job_company
        FROM gap_analyses g
        LEFT JOIN applications a ON a.id = g.application_id
        LEFT JOIN saved_jobs sj ON sj.id = g.saved_job_id
        WHERE g.id = %s
        """,
        (gap_id,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/gap-analyses", methods=["POST"])
def create_gap_analysis():
    """Save a new gap analysis."""
    data = request.get_json(force=True)

    row = db.execute_returning(
        """
        INSERT INTO gap_analyses (application_id, saved_job_id, jd_text, jd_parsed,
            strong_matches, partial_matches, gaps, bonus_value,
            fit_scores, overall_score, recommendation, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data.get("application_id"), data.get("saved_job_id"),
            data.get("jd_text"),
            json.dumps(data["jd_parsed"]) if data.get("jd_parsed") else None,
            json.dumps(data["strong_matches"]) if data.get("strong_matches") else None,
            json.dumps(data["partial_matches"]) if data.get("partial_matches") else None,
            json.dumps(data["gaps"]) if data.get("gaps") else None,
            json.dumps(data["bonus_value"]) if data.get("bonus_value") else None,
            json.dumps(data["fit_scores"]) if data.get("fit_scores") else None,
            data.get("overall_score"),
            data.get("recommendation"),
            data.get("notes"),
        ),
    )

    # Link to application if provided
    if data.get("application_id"):
        db.execute(
            "UPDATE applications SET gap_analysis_id = %s WHERE id = %s",
            (row["id"], data["application_id"]),
        )

    return jsonify(row), 201


@bp.route("/api/gap-analyses/<int:gap_id>", methods=["PATCH"])
def update_gap_analysis(gap_id):
    """Update a gap analysis."""
    data = request.get_json(force=True)
    allowed = [
        "application_id", "saved_job_id", "jd_text", "jd_parsed",
        "strong_matches", "partial_matches", "gaps", "bonus_value",
        "fit_scores", "overall_score", "recommendation", "notes",
    ]
    json_fields = {"jd_parsed", "strong_matches", "partial_matches", "gaps",
                   "bonus_value", "fit_scores"}
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            if key in json_fields:
                params.append(json.dumps(data[key]) if data[key] else None)
            else:
                params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(gap_id)
    row = db.execute_returning(
        f"UPDATE gap_analyses SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/gap-analyses/<int:gap_id>", methods=["DELETE"])
def delete_gap_analysis(gap_id):
    """Delete a gap analysis."""
    count = db.execute("DELETE FROM gap_analyses WHERE id = %s", (gap_id,))
    if count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": gap_id}), 200


# ---------------------------------------------------------------------------
# JD Parsing helpers
# ---------------------------------------------------------------------------

# Salary regex patterns
_SALARY_PATTERNS = [
    # $150k-$200k or $150K - $200K
    re.compile(r"\$\s*([\d,.]+)\s*[kK]\s*[-\u2013to]+\s*\$?\s*([\d,.]+)\s*[kK]"),
    # $150,000-$200,000 or $150000 - $200000
    re.compile(r"\$\s*([\d,]+)\s*[-\u2013to]+\s*\$?\s*([\d,]+)"),
    # 150k-200k without dollar sign
    re.compile(r"([\d,.]+)\s*[kK]\s*[-\u2013to]+\s*([\d,.]+)\s*[kK]\s*(?:per\s*year|annually|/yr)?"),
]

# Common skill keywords for extraction
_COMMON_SKILLS = [
    "python", "java", "javascript", "typescript", "react", "angular", "vue",
    "node.js", "aws", "azure", "gcp", "docker", "kubernetes", "sql", "nosql",
    "machine learning", "deep learning", "ai", "data science", "agile", "scrum",
    "leadership", "strategy", "product management", "devops", "terraform",
    "ci/cd", "microservices", "rest api", "graphql", "go", "rust", "c++",
    "c#", ".net", "ruby", "php", "swift", "django", "flask", "spring",
    "fastapi", "elasticsearch", "tableau", "power bi", "snowflake",
    "databricks", "airflow", "dbt", "kafka", "redis", "mongodb", "postgresql",
    "pandas", "spark", "pytorch", "tensorflow", "nlp", "computer vision",
    "blockchain", "security", "networking", "linux", "git",
]

_REMOTE_PATTERNS = [
    (re.compile(r"\bfully?\s*remote\b", re.I), "remote"),
    (re.compile(r"\bhybrid\b", re.I), "hybrid"),
    (re.compile(r"\bon[- ]?site\b", re.I), "onsite"),
    (re.compile(r"\bin[- ]?office\b", re.I), "onsite"),
    (re.compile(r"\bremote[- ]?first\b", re.I), "remote"),
    (re.compile(r"\bwork from home\b", re.I), "remote"),
]

_EDUCATION_PATTERNS = [
    re.compile(r"\b(bachelor'?s?|bs|ba|b\.s\.|b\.a\.)\b", re.I),
    re.compile(r"\b(master'?s?|ms|ma|m\.s\.|m\.a\.|mba|m\.b\.a\.)\b", re.I),
    re.compile(r"\b(ph\.?d\.?|doctorate|doctoral)\b", re.I),
]

_YEARS_EXP_PATTERN = re.compile(
    r"(\d+)\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp)", re.I
)


def _parse_salary(text: str) -> tuple:
    """Extract salary_min and salary_max from text. Returns (min, max) or (None, None)."""
    for pat in _SALARY_PATTERNS:
        m = pat.search(text)
        if m:
            low_str = m.group(1).replace(",", "").replace(".", "")
            high_str = m.group(2).replace(",", "").replace(".", "")
            try:
                low = float(low_str)
                high = float(high_str)
                # Normalize k values
                if low < 1000:
                    low *= 1000
                if high < 1000:
                    high *= 1000
                return (low, high)
            except ValueError:
                continue
    return (None, None)


def _parse_jd(text: str) -> dict:
    """Parse a JD text into structured data."""
    text_lower = text.lower()

    # Required skills: skills mentioned in the JD
    required_skills = []
    preferred_skills = []
    for skill in _COMMON_SKILLS:
        if skill in text_lower:
            # Heuristic: if near "preferred", "nice to have", "bonus" => preferred
            idx = text_lower.find(skill)
            context_start = max(0, idx - 200)
            context = text_lower[context_start:idx + len(skill) + 200]
            if any(kw in context for kw in ["preferred", "nice to have", "bonus", "plus", "ideally"]):
                preferred_skills.append(skill)
            else:
                required_skills.append(skill)

    # Years of experience
    years_experience = None
    ym = _YEARS_EXP_PATTERN.search(text)
    if ym:
        years_experience = int(ym.group(1))

    # Education
    education = []
    for pat in _EDUCATION_PATTERNS:
        if pat.search(text):
            education.append(pat.pattern.replace(r"\b", "").strip("()"))

    # Salary
    salary_min, salary_max = _parse_salary(text)
    salary_range = None
    if salary_min and salary_max:
        salary_range = f"${int(salary_min):,}-${int(salary_max):,}"

    # Location - try to find city/state patterns
    location = None
    loc_match = re.search(
        r"(?:location|based in|office in|located in)[:\s]+([A-Z][a-zA-Z\s,]+?)(?:\.|;|\n|$)",
        text,
    )
    if loc_match:
        location = loc_match.group(1).strip()[:100]

    # Remote policy
    remote_policy = None
    for pat, policy in _REMOTE_PATTERNS:
        if pat.search(text):
            remote_policy = policy
            break

    return {
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "years_experience": years_experience,
        "education": education,
        "salary_range": salary_range,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "location": location,
        "remote_policy": remote_policy,
    }


# ---------------------------------------------------------------------------
# POST /api/jd/parse — parse raw JD text into structured data
# ---------------------------------------------------------------------------

@bp.route("/api/jd/parse", methods=["POST"])
def parse_jd():
    """Parse raw JD text into structured data and optionally store on a saved_job.

    Body (JSON):
        jd_text (required): raw JD text
        saved_job_id (optional): if provided, stores parsed data on the saved_job
    """
    data = request.get_json(force=True)
    jd_text = data.get("jd_text")
    saved_job_id = data.get("saved_job_id")

    if not jd_text:
        return jsonify({"error": "jd_text is required"}), 400

    parsed = _parse_jd(jd_text)

    # Store on saved_job if requested
    if saved_job_id:
        existing = db.query_one("SELECT id FROM saved_jobs WHERE id = %s", (saved_job_id,))
        if not existing:
            return jsonify({"error": f"Saved job {saved_job_id} not found"}), 404

        db.execute(
            """UPDATE saved_jobs
               SET jd_parsed = %s,
                   salary_min = COALESCE(%s, salary_min),
                   salary_max = COALESCE(%s, salary_max),
                   updated_at = NOW()
               WHERE id = %s""",
            (
                json.dumps(parsed),
                parsed.get("salary_min"),
                parsed.get("salary_max"),
                saved_job_id,
            ),
        )

    return jsonify({"parsed": parsed, "saved_job_id": saved_job_id}), 200


# ---------------------------------------------------------------------------
# GET /api/jd/<saved_job_id>/parsed — return parsed JD structure
# ---------------------------------------------------------------------------

@bp.route("/api/jd/<int:saved_job_id>/parsed", methods=["GET"])
def get_parsed_jd(saved_job_id):
    """Return parsed JD structure for a saved job.

    If jd_parsed is NULL but jd_text exists, parses on the fly and stores.
    """
    row = db.query_one(
        "SELECT id, title, company, jd_text, jd_parsed, salary_min, salary_max FROM saved_jobs WHERE id = %s",
        (saved_job_id,),
    )
    if not row:
        return jsonify({"error": "Saved job not found"}), 404

    # If already parsed, return it
    if row.get("jd_parsed"):
        return jsonify({
            "saved_job_id": saved_job_id,
            "parsed": row["jd_parsed"],
            "salary_min": row.get("salary_min"),
            "salary_max": row.get("salary_max"),
        }), 200

    # Parse on the fly if jd_text available
    jd_text = row.get("jd_text")
    if not jd_text:
        return jsonify({"error": "No JD text available for this job"}), 404

    parsed = _parse_jd(jd_text)

    # Store for next time
    db.execute(
        """UPDATE saved_jobs
           SET jd_parsed = %s,
               salary_min = COALESCE(%s, salary_min),
               salary_max = COALESCE(%s, salary_max),
               updated_at = NOW()
           WHERE id = %s""",
        (
            json.dumps(parsed),
            parsed.get("salary_min"),
            parsed.get("salary_max"),
            saved_job_id,
        ),
    )

    return jsonify({
        "saved_job_id": saved_job_id,
        "parsed": parsed,
        "salary_min": parsed.get("salary_min"),
        "salary_max": parsed.get("salary_max"),
    }), 200
