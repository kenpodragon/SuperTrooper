"""Routes for analytics views."""

from flask import Blueprint, request, jsonify
import db
from mcp_tools_reporting import (
    get_weekly_rollup,
    get_pipeline_report,
    generate_strategy_recommendations,
)

bp = Blueprint("analytics", __name__)


@bp.route("/api/analytics/funnel", methods=["GET"])
def funnel():
    """Application funnel view."""
    rows = db.query("SELECT status, count, pct FROM application_funnel")
    return jsonify(rows), 200


@bp.route("/api/analytics/monthly", methods=["GET"])
def monthly():
    """Monthly activity view."""
    rows = db.query(
        "SELECT month, applications, interviews, rejections, ghosted, offers FROM monthly_activity"
    )
    return jsonify(rows), 200


@bp.route("/api/analytics/sources", methods=["GET"])
def sources():
    """Source effectiveness view."""
    rows = db.query(
        """
        SELECT source, total_apps, got_response, response_rate_pct,
               got_interview, interview_rate_pct
        FROM source_effectiveness
        """
    )
    return jsonify(rows), 200


@bp.route("/api/analytics/summary", methods=["GET"])
def summary():
    """Overall stats: total apps, interviews, companies, etc."""
    stats = db.query_one(
        """
        SELECT
            (SELECT COUNT(*) FROM applications) AS total_applications,
            (SELECT COUNT(*) FROM applications WHERE status = 'Applied') AS applied,
            (SELECT COUNT(*) FROM applications WHERE status IN ('Phone Screen','Interview','Technical','Final')) AS in_progress,
            (SELECT COUNT(*) FROM applications WHERE status = 'Offer') AS offers,
            (SELECT COUNT(*) FROM applications WHERE status = 'Rejected') AS rejected,
            (SELECT COUNT(*) FROM applications WHERE status = 'Ghosted') AS ghosted,
            (SELECT COUNT(*) FROM interviews) AS total_interviews,
            (SELECT COUNT(*) FROM companies) AS total_companies,
            (SELECT COUNT(*) FROM contacts) AS total_contacts,
            (SELECT COUNT(*) FROM emails) AS total_emails,
            (SELECT COUNT(DISTINCT source) FROM applications) AS unique_sources
        """
    )
    return jsonify(stats), 200


@bp.route("/api/analytics/weekly-digest", methods=["GET"])
def weekly_digest():
    """Weekly campaign digest: rollup + pipeline trends + strategy recommendations."""
    try:
        rollup = get_weekly_rollup()
        pipeline = get_pipeline_report()
        recommendations = generate_strategy_recommendations(rollup, pipeline)

        return jsonify({
            "rollup": rollup,
            "pipeline": pipeline,
            "recommendations": recommendations,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /api/analytics/rejection-patterns — Common rejection reasons & patterns
# ---------------------------------------------------------------------------

@bp.route("/api/analytics/rejection-patterns", methods=["GET"])
def rejection_patterns():
    """Analyze rejection patterns: reasons, stage of rejection, company patterns."""
    # Rejection by stage (which status they were in when rejected)
    stage_patterns = db.query(
        """
        SELECT ash.old_status AS rejected_from_stage,
               COUNT(*) AS count
        FROM application_status_history ash
        WHERE ash.new_status = 'Rejected'
        GROUP BY ash.old_status
        ORDER BY count DESC
        """
    ) or []

    # Rejection by company (which companies reject most)
    company_patterns = db.query(
        """
        SELECT a.company_name,
               COUNT(*) AS rejection_count,
               (SELECT COUNT(*) FROM applications a2
                WHERE a2.company_name = a.company_name) AS total_apps,
               ROUND(
                   COUNT(*)::numeric /
                   NULLIF((SELECT COUNT(*) FROM applications a2
                           WHERE a2.company_name = a.company_name), 0) * 100, 1
               ) AS rejection_rate_pct
        FROM applications a
        WHERE a.status = 'Rejected'
        GROUP BY a.company_name
        HAVING COUNT(*) >= 1
        ORDER BY rejection_count DESC
        LIMIT 20
        """
    ) or []

    # Rejection by source
    source_patterns = db.query(
        """
        WITH source_totals AS (
            SELECT COALESCE(source, 'Unknown') AS src, COUNT(*) AS total
            FROM applications GROUP BY COALESCE(source, 'Unknown')
        ),
        source_rejections AS (
            SELECT COALESCE(source, 'Unknown') AS src, COUNT(*) AS rejection_count
            FROM applications WHERE status = 'Rejected'
            GROUP BY COALESCE(source, 'Unknown')
        )
        SELECT sr.src AS source, sr.rejection_count,
               st.total AS total_from_source,
               ROUND(sr.rejection_count::numeric / NULLIF(st.total, 0) * 100, 1) AS rejection_rate_pct
        FROM source_rejections sr
        JOIN source_totals st ON st.src = sr.src
        ORDER BY sr.rejection_count DESC
        """
    ) or []

    # Time to rejection (avg days from apply to rejection)
    time_to_rejection = db.query_one(
        """
        SELECT
            ROUND(AVG(EXTRACT(DAY FROM ash.changed_at - a.date_applied::timestamp))::numeric, 1)
                AS avg_days_to_rejection,
            ROUND(MIN(EXTRACT(DAY FROM ash.changed_at - a.date_applied::timestamp))::numeric, 0)
                AS min_days,
            ROUND(MAX(EXTRACT(DAY FROM ash.changed_at - a.date_applied::timestamp))::numeric, 0)
                AS max_days,
            COUNT(*) AS sample_size
        FROM application_status_history ash
        JOIN applications a ON a.id = ash.application_id
        WHERE ash.new_status = 'Rejected'
          AND a.date_applied IS NOT NULL
        """
    ) or {}

    # Rejection notes/reasons (from status history notes)
    rejection_notes = db.query(
        """
        SELECT ash.notes, a.company_name, a.role, ash.old_status AS stage
        FROM application_status_history ash
        JOIN applications a ON a.id = ash.application_id
        WHERE ash.new_status = 'Rejected'
          AND ash.notes IS NOT NULL
          AND ash.notes != ''
        ORDER BY ash.changed_at DESC
        LIMIT 20
        """
    ) or []

    return jsonify({
        "by_stage": stage_patterns,
        "by_company": company_patterns,
        "by_source": source_patterns,
        "time_to_rejection": time_to_rejection,
        "recent_rejection_notes": rejection_notes,
        "total_rejections": sum(s.get("count", 0) for s in stage_patterns),
    }), 200


# ---------------------------------------------------------------------------
# GET /api/analytics/win-loss — Win/loss ratio by company size, role type, industry
# ---------------------------------------------------------------------------

@bp.route("/api/analytics/win-loss", methods=["GET"])
def win_loss():
    """Win/loss analysis by company size, role type, and industry/sector."""
    # By company size
    by_size = db.query(
        """
        SELECT COALESCE(c.size, 'Unknown') AS company_size,
               COUNT(*) AS total,
               SUM(CASE WHEN a.status IN ('Offer','Accepted') THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN a.status IN ('Rejected','Ghosted') THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN a.status NOT IN ('Offer','Accepted','Rejected','Ghosted','Withdrawn','Rescinded')
                   THEN 1 ELSE 0 END) AS in_progress,
               ROUND(
                   CASE WHEN SUM(CASE WHEN a.status IN ('Offer','Accepted','Rejected','Ghosted') THEN 1 ELSE 0 END) > 0
                   THEN SUM(CASE WHEN a.status IN ('Offer','Accepted') THEN 1 ELSE 0 END)::numeric /
                        SUM(CASE WHEN a.status IN ('Offer','Accepted','Rejected','Ghosted') THEN 1 ELSE 0 END) * 100
                   ELSE 0 END, 1
               ) AS win_rate_pct
        FROM applications a
        LEFT JOIN companies c ON c.name ILIKE a.company_name
        GROUP BY COALESCE(c.size, 'Unknown')
        ORDER BY total DESC
        """
    ) or []

    # By sector/industry
    by_sector = db.query(
        """
        SELECT COALESCE(c.sector, 'Unknown') AS sector,
               COUNT(*) AS total,
               SUM(CASE WHEN a.status IN ('Offer','Accepted') THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN a.status IN ('Rejected','Ghosted') THEN 1 ELSE 0 END) AS losses,
               ROUND(
                   CASE WHEN SUM(CASE WHEN a.status IN ('Offer','Accepted','Rejected','Ghosted') THEN 1 ELSE 0 END) > 0
                   THEN SUM(CASE WHEN a.status IN ('Offer','Accepted') THEN 1 ELSE 0 END)::numeric /
                        SUM(CASE WHEN a.status IN ('Offer','Accepted','Rejected','Ghosted') THEN 1 ELSE 0 END) * 100
                   ELSE 0 END, 1
               ) AS win_rate_pct
        FROM applications a
        LEFT JOIN companies c ON c.name ILIKE a.company_name
        GROUP BY COALESCE(c.sector, 'Unknown')
        ORDER BY total DESC
        """
    ) or []

    # By role type (extract from role title)
    by_role = db.query(
        """
        SELECT
            CASE
                WHEN a.role ILIKE '%%CTO%%' OR a.role ILIKE '%%chief tech%%' THEN 'CTO'
                WHEN a.role ILIKE '%%VP%%' OR a.role ILIKE '%%vice president%%' THEN 'VP'
                WHEN a.role ILIKE '%%director%%' THEN 'Director'
                WHEN a.role ILIKE '%%architect%%' THEN 'Architect'
                WHEN a.role ILIKE '%%manager%%' THEN 'Manager'
                WHEN a.role ILIKE '%%lead%%' OR a.role ILIKE '%%principal%%' THEN 'Lead/Principal'
                WHEN a.role ILIKE '%%head%%' THEN 'Head of'
                ELSE 'Other'
            END AS role_type,
            COUNT(*) AS total,
            SUM(CASE WHEN a.status IN ('Offer','Accepted') THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN a.status IN ('Rejected','Ghosted') THEN 1 ELSE 0 END) AS losses,
            ROUND(
                CASE WHEN SUM(CASE WHEN a.status IN ('Offer','Accepted','Rejected','Ghosted') THEN 1 ELSE 0 END) > 0
                THEN SUM(CASE WHEN a.status IN ('Offer','Accepted') THEN 1 ELSE 0 END)::numeric /
                     SUM(CASE WHEN a.status IN ('Offer','Accepted','Rejected','Ghosted') THEN 1 ELSE 0 END) * 100
                ELSE 0 END, 1
            ) AS win_rate_pct
        FROM applications a
        GROUP BY role_type
        ORDER BY total DESC
        """
    ) or []

    # Overall win/loss
    overall = db.query_one(
        """
        SELECT
            COUNT(*) AS total_applications,
            SUM(CASE WHEN status IN ('Offer','Accepted') THEN 1 ELSE 0 END) AS total_wins,
            SUM(CASE WHEN status IN ('Rejected','Ghosted') THEN 1 ELSE 0 END) AS total_losses,
            SUM(CASE WHEN status NOT IN ('Offer','Accepted','Rejected','Ghosted','Withdrawn','Rescinded')
                THEN 1 ELSE 0 END) AS in_progress,
            ROUND(
                CASE WHEN SUM(CASE WHEN status IN ('Offer','Accepted','Rejected','Ghosted') THEN 1 ELSE 0 END) > 0
                THEN SUM(CASE WHEN status IN ('Offer','Accepted') THEN 1 ELSE 0 END)::numeric /
                     SUM(CASE WHEN status IN ('Offer','Accepted','Rejected','Ghosted') THEN 1 ELSE 0 END) * 100
                ELSE 0 END, 1
            ) AS overall_win_rate_pct
        FROM applications
        """
    ) or {}

    return jsonify({
        "overall": overall,
        "by_company_size": by_size,
        "by_sector": by_sector,
        "by_role_type": by_role,
    }), 200
