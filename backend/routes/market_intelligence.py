"""Routes for market_signals (market intelligence signals)."""

import json
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("market_intelligence", __name__)


@bp.route("/api/market-intelligence", methods=["GET"])
def list_market_signals():
    """List market signals with optional filters. Newest first."""
    source = request.args.get("source")
    signal_type = request.args.get("signal_type")
    severity = request.args.get("severity")
    industry = request.args.get("industry")
    region = request.args.get("region")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if source:
        clauses.append("source = %s")
        params.append(source)
    if signal_type:
        clauses.append("signal_type = %s")
        params.append(signal_type)
    if severity:
        clauses.append("severity = %s")
        params.append(severity)
    if industry:
        clauses.append("industry ILIKE %s")
        params.append(f"%{industry}%")
    if region:
        clauses.append("region ILIKE %s")
        params.append(f"%{region}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT *
        FROM market_signals
        {where}
        ORDER BY captured_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify({"count": len(rows), "signals": rows}), 200


@bp.route("/api/market-intelligence/<int:signal_id>", methods=["GET"])
def get_market_signal(signal_id):
    """Get a single market signal by ID."""
    row = db.query_one(
        "SELECT * FROM market_signals WHERE id = %s",
        (signal_id,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/market-intelligence", methods=["POST"])
def create_market_signal():
    """Create a single market signal (manual entry or cron ingest)."""
    data = request.get_json(force=True)
    if not data.get("source"):
        return jsonify({"error": "source is required"}), 400
    if not data.get("signal_type"):
        return jsonify({"error": "signal_type is required"}), 400
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    data_json = data.get("data_json")
    if data_json is not None and not isinstance(data_json, str):
        data_json = json.dumps(data_json)

    row = db.execute_returning(
        """
        INSERT INTO market_signals
            (source, signal_type, title, body, data_json, region, industry,
             severity, source_url, captured_at, expires_at)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s,
                COALESCE(%s::timestamp, NOW()), %s::timestamp)
        RETURNING *
        """,
        (
            data["source"],
            data["signal_type"],
            data["title"],
            data.get("body"),
            data_json,
            data.get("region"),
            data.get("industry"),
            data.get("severity", "neutral"),
            data.get("source_url"),
            data.get("captured_at"),
            data.get("expires_at"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/market-intelligence/batch", methods=["POST"])
def batch_create_market_signals():
    """Batch create multiple market signals (bulk ingest from external APIs)."""
    data = request.get_json(force=True)
    if not isinstance(data, list):
        return jsonify({"error": "Expected a JSON array of signals"}), 400
    if not data:
        return jsonify({"created": 0, "signals": []}), 200

    created = []
    errors = []
    for i, item in enumerate(data):
        if not item.get("source") or not item.get("signal_type") or not item.get("title"):
            errors.append({"index": i, "error": "source, signal_type, and title are required"})
            continue

        data_json = item.get("data_json")
        if data_json is not None and not isinstance(data_json, str):
            data_json = json.dumps(data_json)

        row = db.execute_returning(
            """
            INSERT INTO market_signals
                (source, signal_type, title, body, data_json, region, industry,
                 severity, source_url, captured_at, expires_at)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s,
                    COALESCE(%s::timestamp, NOW()), %s::timestamp)
            RETURNING *
            """,
            (
                item["source"],
                item["signal_type"],
                item["title"],
                item.get("body"),
                data_json,
                item.get("region"),
                item.get("industry"),
                item.get("severity", "neutral"),
                item.get("source_url"),
                item.get("captured_at"),
                item.get("expires_at"),
            ),
        )
        if row:
            created.append(row)

    return jsonify({"created": len(created), "errors": errors, "signals": created}), 201


@bp.route("/api/market-intelligence/summary", methods=["GET"])
def market_intelligence_summary():
    """Aggregated summary: counts by source, signal_type, severity. Plus recent highlights (last 7 days)."""
    by_source = db.query(
        """
        SELECT source, COUNT(*) AS count
        FROM market_signals
        GROUP BY source
        ORDER BY count DESC
        """
    )
    by_type = db.query(
        """
        SELECT signal_type, COUNT(*) AS count
        FROM market_signals
        GROUP BY signal_type
        ORDER BY count DESC
        """
    )
    by_severity = db.query(
        """
        SELECT severity, COUNT(*) AS count
        FROM market_signals
        GROUP BY severity
        ORDER BY count DESC
        """
    )
    recent_highlights = db.query(
        """
        SELECT id, source, signal_type, title, severity, region, industry, captured_at
        FROM market_signals
        WHERE captured_at >= NOW() - INTERVAL '7 days'
        ORDER BY captured_at DESC
        LIMIT 20
        """
    )
    total = db.query_one("SELECT COUNT(*) AS total FROM market_signals")

    return jsonify({
        "total": total["total"] if total else 0,
        "by_source": by_source,
        "by_signal_type": by_type,
        "by_severity": by_severity,
        "recent_highlights": recent_highlights,
    }), 200


@bp.route("/api/market-intelligence/trends", methods=["GET"])
def market_intelligence_trends():
    """Signals grouped by industry, showing signal counts and severity distribution."""
    trends = db.query(
        """
        SELECT
            industry,
            COUNT(*) AS total_signals,
            COUNT(*) FILTER (WHERE severity = 'positive') AS positive_count,
            COUNT(*) FILTER (WHERE severity = 'neutral') AS neutral_count,
            COUNT(*) FILTER (WHERE severity = 'negative') AS negative_count,
            COUNT(*) FILTER (WHERE severity = 'critical') AS critical_count,
            MAX(captured_at) AS latest_signal_at
        FROM market_signals
        WHERE industry IS NOT NULL
        GROUP BY industry
        ORDER BY total_signals DESC
        """
    )
    return jsonify({"count": len(trends), "trends": trends}), 200


@bp.route("/api/market-intelligence/expired", methods=["DELETE"])
def delete_expired_signals():
    """Clean up expired signals (where expires_at < NOW())."""
    count = db.execute(
        "DELETE FROM market_signals WHERE expires_at IS NOT NULL AND expires_at < NOW()"
    )
    return jsonify({"deleted": count}), 200
