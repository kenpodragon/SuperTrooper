"""MCP-callable campaign functions (standalone, no Flask context needed)."""

import json
import db
from ai_providers.router import route_inference


def convert_saved_job(saved_job_id: int) -> dict:
    """Convert a saved job into an application.

    Creates an application from saved_job data, links them via saved_job_id,
    and updates the saved job status to 'applied'.

    Args:
        saved_job_id: ID of the saved job to convert.

    Returns:
        The created application dict, or error dict.
    """
    job = db.query_one("SELECT * FROM saved_jobs WHERE id = %s", (saved_job_id,))
    if not job:
        return {"error": "Saved job not found"}

    # Check if already converted
    existing = db.query_one(
        "SELECT id FROM applications WHERE saved_job_id = %s", (saved_job_id,)
    )
    if existing:
        return {"error": "Already converted", "application_id": existing["id"]}

    # Check for gap analysis
    gap = db.query_one(
        "SELECT id FROM gap_analyses WHERE saved_job_id = %s ORDER BY created_at DESC LIMIT 1",
        (saved_job_id,),
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
            saved_job_id,
            gap["id"] if gap else None,
        ),
    )

    db.execute(
        "UPDATE saved_jobs SET status = 'applied' WHERE id = %s",
        (saved_job_id,),
    )

    return app


def close_out_campaign(accepted_application_id: int) -> dict:
    """Execute full campaign close-out.

    Marks the accepted application, withdraws all other active applications,
    generates withdrawal email drafts and thank-you drafts.

    Args:
        accepted_application_id: ID of the application with the accepted offer.

    Returns:
        Dict with accepted app, withdrawn apps with email drafts, and thank-you drafts.
    """
    # Update accepted application
    accepted = db.execute_returning(
        """
        UPDATE applications
        SET status = 'Accepted', last_status_change = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (accepted_application_id,),
    )
    if not accepted:
        return {"error": "Application not found"}

    # Pull candidate name
    header = db.query_one("SELECT full_name FROM resume_header ORDER BY id LIMIT 1")
    candidate_name = header["full_name"] if header else "Candidate"

    # Withdraw active applications
    terminal = ("Rejected", "Withdrawn", "Ghosted", "Accepted")
    placeholders = ",".join(["%s"] * len(terminal))
    active_apps = db.query(
        f"""
        SELECT * FROM applications
        WHERE id != %s AND status NOT IN ({placeholders})
        """,
        [accepted_application_id] + list(terminal),
    )

    withdrawn = []
    for app in active_apps:
        db.execute(
            "UPDATE applications SET status = 'Withdrawn', last_status_change = NOW() WHERE id = %s",
            (app["id"],),
        )

        email_draft = None
        if app.get("contact_email"):
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

        withdrawn.append({"application": app, "email_draft": email_draft})

    # Thank-you drafts for contacts at accepted company
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

    return {
        "accepted": accepted,
        "withdrawn": withdrawn,
        "thank_yous": thank_yous,
    }


def get_campaign_summary() -> dict:
    """Get campaign analytics snapshot.

    Returns:
        Dict with total applications, status breakdown, response/offer rates,
        timeline, and top sources.
    """
    status_rows = db.query(
        "SELECT status, COUNT(*) as count FROM applications GROUP BY status ORDER BY count DESC"
    )
    total = sum(r["count"] for r in status_rows)
    by_status = {r["status"]: r["count"] for r in status_rows}

    interview_count = db.query_one(
        "SELECT COUNT(DISTINCT application_id) as count FROM interviews"
    )
    interviews = interview_count["count"] if interview_count else 0

    offer_count = db.query_one("SELECT COUNT(*) as count FROM offers")
    offers = offer_count["count"] if offer_count else 0

    response_rate = round(interviews / total * 100, 1) if total > 0 else 0
    offer_rate = round(offers / total * 100, 1) if total > 0 else 0

    timeline = db.query_one(
        """
        SELECT MIN(date_applied) as first_app,
               MAX(date_applied) as last_app
        FROM applications
        """
    )

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

    python_result = {
        "total_applications": total,
        "by_status": by_status,
        "interviews": interviews,
        "offers": offers,
        "response_rate_pct": response_rate,
        "offer_rate_pct": offer_rate,
        "timeline": {
            "first_application": str(timeline["first_app"]) if timeline and timeline["first_app"] else None,
            "last_application": str(timeline["last_app"]) if timeline and timeline["last_app"] else None,
        },
        "top_sources": top_sources,
    }

    def _python_campaign(ctx):
        return ctx["r"]

    def _ai_campaign(ctx):
        from ai_providers import get_provider
        provider = get_provider()
        result = provider.analyze_strategy(ctx["r"])
        base = ctx["r"]
        base["ai_insights"] = result.get("insights", [])
        base["ai_recommendations"] = result.get("recommendations", [])
        base["ai_risk_areas"] = result.get("risk_areas", [])
        return base

    return route_inference(
        task="campaign_summary",
        context={"r": python_result},
        python_fallback=_python_campaign,
        ai_handler=_ai_campaign,
    )
