"""MCP-callable reporting functions (standalone, no Flask context needed)."""

import db


def get_pipeline_report() -> dict:
    """Pipeline funnel with conversion rates and time-in-stage analysis.

    Returns:
        Dict with funnel breakdown, conversion_rates, and avg_days_per_stage.
    """
    funnel = db.query("SELECT status, count, pct FROM application_funnel")

    totals = {}
    for row in funnel:
        totals[row["status"]] = row["count"]

    total_apps = sum(totals.values())
    screens = totals.get("Phone Screen", 0)
    interviews = sum(totals.get(s, 0) for s in ("Interview", "Technical", "Final"))
    offers = totals.get("Offer", 0)

    conversion_rates = {
        "applied_to_screen": round(screens / total_apps * 100, 1) if total_apps else 0,
        "screen_to_interview": round(interviews / screens * 100, 1) if screens else 0,
        "interview_to_offer": round(offers / interviews * 100, 1) if interviews else 0,
        "overall_offer_rate": round(offers / total_apps * 100, 1) if total_apps else 0,
    }

    avg_days = db.query(
        """
        SELECT status,
               ROUND(AVG(EXTRACT(EPOCH FROM (
                   COALESCE(last_status_change, updated_at, NOW()) - created_at
               )) / 86400)::numeric, 1) AS avg_days
        FROM applications
        GROUP BY status
        ORDER BY avg_days DESC
        """
    )
    avg_days_per_stage = {row["status"]: float(row["avg_days"] or 0) for row in avg_days}

    return {
        "funnel": funnel,
        "conversion_rates": conversion_rates,
        "avg_days_per_stage": avg_days_per_stage,
    }


def get_campaign_report() -> dict:
    """Full campaign performance dashboard.

    Returns:
        Dict with stats, best_companies, and weekly_activity.
    """
    stats = db.query_one(
        """
        SELECT
            COUNT(*) AS total_apps,
            COUNT(*) FILTER (WHERE status NOT IN ('Applied','Ghosted')) AS got_response,
            COUNT(*) FILTER (WHERE status IN ('Interview','Technical','Final','Offer')) AS reached_interview,
            COUNT(*) FILTER (WHERE status = 'Offer') AS offers,
            MIN(date_applied)::text AS first_app,
            MAX(date_applied)::text AS latest_app,
            COUNT(DISTINCT company_name) AS unique_companies,
            COUNT(DISTINCT source) AS unique_sources
        FROM applications
        """
    )

    total = stats["total_apps"] or 0
    stats["response_rate"] = round((stats["got_response"] or 0) / total * 100, 1) if total else 0
    stats["interview_rate"] = round((stats["reached_interview"] or 0) / total * 100, 1) if total else 0
    stats["offer_rate"] = round((stats["offers"] or 0) / total * 100, 1) if total else 0

    # Best performing companies by furthest stage
    best_companies = db.query(
        """
        SELECT company_name, role, status
        FROM applications
        ORDER BY CASE status
            WHEN 'Offer' THEN 6 WHEN 'Final' THEN 5 WHEN 'Technical' THEN 4
            WHEN 'Interview' THEN 3 WHEN 'Phone Screen' THEN 2 WHEN 'Applied' THEN 1
            ELSE 0 END DESC,
            updated_at DESC
        LIMIT 10
        """
    )

    weekly = db.query(
        """
        SELECT DATE_TRUNC('week', date_applied)::date::text AS week_start,
               COUNT(*) AS apps
        FROM applications
        WHERE date_applied IS NOT NULL
        GROUP BY DATE_TRUNC('week', date_applied)
        ORDER BY DATE_TRUNC('week', date_applied)
        """
    )

    return {
        "stats": stats,
        "best_companies": best_companies,
        "weekly_activity": weekly,
    }


def get_interview_analytics() -> dict:
    """Interview win rates, common questions, feeling distribution.

    Returns:
        Dict with by_type, feeling_distribution, common_questions, lessons_learned.
    """
    by_type = db.query(
        """
        SELECT type,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE outcome = 'pass') AS passed,
               COUNT(*) FILTER (WHERE outcome = 'fail') AS failed,
               ROUND(COUNT(*) FILTER (WHERE outcome = 'pass') * 100.0 / NULLIF(COUNT(*), 0), 1) AS win_rate
        FROM interviews
        GROUP BY type
        ORDER BY win_rate DESC NULLS LAST
        """
    )

    feeling_dist = db.query(
        """
        SELECT overall_feeling, COUNT(*) AS count
        FROM interview_debriefs
        WHERE overall_feeling IS NOT NULL
        GROUP BY overall_feeling
        ORDER BY count DESC
        """
    )

    questions_raw = db.query(
        """
        SELECT questions_asked
        FROM interview_debriefs
        WHERE questions_asked IS NOT NULL
        """
    )
    question_counts = {}
    for row in questions_raw:
        qa = row["questions_asked"]
        if isinstance(qa, list):
            for q in qa:
                q_text = q if isinstance(q, str) else q.get("question", str(q))
                question_counts[q_text] = question_counts.get(q_text, 0) + 1
    common_questions = sorted(question_counts.items(), key=lambda x: -x[1])[:20]
    common_questions = [{"question": q, "count": c} for q, c in common_questions]

    lessons_raw = db.query(
        """
        SELECT lessons_learned
        FROM interview_debriefs
        WHERE lessons_learned IS NOT NULL AND lessons_learned != ''
        """
    )
    lessons = [r["lessons_learned"] for r in lessons_raw]

    return {
        "by_type": by_type,
        "feeling_distribution": feeling_dist,
        "common_questions": common_questions,
        "lessons_learned": lessons,
    }


def get_weekly_rollup() -> dict:
    """Weekly rollup: last 7 days vs previous 7 days.

    Returns:
        Dict with this_week, last_week, and deltas.
    """
    this_week = db.query_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE date_applied >= NOW() - INTERVAL '7 days') AS new_apps,
            COUNT(*) FILTER (WHERE status = 'Offer' AND last_status_change >= NOW() - INTERVAL '7 days') AS offers
        FROM applications
        """
    )

    tw_interviews = db.query_one(
        "SELECT COUNT(*) AS c FROM interviews WHERE date >= NOW() - INTERVAL '7 days'"
    )
    tw_outreach = db.query_one(
        "SELECT COUNT(*) AS c FROM outreach_messages WHERE direction = 'outbound' AND created_at >= NOW() - INTERVAL '7 days'"
    )
    tw_materials = db.query_one(
        "SELECT COUNT(*) AS c FROM generated_materials WHERE generated_at >= NOW() - INTERVAL '7 days'"
    )

    last_week = db.query_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE date_applied >= NOW() - INTERVAL '14 days' AND date_applied < NOW() - INTERVAL '7 days') AS new_apps,
            COUNT(*) FILTER (WHERE status = 'Offer' AND last_status_change >= NOW() - INTERVAL '14 days' AND last_status_change < NOW() - INTERVAL '7 days') AS offers
        FROM applications
        """
    )

    lw_interviews = db.query_one(
        "SELECT COUNT(*) AS c FROM interviews WHERE date >= NOW() - INTERVAL '14 days' AND date < NOW() - INTERVAL '7 days'"
    )
    lw_outreach = db.query_one(
        "SELECT COUNT(*) AS c FROM outreach_messages WHERE direction = 'outbound' AND created_at >= NOW() - INTERVAL '14 days' AND created_at < NOW() - INTERVAL '7 days'"
    )
    lw_materials = db.query_one(
        "SELECT COUNT(*) AS c FROM generated_materials WHERE generated_at >= NOW() - INTERVAL '14 days' AND generated_at < NOW() - INTERVAL '7 days'"
    )

    tw = {
        "new_apps": this_week["new_apps"] or 0,
        "interviews": tw_interviews["c"] or 0,
        "offers": this_week["offers"] or 0,
        "outreach_sent": tw_outreach["c"] or 0,
        "materials_generated": tw_materials["c"] or 0,
    }

    lw = {
        "new_apps": last_week["new_apps"] or 0,
        "interviews": lw_interviews["c"] or 0,
        "offers": last_week["offers"] or 0,
        "outreach_sent": lw_outreach["c"] or 0,
        "materials_generated": lw_materials["c"] or 0,
    }

    deltas = {k: tw[k] - lw[k] for k in tw}

    return {
        "this_week": tw,
        "last_week": lw,
        "deltas": deltas,
    }
