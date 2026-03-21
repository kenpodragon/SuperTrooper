"""Routes for search endpoints and gap analysis."""

import re
from collections import Counter

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("search", __name__)


@bp.route("/api/search/bullets", methods=["GET"])
def search_bullets():
    """Full-text bullet search with tag and role_type filters."""
    q = request.args.get("q", "")
    tags = request.args.getlist("tags")
    role_type = request.args.get("role_type")
    industry = request.args.get("industry")
    limit = int(request.args.get("limit", 20))

    clauses, params = [], []
    if q:
        clauses.append("b.text ILIKE %s")
        params.append(f"%{q}%")
    if tags:
        clauses.append("b.tags && %s")
        params.append(tags)
    if role_type:
        clauses.append("%s = ANY(b.role_suitability)")
        params.append(role_type)
    if industry:
        clauses.append("%s = ANY(b.industry_suitability)")
        params.append(industry)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT b.id, b.text, b.type, b.tags, b.role_suitability,
               b.industry_suitability, b.metrics_json, b.detail_recall,
               ch.employer, ch.title
        FROM bullets b
        LEFT JOIN career_history ch ON ch.id = b.career_history_id
        {where}
        ORDER BY b.id
        LIMIT %s
        """,
        params + [limit],
    )
    return jsonify({"count": len(rows), "results": rows}), 200


@bp.route("/api/search/emails", methods=["GET"])
def search_emails():
    """Email search with category and date filters."""
    q = request.args.get("q", "")
    category = request.args.get("category")
    after = request.args.get("after")
    before = request.args.get("before")
    limit = int(request.args.get("limit", 20))

    clauses, params = [], []
    if q:
        clauses.append("(subject ILIKE %s OR snippet ILIKE %s OR body ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if category:
        clauses.append("category = %s")
        params.append(category)
    if after:
        clauses.append("date >= %s")
        params.append(after)
    if before:
        clauses.append("date <= %s")
        params.append(before)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT id, date, from_name, from_address, subject, snippet, category,
               application_id
        FROM emails
        {where}
        ORDER BY date DESC NULLS LAST
        LIMIT %s
        """,
        params + [limit],
    )
    return jsonify({"count": len(rows), "results": rows}), 200


@bp.route("/api/search/companies", methods=["GET"])
def search_companies():
    """Company name search."""
    q = request.args.get("q", "")
    limit = int(request.args.get("limit", 20))

    rows = db.query(
        """
        SELECT id, name, sector, hq_location, size, stage, fit_score, priority,
               target_role, melbourne_relevant
        FROM companies
        WHERE name ILIKE %s
        ORDER BY fit_score DESC NULLS LAST
        LIMIT %s
        """,
        (f"%{q}%", limit),
    )
    return jsonify({"count": len(rows), "results": rows}), 200


@bp.route("/api/search/contacts", methods=["GET"])
def search_contacts():
    """Find contacts at a company (network check)."""
    company = request.args.get("company", "")
    q = request.args.get("q", "")
    limit = int(request.args.get("limit", 20))

    clauses, params = [], []
    if company:
        clauses.append("company ILIKE %s")
        params.append(f"%{company}%")
    if q:
        clauses.append("(name ILIKE %s OR title ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT id, name, company, title, relationship, email, linkedin_url,
               relationship_strength, last_contact
        FROM contacts
        {where}
        ORDER BY relationship_strength, name
        LIMIT %s
        """,
        params + [limit],
    )
    return jsonify({"count": len(rows), "results": rows}), 200


@bp.route("/api/gap-analysis", methods=["POST"])
def gap_analysis():
    """Accept JD text, analyze fit using AI (if available) or rule-based fallback."""
    data = request.get_json(force=True)
    jd_text = data.get("jd_text", "")
    if not jd_text:
        return jsonify({"error": "jd_text is required"}), 400

    from ai_providers.router import route_inference

    result = route_inference(
        task="gap_analysis",
        context={"jd_text": jd_text},
        python_fallback=_python_gap_analysis,
        ai_handler=_ai_gap_analysis,
    )
    return jsonify(result), 200


def _python_gap_analysis(context: dict) -> dict:
    """Rule-based gap analysis using keyword matching against bullets and skills."""
    jd_text = context["jd_text"]

    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "need", "must",
        "that", "this", "these", "those", "it", "its", "we", "our", "you",
        "your", "they", "their", "them", "he", "she", "his", "her", "as",
        "if", "not", "no", "so", "up", "out", "about", "into", "over",
        "after", "before", "between", "through", "during", "such", "each",
        "which", "who", "whom", "what", "where", "when", "how", "all", "any",
        "both", "few", "more", "most", "other", "some", "than", "too", "very",
        "just", "also", "well", "able", "etc", "including", "experience",
        "work", "working", "role", "position", "team", "company", "years",
        "strong", "required", "preferred", "requirements", "qualifications",
        "responsibilities", "job", "description", "candidate", "ideal",
    }

    words = re.findall(r"[a-z][a-z+#/.]+", jd_text.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    keyword_counts = Counter(keywords).most_common(30)
    top_keywords = [k for k, _ in keyword_counts]

    # Search bullets matching each keyword
    matched_bullets = []
    seen_ids = set()

    for kw in top_keywords[:15]:
        rows = db.query(
            """
            SELECT b.id, b.text, b.type, b.tags, b.role_suitability,
                   b.industry_suitability, b.metrics_json, b.detail_recall,
                   ch.employer, ch.title
            FROM bullets b
            LEFT JOIN career_history ch ON ch.id = b.career_history_id
            WHERE b.text ILIKE %s
            LIMIT 5
            """,
            (f"%{kw}%",),
        )
        for row in rows:
            if row["id"] not in seen_ids:
                seen_ids.add(row["id"])
                row["matched_keyword"] = kw
                matched_bullets.append(row)

    # Find matching skills
    matched_skills = []
    for kw in top_keywords:
        skills = db.query(
            "SELECT id, name, category, proficiency, last_used_year FROM skills WHERE name ILIKE %s",
            (f"%{kw}%",),
        )
        for s in skills:
            if s["id"] not in {ms["id"] for ms in matched_skills}:
                s["matched_keyword"] = kw
                matched_skills.append(s)

    # Identify gaps: keywords with no bullet or skill matches
    covered_keywords = set()
    for b in matched_bullets:
        covered_keywords.add(b["matched_keyword"])
    for s in matched_skills:
        covered_keywords.add(s["matched_keyword"])
    gaps = [kw for kw in top_keywords if kw not in covered_keywords]

    # Map to normalized response shape
    strong = []
    seen_strong = set()
    for b in matched_bullets[:20]:
        label = f"{b['matched_keyword']}: {b.get('employer', 'N/A')} - {b.get('title', 'N/A')}"
        if label not in seen_strong:
            seen_strong.add(label)
            strong.append(label)

    partial = []
    seen_partial = set()
    for s in matched_skills:
        label = f"{s['name']} ({s.get('category', 'general')})"
        if label not in seen_partial:
            seen_partial.add(label)
            partial.append(label)

    recommendations = [f"Consider highlighting experience with {g}" for g in gaps[:5]]

    return {
        "fit_score": round(len(covered_keywords) / max(len(top_keywords), 1) * 100, 1),
        "strong_matches": strong,
        "partial_matches": partial,
        "gaps": gaps,
        "recommendations": recommendations,
        "jd_keywords": top_keywords,
    }


def _ai_gap_analysis(context: dict) -> dict:
    """AI-enhanced gap analysis -- stub for future implementation."""
    raise NotImplementedError("AI gap analysis not yet implemented")
