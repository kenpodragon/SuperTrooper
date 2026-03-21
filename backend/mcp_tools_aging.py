"""MCP tool functions for application aging and link monitoring.

Orchestrator note: import these and register with the MCP server in mcp_server.py.
Each function is decorated with @mcp.tool() — pass your `mcp` instance via the
register_aging_tools(mcp) helper at the bottom of this file.
"""

from __future__ import annotations

import db


def register_aging_tools(mcp):
    """Register all aging MCP tools with the given MCP server instance."""

    @mcp.tool()
    def get_stale_applications(days: int = 14, status: str | None = None) -> dict:
        """Get applications that haven't had a status change in X days.

        Args:
            days: Number of days without activity to be considered stale (default 14)
            status: Optional status filter (e.g. 'Applied', 'Phone Screen')

        Returns:
            dict with count and stale applications list
        """
        clauses = ["a.last_status_change < NOW() - INTERVAL '%s days'"]
        params: list = [days]

        if status:
            clauses.append("a.status = %s")
            params.append(status)

        where = "WHERE " + " AND ".join(clauses)

        rows = db.query(
            f"""
            SELECT a.id, a.company_name, a.role, a.status, a.date_applied,
                   a.last_status_change, a.link_status, a.posting_closed,
                   a.jd_url,
                   EXTRACT(DAY FROM NOW() - a.last_status_change)::int AS days_stale
            FROM applications a
            {where}
            ORDER BY a.last_status_change ASC
            """,
            params,
        )
        return {"count": len(rows), "applications": rows}

    @mcp.tool()
    def check_posting_status(entity_type: str, entity_id: int) -> dict:
        """Check and update the posting/link status of a saved job or application.

        Note: This marks the record with the current check timestamp. Actual HTTP
        link checking is deferred to a cron job or manual trigger -- this tool
        reads and returns the stored status, and stamps last_link_check_at = NOW().

        Args:
            entity_type: 'saved_job' or 'application'
            entity_id: The record ID

        Returns:
            dict with current link status info
        """
        if entity_type == "saved_job":
            row = db.execute_returning(
                """
                UPDATE saved_jobs
                SET last_link_check_at = NOW()
                WHERE id = %s
                RETURNING id, title, company, url AS jd_url,
                          link_status, posting_closed, posting_closed_at,
                          last_link_check_at
                """,
                (entity_id,),
            )
        elif entity_type == "application":
            row = db.execute_returning(
                """
                UPDATE applications
                SET last_link_check_at = NOW()
                WHERE id = %s
                RETURNING id, role, company_name AS company, jd_url,
                          link_status, posting_closed, posting_closed_at,
                          last_link_check_at
                """,
                (entity_id,),
            )
        else:
            return {"error": "entity_type must be 'saved_job' or 'application'"}

        if not row:
            return {"error": f"{entity_type} {entity_id} not found"}

        return {"entity_type": entity_type, **row}

    @mcp.tool()
    def get_aging_summary() -> dict:
        """Get a summary of application aging across the pipeline.

        Returns:
            dict with counts: stale_applications, stale_saved_jobs,
            closed_postings, needs_link_check
        """
        stale_apps = db.query_one(
            """
            SELECT COUNT(*)::int AS count
            FROM applications
            WHERE last_status_change < NOW() - INTERVAL '14 days'
            """
        )
        stale_jobs = db.query_one(
            """
            SELECT COUNT(*)::int AS count
            FROM saved_jobs
            WHERE updated_at < NOW() - INTERVAL '30 days'
              AND status NOT IN ('applied', 'archived')
            """
        )
        closed_apps = db.query_one(
            "SELECT COUNT(*)::int AS count FROM applications WHERE posting_closed = TRUE"
        )
        closed_jobs = db.query_one(
            "SELECT COUNT(*)::int AS count FROM saved_jobs WHERE posting_closed = TRUE"
        )
        unknown_apps = db.query_one(
            "SELECT COUNT(*)::int AS count FROM applications WHERE link_status = 'unknown'"
        )
        unknown_jobs = db.query_one(
            "SELECT COUNT(*)::int AS count FROM saved_jobs WHERE link_status = 'unknown'"
        )

        return {
            "stale_applications": stale_apps["count"] if stale_apps else 0,
            "stale_saved_jobs": stale_jobs["count"] if stale_jobs else 0,
            "closed_postings": (
                (closed_apps["count"] if closed_apps else 0)
                + (closed_jobs["count"] if closed_jobs else 0)
            ),
            "needs_link_check": (
                (unknown_apps["count"] if unknown_apps else 0)
                + (unknown_jobs["count"] if unknown_jobs else 0)
            ),
        }
