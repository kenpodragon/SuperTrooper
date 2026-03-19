"""Routes for analytics views."""

from flask import Blueprint, jsonify
import db

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
