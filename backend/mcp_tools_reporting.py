"""MCP-callable reporting functions (standalone, no Flask context needed)."""

import db
from datetime import datetime, timezone


def get_pipeline_report() -> dict:
    """Pipeline funnel with conversion rates, time-in-stage analysis, and week-over-week trend arrows.

    Returns:
        Dict with funnel breakdown, conversion_rates, avg_days_per_stage, and trends.
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

    # Week-over-week velocity: new apps this week vs last week
    velocity = db.query_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE date_applied >= NOW() - INTERVAL '7 days') AS this_week,
            COUNT(*) FILTER (WHERE date_applied >= NOW() - INTERVAL '14 days'
                             AND date_applied < NOW() - INTERVAL '7 days') AS last_week,
            COUNT(*) FILTER (WHERE last_status_change >= NOW() - INTERVAL '7 days'
                             AND status IN ('Phone Screen','Interview','Technical','Final','Offer')) AS advances_this_week,
            COUNT(*) FILTER (WHERE last_status_change >= NOW() - INTERVAL '14 days'
                             AND last_status_change < NOW() - INTERVAL '7 days'
                             AND status IN ('Phone Screen','Interview','Technical','Final','Offer')) AS advances_last_week
        FROM applications
        """
    )

    def trend_arrow(current, previous):
        if current > previous:
            return "up"
        elif current < previous:
            return "down"
        return "flat"

    trends = {
        "new_apps_velocity": trend_arrow(
            velocity["this_week"] or 0, velocity["last_week"] or 0
        ),
        "pipeline_advances": trend_arrow(
            velocity["advances_this_week"] or 0, velocity["advances_last_week"] or 0
        ),
        "new_apps_this_week": velocity["this_week"] or 0,
        "new_apps_last_week": velocity["last_week"] or 0,
        "advances_this_week": velocity["advances_this_week"] or 0,
        "advances_last_week": velocity["advances_last_week"] or 0,
    }

    # Ghosted rate
    ghosted = totals.get("Ghosted", 0)
    ghosted_rate = round(ghosted / total_apps * 100, 1) if total_apps else 0

    return {
        "funnel": funnel,
        "conversion_rates": conversion_rates,
        "avg_days_per_stage": avg_days_per_stage,
        "trends": trends,
        "ghosted_rate": ghosted_rate,
        "total_apps": total_apps,
    }


def get_campaign_report() -> dict:
    """Full campaign performance dashboard with source effectiveness and time-to-response.

    Returns:
        Dict with stats, source_effectiveness, best_companies, weekly_activity, and time_to_response.
    """
    stats = db.query_one(
        """
        SELECT
            COUNT(*) AS total_apps,
            COUNT(*) FILTER (WHERE status NOT IN ('Applied','Ghosted')) AS got_response,
            COUNT(*) FILTER (WHERE status IN ('Interview','Technical','Final','Offer')) AS reached_interview,
            COUNT(*) FILTER (WHERE status = 'Offer') AS offers,
            COUNT(*) FILTER (WHERE status = 'Ghosted') AS ghosted,
            COUNT(*) FILTER (WHERE status = 'Rejected') AS rejected,
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
    stats["ghosted_rate"] = round((stats["ghosted"] or 0) / total * 100, 1) if total else 0
    stats["rejection_rate"] = round((stats["rejected"] or 0) / total * 100, 1) if total else 0

    # Source effectiveness: which job boards produce interviews
    source_eff = db.query(
        """
        SELECT source,
               total_apps,
               got_response,
               response_rate_pct,
               got_interview,
               interview_rate_pct
        FROM source_effectiveness
        ORDER BY interview_rate_pct DESC NULLS LAST
        LIMIT 10
        """
    )

    # Time-to-response by company (days from applied to first status change)
    time_to_response = db.query(
        """
        SELECT company_name,
               ROUND(AVG(EXTRACT(EPOCH FROM (
                   COALESCE(last_status_change, updated_at) - created_at
               )) / 86400)::numeric, 1) AS avg_days_to_response,
               COUNT(*) AS app_count,
               MAX(status) AS latest_status
        FROM applications
        WHERE status NOT IN ('Applied')
          AND last_status_change IS NOT NULL
        GROUP BY company_name
        HAVING COUNT(*) >= 1
        ORDER BY avg_days_to_response ASC
        LIMIT 15
        """
    )

    # Ghosted rate trend: last 30 days vs prior 30 days
    ghosted_trend = db.query_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'Ghosted'
                             AND created_at >= NOW() - INTERVAL '30 days') AS ghosted_recent,
            COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') AS total_recent,
            COUNT(*) FILTER (WHERE status = 'Ghosted'
                             AND created_at >= NOW() - INTERVAL '60 days'
                             AND created_at < NOW() - INTERVAL '30 days') AS ghosted_prior,
            COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '60 days'
                             AND created_at < NOW() - INTERVAL '30 days') AS total_prior
        FROM applications
        """
    )

    recent_total = ghosted_trend["total_recent"] or 0
    prior_total = ghosted_trend["total_prior"] or 0
    ghosted_trend_data = {
        "recent_30d_ghosted_rate": round(
            (ghosted_trend["ghosted_recent"] or 0) / recent_total * 100, 1
        ) if recent_total else 0,
        "prior_30d_ghosted_rate": round(
            (ghosted_trend["ghosted_prior"] or 0) / prior_total * 100, 1
        ) if prior_total else 0,
    }

    # Rejection rate trend
    rejection_trend = db.query_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'Rejected'
                             AND created_at >= NOW() - INTERVAL '30 days') AS rejected_recent,
            COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') AS total_recent,
            COUNT(*) FILTER (WHERE status = 'Rejected'
                             AND created_at >= NOW() - INTERVAL '60 days'
                             AND created_at < NOW() - INTERVAL '30 days') AS rejected_prior,
            COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '60 days'
                             AND created_at < NOW() - INTERVAL '30 days') AS total_prior
        FROM applications
        """
    )
    rej_recent_total = rejection_trend["total_recent"] or 0
    rej_prior_total = rejection_trend["total_prior"] or 0
    rejection_trend_data = {
        "recent_30d_rejection_rate": round(
            (rejection_trend["rejected_recent"] or 0) / rej_recent_total * 100, 1
        ) if rej_recent_total else 0,
        "prior_30d_rejection_rate": round(
            (rejection_trend["rejected_prior"] or 0) / rej_prior_total * 100, 1
        ) if rej_prior_total else 0,
    }

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

    # Monthly/weekly activity heatmap
    weekly = db.query(
        """
        SELECT DATE_TRUNC('week', date_applied)::date::text AS week_start,
               COUNT(*) AS apps,
               COUNT(*) FILTER (WHERE status NOT IN ('Applied','Ghosted')) AS got_response,
               COUNT(*) FILTER (WHERE status IN ('Interview','Technical','Final','Offer')) AS got_interview
        FROM applications
        WHERE date_applied IS NOT NULL
        GROUP BY DATE_TRUNC('week', date_applied)
        ORDER BY DATE_TRUNC('week', date_applied)
        """
    )

    monthly = db.query(
        """
        SELECT TO_CHAR(DATE_TRUNC('month', date_applied), 'YYYY-MM') AS month,
               COUNT(*) AS apps,
               COUNT(*) FILTER (WHERE status NOT IN ('Applied','Ghosted')) AS responses,
               COUNT(*) FILTER (WHERE status IN ('Interview','Technical','Final','Offer')) AS interviews,
               COUNT(*) FILTER (WHERE status = 'Ghosted') AS ghosted,
               COUNT(*) FILTER (WHERE status = 'Rejected') AS rejected,
               COUNT(*) FILTER (WHERE status = 'Offer') AS offers
        FROM applications
        WHERE date_applied IS NOT NULL
        GROUP BY DATE_TRUNC('month', date_applied)
        ORDER BY DATE_TRUNC('month', date_applied)
        """
    )

    return {
        "stats": stats,
        "source_effectiveness": source_eff,
        "time_to_response": time_to_response,
        "ghosted_trend": ghosted_trend_data,
        "rejection_trend": rejection_trend_data,
        "best_companies": best_companies,
        "weekly_activity": weekly,
        "monthly_activity": monthly,
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
    """Weekly rollup: last 7 days activity with full metrics vs previous 7 days.

    Returns:
        Dict with period, this_week, last_week, deltas, conversion_rates, and by_status.
    """
    # Applications this week vs last week
    this_week = db.query_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE date_applied >= NOW() - INTERVAL '7 days') AS new_apps,
            COUNT(*) FILTER (WHERE status = 'Offer'
                             AND last_status_change >= NOW() - INTERVAL '7 days') AS offers,
            COUNT(*) FILTER (WHERE last_status_change >= NOW() - INTERVAL '7 days'
                             AND status IN ('Phone Screen','Interview','Technical','Final')) AS advances
        FROM applications
        """
    )

    last_week = db.query_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE date_applied >= NOW() - INTERVAL '14 days'
                             AND date_applied < NOW() - INTERVAL '7 days') AS new_apps,
            COUNT(*) FILTER (WHERE status = 'Offer'
                             AND last_status_change >= NOW() - INTERVAL '14 days'
                             AND last_status_change < NOW() - INTERVAL '7 days') AS offers,
            COUNT(*) FILTER (WHERE last_status_change >= NOW() - INTERVAL '14 days'
                             AND last_status_change < NOW() - INTERVAL '7 days'
                             AND status IN ('Phone Screen','Interview','Technical','Final')) AS advances
        FROM applications
        """
    )

    # Interviews
    tw_interviews = db.query_one(
        "SELECT COUNT(*) AS c FROM interviews WHERE date >= NOW() - INTERVAL '7 days'"
    )
    lw_interviews = db.query_one(
        "SELECT COUNT(*) AS c FROM interviews WHERE date >= NOW() - INTERVAL '14 days' AND date < NOW() - INTERVAL '7 days'"
    )

    # Networking touchpoints this week
    tw_networking = db.query_one(
        "SELECT COUNT(*) AS c FROM touchpoints WHERE logged_at >= NOW() - INTERVAL '7 days'"
    )
    lw_networking = db.query_one(
        "SELECT COUNT(*) AS c FROM touchpoints WHERE logged_at >= NOW() - INTERVAL '14 days' AND logged_at < NOW() - INTERVAL '7 days'"
    )

    # New contacts this week
    tw_new_contacts = db.query_one(
        "SELECT COUNT(*) AS c FROM contacts WHERE created_at >= NOW() - INTERVAL '7 days'"
    )
    lw_new_contacts = db.query_one(
        "SELECT COUNT(*) AS c FROM contacts WHERE created_at >= NOW() - INTERVAL '14 days' AND created_at < NOW() - INTERVAL '7 days'"
    )

    # New emails (recruiter responses) this week
    tw_emails = db.query_one(
        """
        SELECT COUNT(*) AS c FROM emails
        WHERE date >= NOW() - INTERVAL '7 days'
          AND category IN ('recruiter', 'application_update', 'interview_request')
        """
    )
    lw_emails = db.query_one(
        """
        SELECT COUNT(*) AS c FROM emails
        WHERE date >= NOW() - INTERVAL '14 days'
          AND date < NOW() - INTERVAL '7 days'
          AND category IN ('recruiter', 'application_update', 'interview_request')
        """
    )

    # Outreach messages
    tw_outreach = db.query_one(
        "SELECT COUNT(*) AS c FROM outreach_messages WHERE direction = 'outbound' AND created_at >= NOW() - INTERVAL '7 days'"
    )
    lw_outreach = db.query_one(
        "SELECT COUNT(*) AS c FROM outreach_messages WHERE direction = 'outbound' AND created_at >= NOW() - INTERVAL '14 days' AND created_at < NOW() - INTERVAL '7 days'"
    )

    # Materials generated
    tw_materials = db.query_one(
        "SELECT COUNT(*) AS c FROM generated_materials WHERE generated_at >= NOW() - INTERVAL '7 days'"
    )
    lw_materials = db.query_one(
        "SELECT COUNT(*) AS c FROM generated_materials WHERE generated_at >= NOW() - INTERVAL '14 days' AND generated_at < NOW() - INTERVAL '7 days'"
    )

    # Status breakdown for this week's applications
    status_breakdown = db.query(
        """
        SELECT status, COUNT(*) AS count
        FROM applications
        WHERE date_applied >= NOW() - INTERVAL '7 days'
        GROUP BY status
        ORDER BY count DESC
        """
    )

    # Total pipeline snapshot
    total_active = db.query_one(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'Applied') AS applied,
            COUNT(*) FILTER (WHERE status IN ('Phone Screen','Interview','Technical','Final')) AS in_progress,
            COUNT(*) FILTER (WHERE status = 'Offer') AS offer,
            COUNT(*) FILTER (WHERE status = 'Ghosted') AS ghosted,
            COUNT(*) FILTER (WHERE status = 'Rejected') AS rejected
        FROM applications
        """
    )

    # Conversion rates (all time)
    total = total_active["total"] or 0
    in_progress = total_active["in_progress"] or 0
    offers = total_active["offer"] or 0
    tw_apps = this_week["new_apps"] or 0
    tw_advances = this_week["advances"] or 0

    conversion_rates = {
        "apps_to_interview_alltime": round(in_progress / total * 100, 1) if total else 0,
        "interviews_to_offer_alltime": round(offers / in_progress * 100, 1) if in_progress else 0,
        "overall_offer_rate": round(offers / total * 100, 1) if total else 0,
        "this_week_advance_rate": round(tw_advances / tw_apps * 100, 1) if tw_apps else 0,
    }

    tw = {
        "new_apps": this_week["new_apps"] or 0,
        "pipeline_advances": this_week["advances"] or 0,
        "interviews": tw_interviews["c"] or 0,
        "offers": this_week["offers"] or 0,
        "networking_touches": tw_networking["c"] or 0,
        "new_contacts": tw_new_contacts["c"] or 0,
        "recruiter_emails": tw_emails["c"] or 0,
        "outreach_sent": tw_outreach["c"] or 0,
        "materials_generated": tw_materials["c"] or 0,
    }

    lw = {
        "new_apps": last_week["new_apps"] or 0,
        "pipeline_advances": last_week["advances"] or 0,
        "interviews": lw_interviews["c"] or 0,
        "offers": last_week["offers"] or 0,
        "networking_touches": lw_networking["c"] or 0,
        "new_contacts": lw_new_contacts["c"] or 0,
        "recruiter_emails": lw_emails["c"] or 0,
        "outreach_sent": lw_outreach["c"] or 0,
        "materials_generated": lw_materials["c"] or 0,
    }

    deltas = {k: tw[k] - lw[k] for k in tw}

    return {
        "period": "last_7_days",
        "this_week": tw,
        "last_week": lw,
        "deltas": deltas,
        "by_status": status_breakdown,
        "pipeline_snapshot": total_active,
        "conversion_rates": conversion_rates,
    }


def generate_strategy_recommendations(rollup: dict, pipeline: dict) -> list:
    """Generate action-item recommendations based on weekly data patterns.

    Args:
        rollup: Output from get_weekly_rollup()
        pipeline: Output from get_pipeline_report()

    Returns:
        List of recommendation dicts with {priority, category, action, reason}.
    """
    recommendations = []
    tw = rollup.get("this_week", {})
    snapshot = rollup.get("pipeline_snapshot", {})
    conversion = rollup.get("conversion_rates", {})
    trends = pipeline.get("trends", {})
    ghosted_rate = pipeline.get("ghosted_rate", 0)

    # No interviews in last 14 days
    lw = rollup.get("last_week", {})
    if tw.get("interviews", 0) == 0 and lw.get("interviews", 0) == 0:
        recommendations.append({
            "priority": "high",
            "category": "interview_prep",
            "action": "No interviews in 2 weeks — schedule mock interview sessions",
            "reason": "Stagnant pipeline suggests resume or outreach may need refresh",
        })

    # Low application volume this week
    if tw.get("new_apps", 0) < 3:
        recommendations.append({
            "priority": "medium",
            "category": "application_volume",
            "action": "Increase application volume — target 5-10 applications per week",
            "reason": f"Only {tw.get('new_apps', 0)} apps submitted this week",
        })

    # High ghosted rate
    if ghosted_rate > 50:
        recommendations.append({
            "priority": "high",
            "category": "follow_up",
            "action": "Set up 7-day follow-up cadence for all active applications",
            "reason": f"Ghosted rate is {ghosted_rate}% — proactive follow-up can recover 15-20% of ghosted apps",
        })
    elif ghosted_rate > 30:
        recommendations.append({
            "priority": "medium",
            "category": "follow_up",
            "action": "Review ghosted applications and send one follow-up email each",
            "reason": f"Ghosted rate is {ghosted_rate}% — consider a single polite check-in",
        })

    # Interviews but no offers (interview-to-offer rate is 0 with interviews existing)
    total_in_progress = snapshot.get("in_progress", 0)
    total_offers = snapshot.get("offer", 0)
    if total_in_progress > 3 and total_offers == 0:
        recommendations.append({
            "priority": "high",
            "category": "interview_skills",
            "action": "Focus on interview performance — practice mock interviews or debrief recent attempts",
            "reason": f"{total_in_progress} interviews reached but 0 offers — closing rate needs work",
        })

    # Velocity dropping
    if trends.get("new_apps_velocity") == "down" and tw.get("new_apps", 0) < lw.get("new_apps", 1):
        recommendations.append({
            "priority": "medium",
            "category": "search_breadth",
            "action": "Broaden search criteria — add adjacent roles or expand target geographies",
            "reason": "Application velocity is declining week-over-week",
        })

    # No networking activity
    if tw.get("networking_touches", 0) == 0 and lw.get("networking_touches", 0) == 0:
        recommendations.append({
            "priority": "medium",
            "category": "networking",
            "action": "Log at least 3 networking touchpoints this week — coffee chats, LinkedIn messages, referral asks",
            "reason": "No networking activity in 2 weeks. Warm referrals convert 4x better than cold apps.",
        })

    # No outreach
    if tw.get("outreach_sent", 0) == 0:
        recommendations.append({
            "priority": "low",
            "category": "outreach",
            "action": "Send 3-5 outreach messages to contacts at target companies",
            "reason": "No outbound messages sent this week",
        })

    # Pipeline stale check — if most apps are in 'Applied' with no movement
    total = snapshot.get("total", 0)
    applied_only = snapshot.get("applied", 0)
    if total > 5 and applied_only / total > 0.7:
        recommendations.append({
            "priority": "medium",
            "category": "pipeline_health",
            "action": "Review and refresh resume targeting — too many apps stuck in Applied",
            "reason": f"{round(applied_only / total * 100)}% of pipeline hasn't moved past initial application",
        })

    # Strong week — positive reinforcement
    if (tw.get("new_apps", 0) >= 5 and
            tw.get("networking_touches", 0) >= 2 and
            tw.get("interviews", 0) >= 1):
        recommendations.append({
            "priority": "info",
            "category": "momentum",
            "action": "Strong week — maintain this pace and track which sources produced interviews",
            "reason": "Above-average activity across applications, networking, and interviews",
        })

    # Sort: high > medium > low > info
    priority_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    recommendations.sort(key=lambda r: priority_order.get(r["priority"], 99))

    return recommendations
