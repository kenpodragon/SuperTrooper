"""MCP tool functions for companies, contacts, emails, and analytics.

Orchestrator note: call register_contacts_tools(mcp) in mcp_server.py.
"""

from __future__ import annotations

import db


def register_contacts_tools(mcp):
    """Register all company/contact/email/analytics MCP tools with the given MCP server instance."""

    @mcp.tool()
    def search_companies(
        query: str = "",
        priority: str = "",
        sector: str = "",
        limit: int = 50,
    ) -> dict:
        """Search target companies by name, priority, or sector.

        Args:
            query: Company name search (ILIKE).
            priority: Priority tier (A, B, C).
            sector: Sector filter (ILIKE).
            limit: Max results (default 50).
        """
        clauses, params = [], []
        if query:
            clauses.append("name ILIKE %s")
            params.append(f"%{query}%")
        if priority:
            clauses.append("priority = %s")
            params.append(priority)
        if sector:
            clauses.append("sector ILIKE %s")
            params.append(f"%{sector}%")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = db.query(
            f"""
            SELECT id, name, sector, hq_location, size, stage, fit_score, priority,
                   target_role, resume_variant, melbourne_relevant, comp_range, notes
            FROM companies
            {where}
            ORDER BY fit_score DESC NULLS LAST, name
            LIMIT %s
            """,
            params + [limit],
        )
        return {"count": len(rows), "companies": rows}

    @mcp.tool()
    def get_company_dossier(name: str) -> dict:
        """Get full company info including applications, contacts, and related emails.

        Args:
            name: Company name (ILIKE match).
        """
        company = db.query_one(
            "SELECT * FROM companies WHERE name ILIKE %s",
            (f"%{name}%",),
        )
        if not company:
            return {"error": f"Company '{name}' not found"}

        applications = db.query(
            """
            SELECT id, role, date_applied, source, status, resume_version, notes,
                   last_status_change
            FROM applications
            WHERE company_name ILIKE %s
            ORDER BY date_applied DESC NULLS LAST
            """,
            (f"%{name}%",),
        )

        contacts = db.query(
            """
            SELECT id, name, title, relationship, email, linkedin_url,
                   relationship_strength, last_contact
            FROM contacts
            WHERE company ILIKE %s
            ORDER BY relationship_strength, name
            """,
            (f"%{name}%",),
        )

        emails = db.query(
            """
            SELECT id, date, from_name, subject, snippet, category
            FROM emails
            WHERE subject ILIKE %s OR from_address ILIKE %s OR from_name ILIKE %s
            ORDER BY date DESC NULLS LAST
            LIMIT 20
            """,
            (f"%{name}%", f"%{name}%", f"%{name}%"),
        )

        company["applications"] = applications
        company["contacts"] = contacts
        company["emails"] = emails
        return company

    @mcp.tool()
    def search_contacts(company: str = "", name: str = "") -> dict:
        """Search contacts by company or name.

        Args:
            company: Company name filter (ILIKE).
            name: Contact name filter (ILIKE).
        """
        clauses, params = [], []
        if company:
            clauses.append("company ILIKE %s")
            params.append(f"%{company}%")
        if name:
            clauses.append("name ILIKE %s")
            params.append(f"%{name}%")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = db.query(
            f"""
            SELECT id, name, company, title, relationship, email, phone,
                   linkedin_url, relationship_strength, last_contact, notes
            FROM contacts
            {where}
            ORDER BY relationship_strength, name
            """,
            params,
        )
        return {"count": len(rows), "contacts": rows}

    @mcp.tool()
    def network_check(company: str) -> dict:
        """Find contacts and related emails for a company. Useful for warm intro research.

        Args:
            company: Company name to check network for.
        """
        contacts = db.query(
            """
            SELECT id, name, title, relationship, email, linkedin_url,
                   relationship_strength, last_contact, notes
            FROM contacts
            WHERE company ILIKE %s
            ORDER BY relationship_strength, name
            """,
            (f"%{company}%",),
        )

        emails = db.query(
            """
            SELECT id, date, from_name, from_address, subject, snippet, category
            FROM emails
            WHERE from_name ILIKE %s OR from_address ILIKE %s OR subject ILIKE %s
            ORDER BY date DESC NULLS LAST
            LIMIT 20
            """,
            (f"%{company}%", f"%{company}%", f"%{company}%"),
        )

        applications = db.query(
            """
            SELECT id, role, status, date_applied, contact_name, contact_email
            FROM applications
            WHERE company_name ILIKE %s
            ORDER BY date_applied DESC NULLS LAST
            """,
            (f"%{company}%",),
        )

        return {
            "company": company,
            "contacts": contacts,
            "related_emails": emails,
            "applications": applications,
            "has_warm_intro": any(
                c.get("relationship_strength") in ("strong", "warm") for c in contacts
            ),
        }

    @mcp.tool()
    def search_emails(
        query: str = "",
        category: str = "",
        after: str = "",
        before: str = "",
        limit: int = 20,
    ) -> dict:
        """Search emails by text, category, and date range.

        Args:
            query: Text search in subject, snippet, body (ILIKE).
            category: Email category (application, rejection, interview, recruiter, reference, other).
            after: Date filter - emails after this date (YYYY-MM-DD).
            before: Date filter - emails before this date (YYYY-MM-DD).
            limit: Max results (default 20).
        """
        clauses, params = [], []
        if query:
            clauses.append("(subject ILIKE %s OR snippet ILIKE %s OR body ILIKE %s)")
            params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])
        if category:
            clauses.append("category = %s")
            params.append(category)
        if after:
            clauses.append("date >= %s")
            params.append(after)
        if before:
            clauses.append("date <= %s")
            params.append(before)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = db.query(
            f"""
            SELECT id, date, from_name, from_address, subject, snippet, category,
                   application_id
            FROM emails
            {where}
            ORDER BY date DESC NULLS LAST
            LIMIT %s
            """,
            params + [limit],
        )
        return {"count": len(rows), "emails": rows}

    @mcp.tool()
    def get_analytics() -> dict:
        """Get pipeline statistics: funnel, source effectiveness, monthly activity, and summary counts."""
        funnel = db.query("SELECT status, count, pct FROM application_funnel")
        sources = db.query(
            "SELECT source, total_apps, got_response, response_rate_pct, got_interview, interview_rate_pct FROM source_effectiveness"
        )
        monthly = db.query(
            "SELECT month, applications, interviews, rejections, ghosted, offers FROM monthly_activity"
        )
        summary = db.query_one(
            """
            SELECT
                (SELECT COUNT(*) FROM applications) AS total_applications,
                (SELECT COUNT(*) FROM applications WHERE status IN ('Phone Screen','Interview','Technical','Final')) AS in_progress,
                (SELECT COUNT(*) FROM applications WHERE status = 'Offer') AS offers,
                (SELECT COUNT(*) FROM applications WHERE status = 'Rejected') AS rejected,
                (SELECT COUNT(*) FROM applications WHERE status = 'Ghosted') AS ghosted,
                (SELECT COUNT(*) FROM interviews) AS total_interviews,
                (SELECT COUNT(*) FROM companies) AS total_companies,
                (SELECT COUNT(*) FROM contacts) AS total_contacts
            """
        )
        return {
            "summary": summary,
            "funnel": funnel,
            "sources": sources,
            "monthly": monthly,
        }
