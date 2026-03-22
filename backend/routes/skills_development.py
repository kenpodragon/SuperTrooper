"""Routes for skills development & certification planning."""

import json
import re
from collections import Counter
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("skills_development", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_skills_from_text(text):
    """Extract probable skill tokens from JD or gap text."""
    if not text:
        return []
    # Normalise and split on common delimiters
    text = text.lower()
    tokens = re.split(r"[,;/\n\r•·|]+", text)
    return [t.strip() for t in tokens if 2 < len(t.strip()) < 60]


def _get_all_user_skills():
    """Return set of lowercase skill names the user has."""
    rows = db.query("SELECT LOWER(name) AS name FROM skills")
    return {r["name"] for r in rows}


def _categorise_gap(skill_name, user_skills):
    """Categorise a gap skill relative to user's skills."""
    sl = skill_name.lower()
    if sl in user_skills:
        return "not_showcased"
    # Check adjacency – user has a skill that shares a root word
    for us in user_skills:
        if len(us) > 3 and (us in sl or sl in us):
            return "adjacent"
    return "deep_gap"


# ---------------------------------------------------------------------------
# 1. GET /api/skills/gaps — Skill gap analysis against target JDs
# ---------------------------------------------------------------------------

@bp.route("/api/skills/gaps", methods=["GET"])
def skill_gaps():
    """Analyse skill gaps across all stored gap analyses."""
    gap_rows = db.query(
        "SELECT id, gaps, partial_matches, strong_matches FROM gap_analyses"
    )
    user_skills = _get_all_user_skills()
    gap_counter = Counter()

    for row in gap_rows:
        gaps_json = row.get("gaps")
        if not gaps_json:
            continue
        if isinstance(gaps_json, str):
            gaps_json = json.loads(gaps_json)
        if isinstance(gaps_json, list):
            for item in gaps_json:
                name = item if isinstance(item, str) else (item.get("skill") or item.get("name") or "")
                if name:
                    gap_counter[name.strip()] += 1
        elif isinstance(gaps_json, dict):
            for name in gaps_json.keys():
                gap_counter[name.strip()] += 1

    results = []
    for skill, count in gap_counter.most_common():
        cat = _categorise_gap(skill, user_skills)
        rec = {
            "not_showcased": "Add to resume — you already have this skill",
            "adjacent": "Upskill — you have a related skill",
            "deep_gap": "Learning required — new skill area",
        }
        results.append({
            "skill": skill,
            "category": cat,
            "jd_count": count,
            "recommendation": rec[cat],
        })

    total_skills_asked = len(gap_counter)
    covered = sum(1 for r in results if r["category"] == "not_showcased")
    coverage_pct = round(covered / total_skills_asked * 100, 1) if total_skills_asked else 0

    return jsonify({"gaps": results, "coverage_pct": coverage_pct}), 200


# ---------------------------------------------------------------------------
# 2. GET /api/skills/trends — Skill demand trends
# ---------------------------------------------------------------------------

@bp.route("/api/skills/trends", methods=["GET"])
def skill_trends():
    """Analyse skill demand trends across saved JDs and gap analyses."""
    user_skills = _get_all_user_skills()
    skill_counter = Counter()

    # Pull skills from saved_jobs JD text
    jd_rows = db.query("SELECT jd_text FROM saved_jobs WHERE jd_text IS NOT NULL")
    for row in jd_rows:
        tokens = _extract_skills_from_text(row["jd_text"])
        # Match against known skill names for relevance
        for t in tokens:
            if t.lower() in user_skills or len(t.split()) <= 3:
                skill_counter[t.lower()] += 1

    # Pull from gap_analyses parsed JD requirements
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
                    name = item if isinstance(item, str) else (item.get("skill") or item.get("name") or "")
                    if name:
                        skill_counter[name.strip().lower()] += 1
            elif isinstance(data, dict):
                for k in data.keys():
                    skill_counter[k.strip().lower()] += 1

    # Build trending list
    trending = []
    for skill, freq in skill_counter.most_common(50):
        trending.append({
            "skill": skill,
            "frequency": freq,
            "have": skill in user_skills,
            "category": _categorise_gap(skill, user_skills),
        })

    # Rising = high frequency + user doesn't have
    rising = [t for t in trending if not t["have"]][:15]

    total = len(trending)
    have_count = sum(1 for t in trending if t["have"])
    coverage = round(have_count / total * 100, 1) if total else 0

    return jsonify({
        "trending": trending,
        "rising": rising,
        "user_coverage_pct": coverage,
    }), 200


# ---------------------------------------------------------------------------
# 3. POST /api/skills/certification-roi — Certification ROI analysis
# ---------------------------------------------------------------------------

@bp.route("/api/skills/certification-roi", methods=["POST"])
def certification_roi():
    """Analyse which certifications appear in high-scoring JDs."""
    data = request.get_json(silent=True) or {}
    role_type = data.get("role_type")

    # Common certification patterns to search for in JD text
    cert_patterns = [
        "PMP", "AWS", "Azure", "GCP", "Kubernetes", "CKAD", "CKA",
        "Scrum", "CSM", "CSPO", "SAFe", "ITIL", "Six Sigma",
        "CISSP", "CISM", "CompTIA", "Security+", "TOGAF",
        "Google Cloud", "Terraform", "Docker", "CCNA", "CCNP",
        "PMI-ACP", "Prince2", "Lean", "Agile", "MBA",
        "PhD", "Masters", "Certified", "Certification",
    ]

    # Get JD texts from saved_jobs (optionally filtered by role type)
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

    # Cross-reference with existing certifications
    existing = db.query("SELECT LOWER(name) AS name FROM certifications WHERE is_active = TRUE")
    existing_names = {r["name"] for r in existing}

    recommendations = []
    for cert, freq in cert_counter.most_common():
        have = any(cert.lower() in en for en in existing_names)
        recommendations.append({
            "cert_name": cert,
            "jd_frequency": freq,
            "have": have,
            "estimated_unlock": freq if not have else 0,
            "priority": 1 if freq >= 5 and not have else (2 if freq >= 2 and not have else 3),
        })

    return jsonify({"recommendations": recommendations}), 200


# ---------------------------------------------------------------------------
# 4. CRUD /api/learning-plans
# ---------------------------------------------------------------------------

@bp.route("/api/learning-plans", methods=["POST"])
def create_learning_plan():
    """Create a new learning plan."""
    data = request.get_json(force=True)
    if not data.get("skill_name"):
        return jsonify({"error": "skill_name is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO learning_plans (skill_name, gap_category, priority, resources,
            milestones, status, jd_unlock_count, estimated_hours, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data["skill_name"],
            data.get("gap_category", "deep_gap"),
            data.get("priority", 3),
            json.dumps(data["resources"]) if data.get("resources") else None,
            json.dumps(data["milestones"]) if data.get("milestones") else None,
            data.get("status", "planned"),
            data.get("jd_unlock_count", 0),
            data.get("estimated_hours"),
            data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/learning-plans", methods=["GET"])
def list_learning_plans():
    """List learning plans with optional status filter."""
    status = request.args.get("status")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if status:
        clauses.append("status = %s")
        params.append(status)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT * FROM learning_plans
        {where}
        ORDER BY priority ASC, created_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/learning-plans/<int:plan_id>", methods=["GET"])
def get_learning_plan(plan_id):
    """Get a single learning plan."""
    row = db.query_one("SELECT * FROM learning_plans WHERE id = %s", (plan_id,))
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/learning-plans/<int:plan_id>", methods=["PUT"])
def update_learning_plan(plan_id):
    """Update a learning plan."""
    data = request.get_json(force=True)
    allowed = [
        "skill_name", "gap_category", "priority", "resources", "milestones",
        "status", "jd_unlock_count", "estimated_hours", "notes",
    ]
    json_fields = {"resources", "milestones"}
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

    sets.append("updated_at = NOW()")
    params.append(plan_id)
    row = db.execute_returning(
        f"UPDATE learning_plans SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# 5. POST /api/skills/add — Log newly acquired skill
# ---------------------------------------------------------------------------

@bp.route("/api/skills/add", methods=["POST"])
def add_skill():
    """Add a newly acquired skill to the skills table."""
    data = request.get_json(force=True)
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    # Check for duplicate
    existing = db.query_one(
        "SELECT id FROM skills WHERE LOWER(name) = LOWER(%s)", (data["name"],)
    )
    if existing:
        return jsonify({"error": "Skill already exists", "existing_id": existing["id"]}), 409

    row = db.execute_returning(
        """
        INSERT INTO skills (name, category, proficiency, acquired_date)
        VALUES (%s, %s, %s, %s)
        RETURNING *
        """,
        (
            data["name"],
            data.get("category", "tool"),
            data.get("proficiency", "familiar"),
            data.get("acquired_date"),
        ),
    )
    return jsonify(row), 201


# ---------------------------------------------------------------------------
# 6. POST /api/skills/differentiator — Differentiator analysis
# ---------------------------------------------------------------------------

@bp.route("/api/skills/differentiator", methods=["POST"])
def differentiator_analysis():
    """Analyse user's unique skill combinations vs typical JD requirements."""
    user_skills_rows = db.query("SELECT name, category, proficiency FROM skills")
    user_skills = {r["name"].lower(): r for r in user_skills_rows}

    # Group user skills by category
    by_category = {}
    for r in user_skills_rows:
        by_category.setdefault(r["category"], []).append(r["name"])

    # Build differentiator combos (cross-category expertise)
    differentiators = []
    categories = list(by_category.keys())
    for i, cat1 in enumerate(categories):
        for cat2 in categories[i + 1:]:
            combo_label = f"{cat1.title()} + {cat2.title()}"
            examples = by_category[cat1][:2] + by_category[cat2][:2]
            differentiators.append({
                "combo": combo_label,
                "skills": examples,
                "rarity_note": f"Cross-domain expertise in {cat1} and {cat2}",
            })

    # Expert-level skills are differentiators on their own
    experts = [r for r in user_skills_rows if r.get("proficiency") == "expert"]
    for e in experts:
        differentiators.append({
            "combo": f"Expert: {e['name']}",
            "skills": [e["name"]],
            "rarity_note": f"Expert-level {e['category']} skill",
        })

    # Gaps that would unlock the most JDs
    gap_rows = db.query("SELECT gaps FROM gap_analyses WHERE gaps IS NOT NULL")
    gap_counter = Counter()
    for row in gap_rows:
        gaps_data = row["gaps"]
        if isinstance(gaps_data, str):
            try:
                gaps_data = json.loads(gaps_data)
            except (json.JSONDecodeError, TypeError):
                continue
        if isinstance(gaps_data, list):
            for item in gaps_data:
                name = item if isinstance(item, str) else (item.get("skill") or item.get("name") or "")
                if name and name.lower() not in user_skills:
                    gap_counter[name.strip()] += 1
        elif isinstance(gaps_data, dict):
            for name in gaps_data.keys():
                if name.lower() not in user_skills:
                    gap_counter[name.strip()] += 1

    gaps_to_unlock = [
        {"skill": s, "unlock_count": c}
        for s, c in gap_counter.most_common(10)
    ]

    return jsonify({
        "differentiators": differentiators[:15],
        "gaps_to_unlock": gaps_to_unlock,
    }), 200


# ---------------------------------------------------------------------------
# 7. POST /api/skills/rerun-gaps — Rerun gap analysis after skills update
# ---------------------------------------------------------------------------

@bp.route("/api/skills/rerun-gaps", methods=["POST"])
def rerun_gaps():
    """Rerun gap analysis against saved JDs with current skills."""
    user_skills = _get_all_user_skills()

    # Get all gap analyses
    ga_rows = db.query(
        "SELECT id, gaps, strong_matches, partial_matches, overall_score FROM gap_analyses"
    )

    before_after = []
    for row in ga_rows:
        gaps_data = row.get("gaps")
        if not gaps_data:
            continue
        if isinstance(gaps_data, str):
            try:
                gaps_data = json.loads(gaps_data)
            except (json.JSONDecodeError, TypeError):
                continue

        original_gap_count = len(gaps_data) if isinstance(gaps_data, (list, dict)) else 0

        # Recount: how many gaps are now covered?
        still_gaps = []
        now_covered = []
        if isinstance(gaps_data, list):
            items = gaps_data
        elif isinstance(gaps_data, dict):
            items = [{"skill": k} for k in gaps_data.keys()]
        else:
            items = []
        for item in items:
            name = item if isinstance(item, str) else (item.get("skill") or item.get("name") or "")
            if not name:
                continue
            if name.lower() in user_skills:
                now_covered.append(name)
            else:
                still_gaps.append(name)

        before_after.append({
            "gap_analysis_id": row["id"],
            "original_score": row.get("overall_score"),
            "original_gap_count": original_gap_count,
            "remaining_gap_count": len(still_gaps),
            "newly_covered": now_covered,
            "still_missing": still_gaps,
        })

    total_original = sum(r["original_gap_count"] for r in before_after)
    total_remaining = sum(r["remaining_gap_count"] for r in before_after)
    improvement = round((1 - total_remaining / total_original) * 100, 1) if total_original else 0

    return jsonify({
        "analyses": before_after,
        "summary": {
            "total_original_gaps": total_original,
            "total_remaining_gaps": total_remaining,
            "improvement_pct": improvement,
        },
    }), 200
