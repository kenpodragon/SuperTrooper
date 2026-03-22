"""Routes for Email Intelligence pipeline."""

from flask import Blueprint, jsonify
from services.email_intelligence import (
    run_full_pipeline,
    detect_ghosted_applications,
    get_scan_stats,
    process_email_scan_results,
)

bp = Blueprint("email_intelligence", __name__)


@bp.route("/api/email-intelligence/scan", methods=["POST"])
def trigger_full_scan():
    """Trigger the full email intelligence pipeline.

    Scans emails -> processes into notifications/status updates -> detects ghosted.
    Returns combined summary.
    """
    try:
        result = run_full_pipeline()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/email-intelligence/ghosted", methods=["GET"])
def list_ghosted():
    """Return list of ghosted applications (no activity for 14+ days)."""
    try:
        result = detect_ghosted_applications()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/email-intelligence/status", methods=["GET"])
def scan_status():
    """Return email scan statistics: total, scanned, categorized breakdown."""
    try:
        result = get_scan_stats()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/email-intelligence/process", methods=["POST"])
def process_only():
    """Process already-scanned emails into notifications and status updates.

    Skips the scan step -- useful when emails were already scanned via MCP tool.
    """
    try:
        result = process_email_scan_results()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
