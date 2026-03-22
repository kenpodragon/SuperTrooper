"""Routes for fetching external market intelligence data (BLS JOLTS, etc.)."""

from flask import Blueprint, jsonify, request

import db
from services.bls_fetcher import fetch_jolts

bp = Blueprint("market_intelligence_fetch", __name__)


@bp.route("/api/market-intelligence/fetch/bls-jolts", methods=["POST"])
def trigger_bls_jolts_fetch():
    """Trigger a BLS JOLTS data fetch and ingest into market_signals.

    Optional JSON body:
        start_year (int): First year to fetch (default: current year - 1)
        end_year (int): Last year to fetch (default: current year)
    """
    data = request.get_json(silent=True) or {}
    start_year = data.get("start_year")
    end_year = data.get("end_year")

    result = fetch_jolts(start_year=start_year, end_year=end_year)

    if "error" in result:
        return jsonify({
            "status": "error",
            "error": result["error"],
            "inserted": result["inserted"],
            "skipped": result["skipped"],
        }), 502

    return jsonify({
        "status": "ok",
        "inserted": result["inserted"],
        "skipped": result["skipped"],
    }), 200


@bp.route("/api/market-intelligence/fetch/bls-jolts/status", methods=["GET"])
def bls_jolts_status():
    """Return last BLS JOLTS fetch timestamp and total signal count."""
    row = db.query_one(
        """
        SELECT
            COUNT(*) AS total_signals,
            MAX(captured_at) AS latest_data_period,
            MAX(created_at) AS last_fetched_at
        FROM market_signals
        WHERE source = 'bls_jolts'
        """
    )

    if not row or row["total_signals"] == 0:
        return jsonify({
            "source": "bls_jolts",
            "total_signals": 0,
            "latest_data_period": None,
            "last_fetched_at": None,
        }), 200

    return jsonify({
        "source": "bls_jolts",
        "total_signals": row["total_signals"],
        "latest_data_period": row["latest_data_period"],
        "last_fetched_at": row["last_fetched_at"],
    }), 200
