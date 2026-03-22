"""Routes for Analytics & Reporting (Pipeline, Campaign, Interview, Outreach, Materials)."""

import json
from flask import Blueprint, jsonify
import db

bp = Blueprint("reporting", __name__)


# ---------------------------------------------------------------------------
# Pipeline Reporting
# ---------------------------------------------------------------------------

@bp.route("/api/reporting/pipeline", methods=["GET"])
def pipeline_report():
    """Pipeline funnel with conversion rates and time-in-stage analysis."""
    funnel = db.query("SELECT status, count, pct FROM application_funnel")

    # Conversion rates
    totals = {}
    for row in funnel:
        totals[row["status"]] = row["count"]

    total_apps = sum(totals.values())
    screen_statuses = ("Phone Screen",)
    interview_statuses = ("Interview", "Technical", "Final")
    offer_statuses = ("Offer",)

    screens = sum(totals.get(s, 0) for s in screen_statuses)
    interviews = sum(totals.get(s, 0) for s in interview_statuses)
    offers = sum(totals.get(s, 0) for s in offer_statuses)

    conversion_rates = {
        "applied_to_screen": round(screens / total_apps * 100, 1) if total_apps else 0,
        "screen_to_interview": round(interviews / screens * 100, 1) if screens else 0,
        "interview_to_offer": round(offers / interviews * 100, 1) if interviews else 0,
        "overall_offer_rate": round(offers / total_apps * 100, 1) if total_apps else 0,
    }

    # Average days per stage
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

    return jsonify({
        "funnel": funnel,
        "conversion_rates": conversion_rates,
        "avg_days_per_stage": avg_days_per_stage,
    }), 200


# ---------------------------------------------------------------------------
# Source Effectiveness
# ---------------------------------------------------------------------------

@bp.route("/api/reporting/sources", methods=["GET"])
def sources_report():
    """Source effectiveness with best/worst highlights."""
    sources = db.query(
        """
        SELECT source, total_apps, got_response, response_rate_pct,
               got_interview, interview_rate_pct
        FROM source_effectiveness
        ORDER BY interview_rate_pct DESC
        """
    )

    # Add offer counts per source
    offer_counts = db.query(
        """
        SELECT a.source, COUNT(o.id) AS offers
        FROM applications a
        JOIN offers o ON o.application_id = a.id
        GROUP BY a.source
        """
    )
    offer_map = {r["source"]: r["offers"] for r in offer_counts}

    for s in sources:
        s["offers"] = offer_map.get(s["source"], 0)

    best = sources[0]["source"] if sources else None
    worst = sources[-1]["source"] if sources else None

    return jsonify({
        "sources": sources,
        "best_source": best,
        "worst_source": worst,
    }), 200


# ---------------------------------------------------------------------------
# Monthly Activity Trends
# ---------------------------------------------------------------------------

@bp.route("/api/reporting/monthly", methods=["GET"])
def monthly_report():
    """Monthly activity with month-over-month deltas."""
    months = db.query(
        "SELECT month, applications, interviews, rejections, ghosted, offers FROM monthly_activity ORDER BY month"
    )

    # Compute deltas
    for i, m in enumerate(months):
        if i == 0:
            m["delta_apps"] = 0
            m["delta_interviews"] = 0
            m["delta_offers"] = 0
        else:
            prev = months[i - 1]
            m["delta_apps"] = (m["applications"] or 0) - (prev["applications"] or 0)
            m["delta_interviews"] = (m["interviews"] or 0) - (prev["interviews"] or 0)
            m["delta_offers"] = (m["offers"] or 0) - (prev["offers"] or 0)

    return jsonify({"months": months}), 200


# ---------------------------------------------------------------------------
# Full Campaign Dashboard
# ---------------------------------------------------------------------------

@bp.route("/api/reporting/campaign", methods=["GET"])
def campaign_report():
    """Comprehensive campaign performance dashboard."""
    stats = db.query_one(
        """
        SELECT
            COUNT(*) AS total_apps,
            COUNT(*) FILTER (WHERE status NOT IN ('Applied','Ghosted')) AS got_response,
            COUNT(*) FILTER (WHERE status IN ('Interview','Technical','Final','Offer')) AS reached_interview,
            COUNT(*) FILTER (WHERE status = 'Offer') AS offers,
            MIN(date_applied) AS first_app,
            MAX(date_applied) AS latest_app,
            COUNT(DISTINCT company_name) AS unique_companies,
            COUNT(DISTINCT source) AS unique_sources
        FROM applications
        """
    )

    total = stats["total_apps"] or 0
    stats["response_rate"] = round((stats["got_response"] or 0) / total * 100, 1) if total else 0
    stats["interview_rate"] = round((stats["reached_interview"] or 0) / total * 100, 1) if total else 0
    stats["offer_rate"] = round((stats["offers"] or 0) / total * 100, 1) if total else 0

    # Campaign duration in days
    if stats["first_app"] and stats["latest_app"]:
        delta = stats["latest_app"] - stats["first_app"]
        stats["campaign_days"] = delta.days if hasattr(delta, "days") else 0
    else:
        stats["campaign_days"] = 0

    # Best performing companies (by furthest stage reached)
    stage_order = "CASE status WHEN 'Offer' THEN 6 WHEN 'Final' THEN 5 WHEN 'Technical' THEN 4 WHEN 'Interview' THEN 3 WHEN 'Phone Screen' THEN 2 WHEN 'Applied' THEN 1 ELSE 0 END"
    best_companies = db.query(
        f"""
        SELECT company_name, role, status,
               {stage_order} AS stage_rank
        FROM applications
        ORDER BY stage_rank DESC, updated_at DESC
        LIMIT 10
        """
    )

    # Weekly activity heatmap (apps per week)
    weekly = db.query(
        """
        SELECT DATE_TRUNC('week', date_applied)::date AS week_start,
               COUNT(*) AS apps
        FROM applications
        WHERE date_applied IS NOT NULL
        GROUP BY week_start
        ORDER BY week_start
        """
    )

    # Serialize dates for JSON
    if stats.get("first_app"):
        stats["first_app"] = stats["first_app"].isoformat() if hasattr(stats["first_app"], "isoformat") else str(stats["first_app"])
    if stats.get("latest_app"):
        stats["latest_app"] = stats["latest_app"].isoformat() if hasattr(stats["latest_app"], "isoformat") else str(stats["latest_app"])

    for w in weekly:
        if hasattr(w.get("week_start"), "isoformat"):
            w["week_start"] = w["week_start"].isoformat()

    return jsonify({
        "stats": stats,
        "best_companies": best_companies,
        "weekly_activity": weekly,
    }), 200


# ---------------------------------------------------------------------------
# Interview Analytics
# ---------------------------------------------------------------------------

@bp.route("/api/reporting/interviews", methods=["GET"])
def interview_analytics():
    """Interview win rates, common questions, feeling distribution."""
    # Win rate by type
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

    # Overall feeling distribution from debriefs
    feeling_dist = db.query(
        """
        SELECT overall_feeling, COUNT(*) AS count
        FROM interview_debriefs
        WHERE overall_feeling IS NOT NULL
        GROUP BY overall_feeling
        ORDER BY count DESC
        """
    )

    # Common questions from debriefs (aggregate JSONB arrays)
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

    # Lessons learned aggregation
    lessons_raw = db.query(
        """
        SELECT lessons_learned
        FROM interview_debriefs
        WHERE lessons_learned IS NOT NULL AND lessons_learned != ''
        """
    )
    lessons = [r["lessons_learned"] for r in lessons_raw]

    return jsonify({
        "by_type": by_type,
        "feeling_distribution": feeling_dist,
        "common_questions": common_questions,
        "lessons_learned": lessons,
    }), 200


# ---------------------------------------------------------------------------
# Outreach Analytics
# ---------------------------------------------------------------------------

@bp.route("/api/reporting/outreach", methods=["GET"])
def outreach_analytics():
    """Outreach message stats by channel and type."""
    summary = db.query_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE direction = 'outbound') AS total_sent,
            COUNT(*) FILTER (WHERE direction = 'inbound') AS total_responses,
            ROUND(
                COUNT(*) FILTER (WHERE direction = 'inbound') * 100.0 /
                NULLIF(COUNT(*) FILTER (WHERE direction = 'outbound'), 0), 1
            ) AS response_rate
        FROM outreach_messages
        """
    )

    by_channel = db.query(
        """
        SELECT channel,
               COUNT(*) FILTER (WHERE direction = 'outbound') AS sent,
               COUNT(*) FILTER (WHERE direction = 'inbound') AS responses,
               ROUND(
                   COUNT(*) FILTER (WHERE direction = 'inbound') * 100.0 /
                   NULLIF(COUNT(*) FILTER (WHERE direction = 'outbound'), 0), 1
               ) AS response_rate
        FROM outreach_messages
        GROUP BY channel
        ORDER BY response_rate DESC NULLS LAST
        """
    )

    by_status = db.query(
        """
        SELECT status, COUNT(*) AS count
        FROM outreach_messages
        GROUP BY status
        ORDER BY count DESC
        """
    )

    return jsonify({
        "total_sent": summary["total_sent"] or 0,
        "total_responses": summary["total_responses"] or 0,
        "response_rate": float(summary["response_rate"] or 0),
        "by_channel": by_channel,
        "by_status": by_status,
    }), 200


# ---------------------------------------------------------------------------
# Materials Generation Analytics
# ---------------------------------------------------------------------------

@bp.route("/api/reporting/materials", methods=["GET"])
def materials_analytics():
    """Generated materials stats by type and voice check pass rate."""
    by_type = db.query(
        """
        SELECT type, COUNT(*) AS count
        FROM generated_materials
        GROUP BY type
        ORDER BY count DESC
        """
    )

    totals = db.query_one(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'voice_passed') AS voice_passed,
            COUNT(*) FILTER (WHERE status = 'voice_failed') AS voice_failed
        FROM generated_materials
        """
    )
    total = totals["total"] or 0
    passed = totals["voice_passed"] or 0

    # Average materials per application
    avg_per_app = db.query_one(
        """
        SELECT ROUND(COUNT(gm.id)::numeric / NULLIF(COUNT(DISTINCT gm.application_id), 0), 1) AS avg
        FROM generated_materials gm
        WHERE gm.application_id IS NOT NULL
        """
    )

    return jsonify({
        "by_type": by_type,
        "total_generated": total,
        "voice_pass_rate": round(passed / total * 100, 1) if total else 0,
        "avg_per_application": float(avg_per_app["avg"] or 0),
    }), 200


# ---------------------------------------------------------------------------
# Weekly Rollup
# ---------------------------------------------------------------------------

@bp.route("/api/reporting/weekly-rollup", methods=["GET"])
def weekly_rollup():
    """Last 7 days summary with comparison to previous week."""
    this_week = db.query_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE date_applied >= NOW() - INTERVAL '7 days') AS new_apps,
            COUNT(*) FILTER (WHERE status = 'Offer' AND last_status_change >= NOW() - INTERVAL '7 days') AS offers
        FROM applications
        """
    )

    this_week_interviews = db.query_one(
        """
        SELECT COUNT(*) AS interviews
        FROM interviews
        WHERE date >= NOW() - INTERVAL '7 days'
        """
    )

    this_week_outreach = db.query_one(
        """
        SELECT COUNT(*) AS outreach_sent
        FROM outreach_messages
        WHERE direction = 'outbound' AND created_at >= NOW() - INTERVAL '7 days'
        """
    )

    this_week_materials = db.query_one(
        """
        SELECT COUNT(*) AS materials
        FROM generated_materials
        WHERE generated_at >= NOW() - INTERVAL '7 days'
        """
    )

    last_week = db.query_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE date_applied >= NOW() - INTERVAL '14 days' AND date_applied < NOW() - INTERVAL '7 days') AS new_apps,
            COUNT(*) FILTER (WHERE status = 'Offer' AND last_status_change >= NOW() - INTERVAL '14 days' AND last_status_change < NOW() - INTERVAL '7 days') AS offers
        FROM applications
        """
    )

    last_week_interviews = db.query_one(
        """
        SELECT COUNT(*) AS interviews
        FROM interviews
        WHERE date >= NOW() - INTERVAL '14 days' AND date < NOW() - INTERVAL '7 days'
        """
    )

    last_week_outreach = db.query_one(
        """
        SELECT COUNT(*) AS outreach_sent
        FROM outreach_messages
        WHERE direction = 'outbound'
          AND created_at >= NOW() - INTERVAL '14 days'
          AND created_at < NOW() - INTERVAL '7 days'
        """
    )

    last_week_materials = db.query_one(
        """
        SELECT COUNT(*) AS materials
        FROM generated_materials
        WHERE generated_at >= NOW() - INTERVAL '14 days'
          AND generated_at < NOW() - INTERVAL '7 days'
        """
    )

    tw = {
        "new_apps": this_week["new_apps"] or 0,
        "interviews": this_week_interviews["interviews"] or 0,
        "offers": this_week["offers"] or 0,
        "outreach_sent": this_week_outreach["outreach_sent"] or 0,
        "materials_generated": this_week_materials["materials"] or 0,
    }

    lw = {
        "new_apps": last_week["new_apps"] or 0,
        "interviews": last_week_interviews["interviews"] or 0,
        "offers": last_week["offers"] or 0,
        "outreach_sent": last_week_outreach["outreach_sent"] or 0,
        "materials_generated": last_week_materials["materials"] or 0,
    }

    deltas = {k: tw[k] - lw[k] for k in tw}

    return jsonify({
        "this_week": tw,
        "last_week": lw,
        "deltas": deltas,
    }), 200
