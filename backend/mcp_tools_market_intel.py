"""MCP tool functions for market intelligence signals.

Orchestrator note: call register_market_intel_tools(mcp) in mcp_server.py.
"""

from __future__ import annotations

import json

import db


def register_market_intel_tools(mcp):
    """Register all market intelligence MCP tools with the given MCP server instance."""

    @mcp.tool()
    def get_market_signals(
        source: str | None = None,
        signal_type: str | None = None,
        severity: str | None = None,
        industry: str | None = None,
        region: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Get market intelligence signals, optionally filtered.

        Args:
            source: Filter by source (bls_jolts, lisep_tru, warn_act, hn_hiring, news, manual)
            signal_type: Filter by type (layoff, hiring_freeze, market_trend, job_openings,
                         separation_rate, quit_rate, wage_data)
            severity: Filter by severity (positive, neutral, negative, critical)
            industry: Filter by industry sector
            region: Filter by region
            limit: Max results (default 20)

        Returns:
            dict with count and signals list
        """
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
            LIMIT %s
            """,
            params + [limit],
        )
        return {"count": len(rows), "signals": rows}

    @mcp.tool()
    def add_market_signal(
        source: str,
        signal_type: str,
        title: str,
        severity: str = "neutral",
        body: str | None = None,
        data_json: str | None = None,
        region: str | None = None,
        industry: str | None = None,
        source_url: str | None = None,
    ) -> dict:
        """Add a market intelligence signal.

        Args:
            source: Signal source (bls_jolts, lisep_tru, warn_act, hn_hiring, news, manual)
            signal_type: Type of signal (layoff, hiring_freeze, market_trend, job_openings,
                         separation_rate, quit_rate, wage_data)
            title: Signal title/headline
            severity: positive, neutral, negative, or critical (default: neutral)
            body: Detailed description
            data_json: Optional JSON string with structured data specific to the signal type
            region: Geographic region (e.g., US, CA, New York Metro)
            industry: Industry sector (e.g., Technology, Finance, Healthcare)
            source_url: URL to the original source

        Returns:
            dict with created signal
        """
        if data_json is not None:
            try:
                json.loads(data_json)
            except (json.JSONDecodeError, TypeError):
                return {"error": "data_json must be a valid JSON string"}

        row = db.execute_returning(
            """
            INSERT INTO market_signals
                (source, signal_type, title, body, data_json, region, industry,
                 severity, source_url)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
            RETURNING *
            """,
            (source, signal_type, title, body, data_json, region, industry, severity, source_url),
        )
        return row or {"error": "Insert failed"}

    @mcp.tool()
    def get_market_summary() -> dict:
        """Get a summary of current market intelligence.

        Returns:
            dict with counts by source/type/severity, plus recent highlights (last 7 days)
        """
        by_source = db.query(
            "SELECT source, COUNT(*) AS count FROM market_signals GROUP BY source ORDER BY count DESC"
        )
        by_type = db.query(
            "SELECT signal_type, COUNT(*) AS count FROM market_signals GROUP BY signal_type ORDER BY count DESC"
        )
        by_severity = db.query(
            "SELECT severity, COUNT(*) AS count FROM market_signals GROUP BY severity ORDER BY count DESC"
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

        return {
            "total": total["total"] if total else 0,
            "by_source": by_source,
            "by_signal_type": by_type,
            "by_severity": by_severity,
            "recent_highlights": recent_highlights,
        }
