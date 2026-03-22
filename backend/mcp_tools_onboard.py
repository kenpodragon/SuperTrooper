"""MCP tool functions for onboarding status and next steps.

Orchestrator note: call register_onboard_tools(mcp) in mcp_server.py.
"""

from __future__ import annotations

import db


def register_onboard_tools(mcp):
    """Register all onboarding MCP tools with the given MCP server instance."""

    @mcp.tool()
    def get_onboard_status() -> dict:
        """Check onboarding completion status across all data categories.

        Returns:
            dict with boolean flags for each category, counts, and completion_percentage
        """
        bullets = db.query_one("SELECT COUNT(*) AS cnt FROM bullets")
        career = db.query_one("SELECT COUNT(*) AS cnt FROM career_history")
        contacts = db.query_one("SELECT COUNT(*) AS cnt FROM contacts")
        skills = db.query_one("SELECT COUNT(*) AS cnt FROM skills")
        recipes = db.query_one("SELECT COUNT(*) AS cnt FROM resume_recipes")
        templates = db.query_one("SELECT COUNT(*) AS cnt FROM resume_templates")
        settings = db.query_one("SELECT preferences FROM settings WHERE id = 1")

        bullets_count = bullets["cnt"] if bullets else 0
        career_count = career["cnt"] if career else 0
        contacts_count = contacts["cnt"] if contacts else 0
        skills_count = skills["cnt"] if skills else 0
        recipes_count = recipes["cnt"] if recipes else 0
        templates_count = templates["cnt"] if templates else 0

        prefs = (settings or {}).get("preferences") or {}
        has_profile = bool(prefs.get("candidate_name") or prefs.get("candidate_email"))

        checks = {
            "has_bullets": bullets_count > 0,
            "has_career_history": career_count > 0,
            "has_contacts": contacts_count > 0,
            "has_skills": skills_count > 0,
            "has_recipes": recipes_count > 0,
            "has_templates": templates_count > 0,
            "has_profile": has_profile,
        }

        completed = sum(1 for v in checks.values() if v)
        total = len(checks)
        completion_percentage = round(completed / total * 100, 1)

        return {
            **checks,
            "counts": {
                "bullets": bullets_count,
                "career_history": career_count,
                "contacts": contacts_count,
                "skills": skills_count,
                "recipes": recipes_count,
                "templates": templates_count,
            },
            "completion_percentage": completion_percentage,
        }

    @mcp.tool()
    def get_next_steps() -> dict:
        """Get ordered list of recommended onboarding actions based on current data status.

        Returns:
            dict with ordered list of next steps with priority, action, and detail
        """
        status = get_onboard_status()
        steps = []
        priority = 1

        if not status["has_profile"]:
            steps.append({
                "priority": priority,
                "action": "Set up your profile",
                "detail": "Add your name, email, target roles, and target locations via POST /api/onboard/quick-setup.",
                "endpoint": "POST /api/onboard/quick-setup",
            })
            priority += 1

        if not status["has_career_history"]:
            steps.append({
                "priority": priority,
                "action": "Upload your resume",
                "detail": "Upload a .docx or .pdf resume to populate your career history, bullets, and skills automatically.",
                "endpoint": "POST /api/onboard/upload",
                "tool": "onboard_resume",
            })
            priority += 1

        if not status["has_bullets"]:
            steps.append({
                "priority": priority,
                "action": "Add resume bullets",
                "detail": f"No bullets found. Upload a resume or add achievements manually with concrete metrics.",
                "tool": "search_bullets",
            })
            priority += 1

        if not status["has_skills"]:
            steps.append({
                "priority": priority,
                "action": "Populate your skills",
                "detail": "Add your technical and leadership skills to enable gap analysis and resume tailoring.",
                "tool": "get_skills",
            })
            priority += 1

        if not status["has_contacts"]:
            steps.append({
                "priority": priority,
                "action": "Add networking contacts",
                "detail": "Import contacts for warm introductions, referrals, and networking outreach.",
                "tool": "search_contacts",
            })
            priority += 1

        if not status["has_recipes"]:
            steps.append({
                "priority": priority,
                "action": "Create a resume recipe",
                "detail": "A recipe defines your resume structure. Upload a resume to auto-generate one, or create manually.",
                "tool": "create_recipe",
            })
            priority += 1

        if status["has_career_history"] and status["has_bullets"]:
            steps.append({
                "priority": priority,
                "action": "Run a gap analysis",
                "detail": "Paste a job description to see how well your profile matches and identify gaps.",
                "tool": "match_jd",
            })
            priority += 1

        if not steps:
            steps.append({
                "priority": 1,
                "action": "You're all set!",
                "detail": "All onboarding steps are complete. Start searching for jobs or generating tailored resumes.",
            })

        return {"next_steps": steps, "completion_percentage": status["completion_percentage"]}
