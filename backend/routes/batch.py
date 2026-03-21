"""Batch operation routes — gap analysis, company research, outreach, status updates."""

import uuid
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("batch", __name__)


# ---------------------------------------------------------------------------
# POST /api/batch/gap-analysis
# ---------------------------------------------------------------------------

@bp.route("/api/batch/gap-analysis", methods=["POST"])
def batch_gap_analysis():
    """Run gap analysis for multiple saved jobs against candidate skills.

    Body: { job_ids: [int] }
    Returns: [{ job_id, title, company, match_score, gaps[], strengths[] }]
    """
    data = request.get_json(force=True)
    job_ids = data.get("job_ids")
    if not job_ids or not isinstance(job_ids, list):
        return jsonify({"error": "job_ids must be a non-empty array"}), 400

    # Load candidate skills once
    skill_rows = db.query("SELECT skill, category, proficiency FROM skills ORDER BY skill")
    candidate_skills = {r["skill"].lower() for r in skill_rows}
    skill_list = [r["skill"] for r in skill_rows]

    results = []
    for job_id in job_ids:
        job = db.query_one(
            "SELECT id, title, company, requirements, description FROM saved_jobs WHERE id = %s",
            (job_id,),
        )
        if not job:
            results.append({"job_id": job_id, "error": "Not found"})
            continue

        # Use requirements field if populated, fall back to description
        source_text = (job.get("requirements") or job.get("description") or "").lower()

        # Simple keyword matching: check which candidate skills appear in the JD text
        strengths = [s for s in skill_list if s.lower() in source_text]

        # Gaps: words in JD that look like skill keywords but aren't in candidate skills
        # Use a curated approach: tokenize JD and flag multi-word/single terms not in skills
        jd_tokens = set(source_text.replace(",", " ").replace(".", " ").split())
        # Check existing gap_analyses for this job to surface saved gaps
        saved_gap = db.query_one(
            """
            SELECT overall_score, missing_keywords
            FROM gap_analyses
            WHERE saved_job_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (job_id,),
        )

        if saved_gap:
            match_score = saved_gap.get("overall_score") or 0
            gaps = saved_gap.get("missing_keywords") or []
        else:
            # Naive score: strengths / total skills mentioned in JD (capped at 1.0)
            total_mentioned = max(len([s for s in skill_list if s.lower() in source_text]), 1)
            match_score = round(min(len(strengths) / total_mentioned, 1.0) * 100, 1)
            # Gaps: candidate skills NOT mentioned in JD (may indicate mismatch focus)
            gaps = [s for s in skill_list if s.lower() not in source_text][:10]

        results.append({
            "job_id": job_id,
            "title": job.get("title"),
            "company": job.get("company"),
            "match_score": match_score,
            "strengths": strengths,
            "gaps": gaps,
        })

    return jsonify(results), 200


# ---------------------------------------------------------------------------
# POST /api/batch/research
# ---------------------------------------------------------------------------

@bp.route("/api/batch/research", methods=["POST"])
def batch_research():
    """Look up existing company dossiers for a list of company names.

    Body: { company_names: [str] }
    Returns: [{ company, dossier }]
    """
    data = request.get_json(force=True)
    company_names = data.get("company_names")
    if not company_names or not isinstance(company_names, list):
        return jsonify({"error": "company_names must be a non-empty array"}), 400

    results = []
    for name in company_names:
        row = db.query_one(
            """
            SELECT cd.id, cd.company_id, cd.content, cd.source, cd.created_at,
                   c.name AS company_name, c.sector, c.hq_location, c.size,
                   c.fit_score, c.priority
            FROM company_dossiers cd
            JOIN companies c ON c.id = cd.company_id
            WHERE c.name ILIKE %s
            ORDER BY cd.created_at DESC
            LIMIT 1
            """,
            (name,),
        )
        if row:
            results.append({"company": name, "dossier": row})
        else:
            # Fall back to basic company record if no dossier exists
            company = db.query_one(
                "SELECT id, name, sector, hq_location, size, fit_score, priority, notes FROM companies WHERE name ILIKE %s",
                (name,),
            )
            results.append({
                "company": name,
                "dossier": company if company else None,
            })

    return jsonify(results), 200


# ---------------------------------------------------------------------------
# POST /api/batch/outreach
# ---------------------------------------------------------------------------

@bp.route("/api/batch/outreach", methods=["POST"])
def batch_outreach():
    """Generate personalized outreach drafts for a list of contacts.

    Body: { contact_ids: [int], template: str }
    Template supports: {name}, {first_name}, {title}, {company}, {relationship}
    Returns: [{ contact_id, name, draft }]
    """
    data = request.get_json(force=True)
    contact_ids = data.get("contact_ids")
    template = data.get("template", "")
    if not contact_ids or not isinstance(contact_ids, list):
        return jsonify({"error": "contact_ids must be a non-empty array"}), 400
    if not template:
        return jsonify({"error": "template is required"}), 400

    results = []
    for contact_id in contact_ids:
        contact = db.query_one(
            """
            SELECT id, name, title, company, relationship, email,
                   linkedin_url, notes, relationship_strength
            FROM contacts
            WHERE id = %s
            """,
            (contact_id,),
        )
        if not contact:
            results.append({"contact_id": contact_id, "error": "Not found"})
            continue

        name = contact.get("name") or ""
        first_name = name.split()[0] if name else ""

        draft = (
            template
            .replace("{name}", name)
            .replace("{first_name}", first_name)
            .replace("{title}", contact.get("title") or "")
            .replace("{company}", contact.get("company") or "")
            .replace("{relationship}", contact.get("relationship") or "contact")
        )

        results.append({
            "contact_id": contact_id,
            "name": name,
            "email": contact.get("email"),
            "draft": draft,
        })

    return jsonify(results), 200


# ---------------------------------------------------------------------------
# POST /api/batch/status-update
# ---------------------------------------------------------------------------

@bp.route("/api/batch/status-update", methods=["POST"])
def batch_status_update():
    """Bulk update application statuses.

    Body: { application_ids: [int], new_status: str, notes: str? }
    Returns: { updated: int, errors: [] }
    """
    data = request.get_json(force=True)
    application_ids = data.get("application_ids")
    new_status = data.get("new_status")
    notes = data.get("notes")

    if not application_ids or not isinstance(application_ids, list):
        return jsonify({"error": "application_ids must be a non-empty array"}), 400
    if not new_status:
        return jsonify({"error": "new_status is required"}), 400

    errors = []

    if notes:
        count = db.execute(
            """
            UPDATE applications
            SET status = %s,
                notes = COALESCE(notes || E'\\n', '') || %s,
                last_status_change = NOW()
            WHERE id = ANY(%s)
            """,
            (new_status, notes, application_ids),
        )
    else:
        count = db.execute(
            """
            UPDATE applications
            SET status = %s,
                last_status_change = NOW()
            WHERE id = ANY(%s)
            """,
            (new_status, application_ids),
        )

    # Report any IDs that didn't match
    if count < len(application_ids):
        found_rows = db.query(
            "SELECT id FROM applications WHERE id = ANY(%s)",
            (application_ids,),
        )
        found_ids = {r["id"] for r in found_rows}
        errors = [
            {"application_id": aid, "error": "Not found"}
            for aid in application_ids
            if aid not in found_ids
        ]

    return jsonify({"updated": count, "errors": errors}), 200


# ---------------------------------------------------------------------------
# GET /api/batch/progress/:batch_id
# ---------------------------------------------------------------------------

@bp.route("/api/batch/progress/<batch_id>", methods=["GET"])
def batch_progress(batch_id):
    """Return progress for a batch operation.

    Stub for future async support — all operations are currently synchronous.
    Returns: { batch_id, status, progress }
    """
    return jsonify({
        "batch_id": batch_id,
        "status": "complete",
        "progress": 100,
    }), 200
