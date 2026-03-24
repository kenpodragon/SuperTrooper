"""MCP tool functions for networking: warm paths, LinkedIn connection/profile import.

Orchestrator note: call register_networking_tools(mcp) in mcp_server.py.
"""

from __future__ import annotations

import db
from ai_providers.router import route_inference


def register_networking_tools(mcp):
    """Register all networking MCP tools with the given MCP server instance."""

    @mcp.tool()
    def find_warm_paths(company_name: str) -> dict:
        """Find warm intro paths to a target company.

        Finds direct contacts at the company, contacts at same-sector companies,
        and ranks by relationship strength.

        Args:
            company_name: Name of the target company

        Returns:
            dict with direct contacts, same_sector contacts, and warm_path_score
        """
        company = db.query_one(
            "SELECT id, name, sector FROM companies WHERE name ILIKE %s",
            (f"%{company_name}%",),
        )
        sector = company.get("sector") if company else None

        direct = db.query(
            """
            SELECT id, name, company, title, relationship, relationship_strength,
                   email, last_contact
            FROM contacts
            WHERE company ILIKE %s
            ORDER BY CASE relationship_strength
                WHEN 'strong' THEN 1 WHEN 'warm' THEN 2 WHEN 'cold' THEN 3 ELSE 4
            END, last_contact DESC NULLS LAST
            """,
            (f"%{company_name}%",),
        )

        same_sector = []
        if sector:
            same_sector = db.query(
                """
                SELECT c.id, c.name, c.company, c.title, c.relationship,
                       c.relationship_strength, co.name AS their_company
                FROM contacts c
                LEFT JOIN companies co ON c.company_id = co.id
                WHERE co.sector = %s AND c.company NOT ILIKE %s
                ORDER BY CASE c.relationship_strength
                    WHEN 'strong' THEN 1 WHEN 'warm' THEN 2 WHEN 'cold' THEN 3 ELSE 4
                END
                LIMIT 20
                """,
                (sector, f"%{company_name}%"),
            )

        score = 0
        for c in direct:
            s = c.get("relationship_strength", "")
            score += 3 if s == "strong" else 2 if s == "warm" else 1
        for c in same_sector:
            s = c.get("relationship_strength", "")
            score += 1.5 if s == "strong" else 1 if s == "warm" else 0.5

        python_result = {
            "company": company_name,
            "sector": sector,
            "direct": direct,
            "same_sector": same_sector,
            "warm_path_score": score,
        }

        def _python_warm(ctx):
            return ctx["r"]

        def _ai_warm(ctx):
            from ai_providers import get_provider
            provider = get_provider()
            contacts = [{"name": c["name"], "title": c.get("title"), "strength": c.get("relationship_strength")}
                        for c in (ctx["r"]["direct"] + ctx["r"]["same_sector"])[:8]]
            result = provider.generate_content("networking_strategy", {
                "target_company": ctx["r"]["company"],
                "sector": ctx["r"]["sector"],
                "contacts": contacts,
            })
            base = ctx["r"]
            base["ai_approach_strategy"] = result.get("content", "")
            return base

        return route_inference(
            task="find_warm_paths",
            context={"r": python_result},
            python_fallback=_python_warm,
            ai_handler=_ai_warm,
        )

    @mcp.tool()
    def import_linkedin_connections(connections: list) -> dict:
        """Import LinkedIn connections as contacts.

        Creates contacts with source='linkedin', deduplicates by name+company,
        and links to existing companies where possible.

        Args:
            connections: List of dicts with keys: name, company, title, connected_on

        Returns:
            dict with imported count, skipped_duplicates, companies_linked
        """
        imported = 0
        skipped = 0
        companies_linked = 0

        for conn in connections:
            name = conn.get("name", "").strip()
            company = conn.get("company", "").strip()
            title = conn.get("title", "").strip()
            connected_on = conn.get("connected_on")

            if not name:
                continue

            existing = db.query_one(
                "SELECT id FROM contacts WHERE name ILIKE %s AND company ILIKE %s",
                (name, company if company else ""),
            )
            if existing:
                skipped += 1
                continue

            company_id = None
            if company:
                co = db.query_one(
                    "SELECT id FROM companies WHERE name ILIKE %s", (company,)
                )
                if co:
                    company_id = co["id"]
                    companies_linked += 1

            db.execute_returning(
                """
                INSERT INTO contacts (name, company, company_id, title, source, last_contact)
                VALUES (%s, %s, %s, %s, 'linkedin', %s)
                RETURNING id
                """,
                (name, company, company_id, title, connected_on),
            )
            imported += 1

        return {
            "imported": imported,
            "skipped_duplicates": skipped,
            "companies_linked": companies_linked,
        }

    @mcp.tool()
    def import_linkedin_profile(positions: list, skills: list | None = None) -> dict:
        """Import career history and skills from LinkedIn profile data.

        Creates career_history records for unknown positions, extracts bullets
        from descriptions, and adds new skills.

        Args:
            positions: List of dicts with keys: title, company, start_date, end_date, description
            skills: Optional list of skill name strings

        Returns:
            dict with positions_added, bullets_extracted, skills_added
        """
        skills = skills or []
        positions_added = 0
        bullets_extracted = 0
        skills_added = 0

        for pos in positions:
            title = pos.get("title", "").strip()
            company = pos.get("company", "").strip()
            start_date = pos.get("start_date")
            end_date = pos.get("end_date")
            description = pos.get("description", "")

            if not title or not company:
                continue

            existing = db.query_one(
                "SELECT id FROM career_history WHERE employer ILIKE %s AND title ILIKE %s",
                (company, title),
            )
            if existing:
                continue

            ch = db.execute_returning(
                """
                INSERT INTO career_history (employer, title, start_date, end_date)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (company, title, start_date, end_date),
            )
            positions_added += 1

            if description and ch:
                lines = [
                    line.strip().lstrip("-").lstrip("*").lstrip("•").strip()
                    for line in description.split("\n")
                    if line.strip() and len(line.strip()) > 10
                ]
                for line in lines:
                    db.execute_returning(
                        """
                        INSERT INTO bullets (career_history_id, text, type)
                        VALUES (%s, %s, 'achievement')
                        RETURNING id
                        """,
                        (ch["id"], line),
                    )
                    bullets_extracted += 1

        for skill_name in skills:
            skill_name = skill_name.strip()
            if not skill_name:
                continue
            existing = db.query_one(
                "SELECT id FROM skills WHERE name ILIKE %s", (skill_name,)
            )
            if existing:
                continue
            db.execute_returning(
                """
                INSERT INTO skills (name, category, proficiency)
                VALUES (%s, 'linkedin_import', 'intermediate')
                RETURNING id
                """,
                (skill_name,),
            )
            skills_added += 1

        return {
            "positions_added": positions_added,
            "bullets_extracted": bullets_extracted,
            "skills_added": skills_added,
        }
