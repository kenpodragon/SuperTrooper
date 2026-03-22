"""Routes for Calendar Interview Detection."""

from flask import Blueprint, request, jsonify
from services.calendar_intelligence import (
    detect_interviews,
    get_upcoming_interviews,
    get_interview_prep_needed,
)

bp = Blueprint("calendar_intelligence", __name__)


@bp.route("/api/calendar-intelligence/detect", methods=["POST"])
def detect():
    """Accept calendar events and detect interviews.

    Body (JSON):
        events (required): list of calendar event dicts, each with:
            title, start, end, attendees, description, location, event_id
    """
    data = request.get_json(force=True)
    events = data.get("events")
    if not events or not isinstance(events, list):
        return jsonify({"error": "events array is required"}), 400

    try:
        result = detect_interviews(events)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/calendar-intelligence/upcoming", methods=["GET"])
def upcoming():
    """Return upcoming interviews.

    Query params:
        days: number of days to look ahead (default 14)
    """
    days = int(request.args.get("days", 14))
    try:
        rows = get_upcoming_interviews(days)
        return jsonify(rows), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/calendar-intelligence/prep-needed", methods=["GET"])
def prep_needed():
    """Return upcoming interviews (next 7 days) that still need prep."""
    try:
        rows = get_interview_prep_needed()
        return jsonify(rows), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
