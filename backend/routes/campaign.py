"""Routes for Campaign Management (close-out, conversion, analytics, onboarding)."""

import json
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("campaign", __name__)


# ---------------------------------------------------------------------------
# Saved Job -> Application Conversion
# ---------------------------------------------------------------------------

@bp.route("/api/saved-jobs/<int:job_id>/convert", methods=["POST"])
def convert_saved_job(job_id):
    """Convert a saved job into an application.

    Creates an application from saved_job data, links them,
    and updates saved_job status to 'applied'.
    """
    job = db.query_one("SELECT * FROM saved_jobs WHERE id = %s", (job_id,))
    if not job:
        return jsonify({"error": "Saved job not found"}), 404

    # Check if already converted
    existing = db.query_one(
        "SELECT id FROM applications WHERE saved_job_id = %s", (job_id,)
    )
    if existing:
        return jsonify({"error": "Already converted", "application_id": existing["id"]}), 409

    # Check for gap analysis linked to this saved job
    gap = db.query_one(
        "SELECT id FROM gap_analyses WHERE saved_job_id = %s ORDER BY created_at DESC LIMIT 1",
        (job_id,),
    )

    app = db.execute_returning(
        """
        INSERT INTO applications
            (company_name, company_id, role, source, status, jd_text, jd_url,
             saved_job_id, gap_analysis_id, date_applied, last_status_change)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        RETURNING *
        """,
        (
            job.get("company"),
            job.get("company_id"),
            job.get("title"),
            job.get("source", "saved_job"),
            "Applied",
            job.get("jd_text"),
            job.get("jd_url") or job.get("url"),
            job_id,
            gap["id"] if gap else None,
        ),
    )

    # Update saved job status
    db.execute(
        "UPDATE saved_jobs SET status = 'applied' WHERE id = %s",
        (job_id,),
    )

    return jsonify(app), 201


# ---------------------------------------------------------------------------
# Campaign Close-Out
# ---------------------------------------------------------------------------

@bp.route("/api/campaign/close-out", methods=["POST"])
def close_out_campaign():
    """Execute campaign close-out workflow.

    Body: { accepted_application_id: int }

    Marks the accepted application, withdraws all others,
    generates withdrawal emails and thank-you drafts.
    """
    data = request.get_json(force=True)
    accepted_id = data.get("accepted_application_id")
    if not accepted_id:
        return jsonify({"error": "accepted_application_id is required"}), 400

    # Verify and update accepted application
    accepted = db.execute_returning(
        """
        UPDATE applications
        SET status = 'Accepted', last_status_change = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (accepted_id,),
    )
    if not accepted:
        return jsonify({"error": "Application not found"}), 404

    # Pull candidate name
    header = db.query_one("SELECT full_name FROM resume_header ORDER BY id LIMIT 1")
    candidate_name = header["full_name"] if header else "Candidate"

    # Withdraw all other active applications
    terminal = ("Rejected", "Withdrawn", "Ghosted", "Accepted")
    placeholders = ",".join(["%s"] * len(terminal))
    active_apps = db.query(
        f"""
        SELECT * FROM applications
        WHERE id != %s AND status NOT IN ({placeholders})
        """,
        [accepted_id] + list(terminal),
    )

    withdrawn = []
    for app in active_apps:
        db.execute(
            "UPDATE applications SET status = 'Withdrawn', last_status_change = NOW() WHERE id = %s",
            (app["id"],),
        )

        email_draft = None
        contact_email = app.get("contact_email")
        if contact_email:
            company = app.get("company_name", "[Company]")
            role = app.get("role", "[Role]")
            email_draft = (
                f"Dear Hiring Team,\n\n"
                f"Thank you for considering me for the {role} position at {company}. "
                f"After careful consideration, I have decided to pursue another opportunity "
                f"that closely aligns with my current goals.\n\n"
                f"I genuinely enjoyed learning about {company} and hope we can stay in touch "
                f"for future opportunities.\n\n"
                f"Best regards,\n{candidate_name}"
            )

        withdrawn.append({
            "application": app,
            "email_draft": email_draft,
        })

    # Generate thank-you drafts for contacts linked to accepted company
    thank_yous = []
    accepted_company = accepted.get("company_name")
    if accepted_company:
        helpers = db.query(
            "SELECT * FROM contacts WHERE company ILIKE %s",
            (accepted_company,),
        )
        for contact in helpers:
            name = contact.get("name") or "there"
            draft = (
                f"Hi {name},\n\n"
                f"I wanted to let you know that I have accepted a position at {accepted_company}. "
                f"Thank you for your support throughout this process... it truly made a difference.\n\n"
                f"I look forward to working together.\n\n"
                f"Best,\n{candidate_name}"
            )
            thank_yous.append({
                "contact_id": contact["id"],
                "contact_name": name,
                "draft": draft,
            })

    # Final analytics snapshot — capture campaign stats at close-out
    status_counts = db.query(
        "SELECT status, COUNT(*) as count FROM applications GROUP BY status"
    )
    total_apps = sum(r["count"] for r in status_counts) if status_counts else 0
    status_map = {r["status"]: r["count"] for r in status_counts} if status_counts else {}

    offers_count = db.query_one(
        "SELECT COUNT(*) as cnt FROM applications WHERE status IN ('Offer', 'Accepted')"
    )
    interviews_count = db.query_one(
        "SELECT COUNT(*) as cnt FROM applications WHERE status IN ('Interview', 'Phone Screen', 'Final Round')"
    )

    response_rate = None
    offer_rate = None
    if total_apps > 0:
        responded = sum(
            status_map.get(s, 0)
            for s in ("Interview", "Phone Screen", "Final Round", "Offer", "Accepted", "Rejected")
        )
        response_rate = round(responded / total_apps * 100, 1)
        offer_count = (offers_count["cnt"] if offers_count else 0)
        offer_rate = round(offer_count / total_apps * 100, 1)

    first_app = db.query_one(
        "SELECT MIN(applied_date) as first_date FROM applications"
    )
    campaign_snapshot = {
        "total_applications": total_apps,
        "status_breakdown": status_map,
        "response_rate_pct": response_rate,
        "offer_rate_pct": offer_rate,
        "interviews_reached": interviews_count["cnt"] if interviews_count else 0,
        "offers_received": offers_count["cnt"] if offers_count else 0,
        "withdrawn_this_close_out": len(withdrawn),
        "campaign_start_date": str(first_app["first_date"]) if first_app and first_app.get("first_date") else None,
        "close_out_date": accepted.get("last_status_change"),
        "accepted_company": accepted.get("company_name"),
        "accepted_role": accepted.get("role"),
    }

    return jsonify({
        "accepted": accepted,
        "withdrawn": withdrawn,
        "thank_yous": thank_yous,
        "campaign_snapshot": campaign_snapshot,
    }), 200


# ---------------------------------------------------------------------------
# Campaign Summary / Analytics
# ---------------------------------------------------------------------------

@bp.route("/api/campaign/summary", methods=["GET"])
def campaign_summary():
    """Campaign analytics summary.

    Returns total applications, status breakdown, response rate,
    offer rate, timeline, and top sources.
    """
    # Total and by-status counts
    status_rows = db.query(
        "SELECT status, COUNT(*) as count FROM applications GROUP BY status ORDER BY count DESC"
    )
    total = sum(r["count"] for r in status_rows)
    by_status = {r["status"]: r["count"] for r in status_rows}

    # Interview count (applications that reached interview stage)
    interview_count = db.query_one(
        """
        SELECT COUNT(DISTINCT application_id) as count
        FROM interviews
        """
    )
    interviews = interview_count["count"] if interview_count else 0

    # Offer count
    offer_count = db.query_one("SELECT COUNT(*) as count FROM offers")
    offers = offer_count["count"] if offer_count else 0

    # Response rate & offer rate
    response_rate = round(interviews / total * 100, 1) if total > 0 else 0
    offer_rate = round(offers / total * 100, 1) if total > 0 else 0

    # Timeline
    timeline = db.query_one(
        """
        SELECT MIN(date_applied) as first_app,
               MAX(date_applied) as last_app
        FROM applications
        """
    )

    # Top sources by success rate (interviews / apps per source)
    source_rows = db.query(
        """
        SELECT source,
               COUNT(*) as total,
               COUNT(*) FILTER (WHERE status IN ('Interview', 'Offer', 'Accepted')) as successes
        FROM applications
        WHERE source IS NOT NULL
        GROUP BY source
        ORDER BY successes DESC, total DESC
        """
    )
    top_sources = []
    for s in source_rows:
        rate = round(s["successes"] / s["total"] * 100, 1) if s["total"] > 0 else 0
        top_sources.append({
            "source": s["source"],
            "total": s["total"],
            "successes": s["successes"],
            "success_rate": rate,
        })

    return jsonify({
        "total_applications": total,
        "by_status": by_status,
        "interviews": interviews,
        "offers": offers,
        "response_rate_pct": response_rate,
        "offer_rate_pct": offer_rate,
        "timeline": {
            "first_application": timeline["first_app"] if timeline else None,
            "last_application": timeline["last_app"] if timeline else None,
        },
        "top_sources": top_sources,
    }), 200


# ---------------------------------------------------------------------------
# Campaign Archive
# ---------------------------------------------------------------------------

@bp.route("/api/campaign/archive", methods=["POST"])
def archive_campaign():
    """Snapshot current campaign stats into a generated_material."""
    # Build snapshot by calling summary logic inline
    status_rows = db.query(
        "SELECT status, COUNT(*) as count FROM applications GROUP BY status"
    )
    total = sum(r["count"] for r in status_rows)
    by_status = {r["status"]: r["count"] for r in status_rows}

    offer_count = db.query_one("SELECT COUNT(*) as count FROM offers")
    offers = offer_count["count"] if offer_count else 0

    interview_count = db.query_one(
        "SELECT COUNT(DISTINCT application_id) as count FROM interviews"
    )
    interviews = interview_count["count"] if interview_count else 0

    snapshot = {
        "total_applications": total,
        "by_status": by_status,
        "interviews": interviews,
        "offers": offers,
        "response_rate_pct": round(interviews / total * 100, 1) if total > 0 else 0,
        "offer_rate_pct": round(offers / total * 100, 1) if total > 0 else 0,
    }

    row = db.execute_returning(
        """
        INSERT INTO generated_materials
            (type, content, content_format, status)
        VALUES (%s, %s, %s, %s)
        RETURNING *
        """,
        (
            "campaign_snapshot",
            json.dumps(snapshot),
            "json",
            "draft",
        ),
    )
    return jsonify(row), 201


# ---------------------------------------------------------------------------
# Onboarding — Voice Sample Analysis
# ---------------------------------------------------------------------------

@bp.route("/api/onboarding/voice-sample", methods=["POST"])
def analyze_voice_sample():
    """Analyze writing samples to detect voice patterns.

    Body: { writing_samples: [str] }
    Returns detected patterns and suggested rules.
    """
    data = request.get_json(force=True)
    samples = data.get("writing_samples")
    if not samples or not isinstance(samples, list):
        return jsonify({"error": "writing_samples array is required"}), 400

    # Analyze patterns across all samples
    all_words = []
    sentence_lengths = []
    for sample in samples:
        words = sample.split()
        all_words.extend(words)
        # Split on sentence-ending punctuation
        sentences = [s.strip() for s in sample.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        sentence_lengths.extend(len(s.split()) for s in sentences)

    # Word frequency (top 20 non-trivial words)
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "it", "its",
        "this", "that", "these", "those", "i", "we", "you", "he", "she",
        "they", "me", "us", "him", "her", "them", "my", "our", "your",
        "not", "no", "so", "if", "as",
    }
    word_freq = {}
    for w in all_words:
        cleaned = w.lower().strip(".,!?;:\"'()-")
        if cleaned and cleaned not in stop_words and len(cleaned) > 2:
            word_freq[cleaned] = word_freq.get(cleaned, 0) + 1

    top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:20]

    # Tone markers
    avg_sentence_len = round(sum(sentence_lengths) / len(sentence_lengths), 1) if sentence_lengths else 0
    uses_contractions = any("'" in w for w in all_words)
    uses_ellipses = any("..." in s for s in samples)
    uses_em_dashes = any("—" in s or " - " in s for s in samples)

    detected_patterns = {
        "avg_sentence_length": avg_sentence_len,
        "top_words": [{"word": w, "count": c} for w, c in top_words],
        "uses_contractions": uses_contractions,
        "uses_ellipses": uses_ellipses,
        "uses_em_dashes": uses_em_dashes,
        "total_words_analyzed": len(all_words),
        "total_sentences": len(sentence_lengths),
    }

    # Generate suggested rules
    suggested_rules = []
    if avg_sentence_len < 15:
        suggested_rules.append("Keep sentences short and punchy (under 15 words average)")
    elif avg_sentence_len > 25:
        suggested_rules.append("Use longer, more detailed sentences when explaining concepts")

    if uses_contractions:
        suggested_rules.append("Use contractions for a conversational tone")
    else:
        suggested_rules.append("Avoid contractions for a more formal tone")

    if uses_ellipses:
        suggested_rules.append("Use ellipses for trailing thoughts and pauses")

    if uses_em_dashes:
        suggested_rules.append("Use em dashes or hyphens for parenthetical asides")

    # Suggest based on frequent words
    if top_words:
        power_words = [w for w, c in top_words[:10] if c >= 3]
        if power_words:
            suggested_rules.append(f"Signature vocabulary: {', '.join(power_words)}")

    return jsonify({
        "detected_patterns": detected_patterns,
        "suggested_rules": suggested_rules,
        "sample_count": len(samples),
    }), 200


# ---------------------------------------------------------------------------
# Onboarding — Initial Recipe
# ---------------------------------------------------------------------------

@bp.route("/api/onboarding/initial-recipe", methods=["POST"])
def initial_recipe():
    """Create an initial resume recipe outline from career data.

    Body: { role_type: str }
    Pulls career history, bullets, and summary variants for the role type.
    """
    data = request.get_json(force=True)
    role_type = data.get("role_type")
    if not role_type:
        return jsonify({"error": "role_type is required"}), 400

    # Pull career history
    career = db.query(
        "SELECT * FROM career_history ORDER BY start_date DESC"
    )

    # Pull top bullets
    bullets = db.query(
        "SELECT * FROM bullets ORDER BY id DESC LIMIT 20"
    )

    # Pull summary variant for role type
    summary = db.query_one(
        "SELECT * FROM summary_variants WHERE role_type ILIKE %s LIMIT 1",
        (f"%{role_type}%",),
    )

    # Pull skills
    skills = db.query("SELECT * FROM skills ORDER BY proficiency DESC NULLS LAST")

    # Assemble recipe outline
    recipe = {
        "role_type": role_type,
        "summary": summary.get("content") if summary else None,
        "experience": [
            {
                "company": c.get("company"),
                "title": c.get("title"),
                "start_date": str(c.get("start_date")) if c.get("start_date") else None,
                "end_date": str(c.get("end_date")) if c.get("end_date") else None,
            }
            for c in (career or [])
        ],
        "bullet_count": len(bullets) if bullets else 0,
        "top_bullets": [
            b.get("text") for b in (bullets or [])[:5]
        ],
        "skills": [s.get("name") for s in (skills or [])[:15]],
    }

    return jsonify({
        "recipe_outline": recipe,
        "career_entries": len(career) if career else 0,
        "available_bullets": len(bullets) if bullets else 0,
        "summary_found": summary is not None,
    }), 200


# ---------------------------------------------------------------------------
# GET /api/campaign/close-out-preview — Preview close-out actions
# ---------------------------------------------------------------------------

@bp.route("/api/campaign/close-out-preview", methods=["GET"])
def close_out_preview():
    """Preview what campaign close-out would do.

    Lists applications to withdraw, emails to draft, contacts to notify.
    Does NOT actually perform any actions.
    """
    # Active applications that would be withdrawn
    active_apps = db.query(
        """
        SELECT id, company_name, role, status, date_applied, last_status_change
        FROM applications
        WHERE status NOT IN ('Rejected', 'Ghosted', 'Withdrawn', 'Offer', 'Accepted')
        ORDER BY date_applied DESC
        """
    ) or []

    # Pending interviews that would be cancelled
    pending_interviews = db.query(
        """
        SELECT i.id, i.date, i.type, a.company_name, a.role
        FROM interviews i
        JOIN applications a ON a.id = i.application_id
        WHERE i.date >= CURRENT_DATE AND i.outcome = 'pending'
        ORDER BY i.date ASC
        """
    ) or []

    # Draft outreach that would be discarded
    draft_outreach = db.query(
        """
        SELECT id, message_type, subject, status
        FROM outreach_messages
        WHERE status = 'draft'
        """
    ) or []

    # Contacts to potentially notify (strong/warm relationships with active apps)
    contacts_to_notify = db.query(
        """
        SELECT DISTINCT c.id, c.name, c.company, c.relationship_strength
        FROM contacts c
        JOIN applications a ON a.company_name ILIKE '%%' || c.company || '%%'
        WHERE a.status NOT IN ('Rejected', 'Ghosted', 'Withdrawn', 'Offer', 'Accepted')
          AND c.relationship_strength IN ('strong', 'warm')
        LIMIT 20
        """
    ) or []

    # Thank-you emails to draft for completed interviews
    thank_you_needed = db.query(
        """
        SELECT i.id AS interview_id, i.date, i.type, a.company_name, a.role
        FROM interviews i
        JOIN applications a ON a.id = i.application_id
        WHERE i.thank_you_sent = false
          AND i.date < CURRENT_DATE
          AND i.outcome != 'cancelled'
        ORDER BY i.date DESC
        """
    ) or []

    return jsonify({
        "applications_to_withdraw": active_apps,
        "interviews_to_cancel": pending_interviews,
        "drafts_to_discard": draft_outreach,
        "contacts_to_notify": contacts_to_notify,
        "thank_yous_needed": thank_you_needed,
        "summary": {
            "withdraw_count": len(active_apps),
            "cancel_interviews": len(pending_interviews),
            "discard_drafts": len(draft_outreach),
            "notify_contacts": len(contacts_to_notify),
            "thank_yous_pending": len(thank_you_needed),
        },
    }), 200


# ---------------------------------------------------------------------------
# POST /api/campaign/archive — Archive campaign data
# ---------------------------------------------------------------------------

@bp.route("/api/campaign/archive", methods=["POST"])
def archive_full_campaign():
    """Archive completed campaign data for historical reference.

    Creates a comprehensive snapshot in generated_materials with all campaign stats,
    timeline, top outcomes, and lessons learned.

    Body (JSON, optional):
        notes: additional notes to include in the archive
        campaign_name: name for this campaign (default: auto-generated)
    """
    data = request.get_json(force=True) if request.data else {}
    notes = data.get("notes", "")
    campaign_name = data.get("campaign_name", "")

    # Gather comprehensive stats
    app_stats = db.query(
        "SELECT status, COUNT(*) AS count FROM applications GROUP BY status ORDER BY count DESC"
    ) or []
    total_apps = sum(r["count"] for r in app_stats)
    by_status = {r["status"]: r["count"] for r in app_stats}

    # Interview stats
    interview_stats = db.query_one(
        """
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE outcome = 'pass') AS passed,
               COUNT(*) FILTER (WHERE outcome = 'fail') AS failed,
               COUNT(DISTINCT application_id) AS unique_apps
        FROM interviews
        """
    ) or {}

    # Offer stats
    offers = db.query(
        """
        SELECT o.id, o.base_salary, o.total_comp, o.status,
               a.company_name, a.role
        FROM offers o
        JOIN applications a ON a.id = o.application_id
        ORDER BY o.created_at DESC
        """
    ) or []

    # Timeline
    first_app = db.query_one(
        "SELECT MIN(date_applied) AS first FROM applications"
    )
    last_app = db.query_one(
        "SELECT MAX(date_applied) AS last FROM applications"
    )

    # Materials generated
    materials_count = db.query_one(
        "SELECT COUNT(*) AS cnt FROM generated_materials"
    )

    # Outreach stats
    outreach_count = db.query_one(
        """
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE status = 'sent') AS sent,
               COUNT(*) FILTER (WHERE outcome = 'replied') AS replied
        FROM outreach_messages
        """
    ) or {}

    if not campaign_name:
        start = str(first_app["first"])[:10] if first_app and first_app.get("first") else "unknown"
        campaign_name = f"Campaign {start}"

    archive = {
        "campaign_name": campaign_name,
        "notes": notes,
        "timeline": {
            "first_application": str(first_app["first"]) if first_app and first_app.get("first") else None,
            "last_application": str(last_app["last"]) if last_app and last_app.get("last") else None,
        },
        "applications": {
            "total": total_apps,
            "by_status": by_status,
        },
        "interviews": {
            "total": interview_stats.get("total", 0),
            "passed": interview_stats.get("passed", 0),
            "failed": interview_stats.get("failed", 0),
            "unique_applications": interview_stats.get("unique_apps", 0),
        },
        "offers": [
            {
                "company": o.get("company_name"),
                "role": o.get("role"),
                "base_salary": o.get("base_salary"),
                "total_comp": o.get("total_comp"),
                "status": o.get("status"),
            }
            for o in offers
        ],
        "outreach": {
            "total": outreach_count.get("total", 0),
            "sent": outreach_count.get("sent", 0),
            "replied": outreach_count.get("replied", 0),
        },
        "materials_generated": materials_count["cnt"] if materials_count else 0,
    }

    row = db.execute_returning(
        """
        INSERT INTO generated_materials
            (type, content, content_format, status)
        VALUES (%s, %s, %s, %s)
        RETURNING *
        """,
        (
            "campaign_archive",
            json.dumps(archive),
            "json",
            "draft",
        ),
    )
    return jsonify({
        "archive": archive,
        "material_id": row["id"] if row else None,
    }), 201
