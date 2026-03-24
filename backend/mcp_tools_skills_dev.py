"""MCP tool functions for skills development & certification planning.

Orchestrator note: call register_skills_dev_tools(mcp) in mcp_server.py.
"""

from __future__ import annotations

import json
from collections import Counter

import db
from ai_providers.router import route_inference


def register_skills_dev_tools(mcp):
    """Register all skills development MCP tools with the given MCP server instance."""

    @mcp.tool()
    def get_skill_gaps() -> dict:
        """Analyse skill gaps across all stored gap analyses.

        Compares skills mentioned in gap_analyses.gaps against the user's
        skills table. Categorises each gap as not_showcased, adjacent, or
        deep_gap.

        Returns:
            dict with gaps list and coverage_pct
        """
        gap_rows = db.query(
            "SELECT id, gaps FROM gap_analyses WHERE gaps IS NOT NULL"
        )
        user_rows = db.query("SELECT LOWER(name) AS name FROM skills")
        user_skills = {r["name"] for r in user_rows}

        gap_counter = Counter()
        for row in gap_rows:
            data = row["gaps"]
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(data, list):
                for item in data:
                    name = item.get("skill") or item.get("name") or (item if isinstance(item, str) else "")
                    if name:
                        gap_counter[name.strip()] += 1
            elif isinstance(data, dict):
                for name in data.keys():
                    gap_counter[name.strip()] += 1

        def _cat(skill):
            sl = skill.lower()
            if sl in user_skills:
                return "not_showcased"
            for us in user_skills:
                if len(us) > 3 and (us in sl or sl in us):
                    return "adjacent"
            return "deep_gap"

        rec_map = {
            "not_showcased": "Add to resume — you already have this skill",
            "adjacent": "Upskill — you have a related skill",
            "deep_gap": "Learning required — new skill area",
        }

        results = []
        for skill, count in gap_counter.most_common():
            cat = _cat(skill)
            results.append({
                "skill": skill, "category": cat,
                "jd_count": count, "recommendation": rec_map[cat],
            })

        total = len(gap_counter)
        covered = sum(1 for r in results if r["category"] == "not_showcased")
        pct = round(covered / total * 100, 1) if total else 0

        python_result = {"gaps": results, "coverage_pct": pct}

        def _python_gaps(ctx):
            return ctx["r"]

        def _ai_gaps(ctx):
            from ai_providers import get_provider
            provider = get_provider()
            gap_names = [g["skill"] for g in ctx["r"]["gaps"][:15]]
            result = provider.analyze_skills(list(user_skills), [f"Required: {', '.join(gap_names)}"])
            base = ctx["r"]
            base["ai_recommendations"] = result.get("recommendations", [])
            return base

        return route_inference(
            task="skill_gap_analysis",
            context={"r": python_result},
            python_fallback=_python_gaps,
            ai_handler=_ai_gaps,
        )

    @mcp.tool()
    def get_skill_trends() -> dict:
        """Analyse skill demand trends across saved JDs and gap analyses.

        Returns:
            dict with trending skills, rising (unowned) skills, and user_coverage_pct
        """
        user_rows = db.query("SELECT LOWER(name) AS name FROM skills")
        user_skills = {r["name"] for r in user_rows}
        counter = Counter()

        ga_rows = db.query("SELECT jd_parsed, gaps FROM gap_analyses")
        for row in ga_rows:
            for field in ("jd_parsed", "gaps"):
                data = row.get(field)
                if not data:
                    continue
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except (json.JSONDecodeError, TypeError):
                        continue
                if isinstance(data, list):
                    for item in data:
                        name = item.get("skill") or item.get("name") or (item if isinstance(item, str) else "")
                        if name:
                            counter[name.strip().lower()] += 1
                elif isinstance(data, dict):
                    for k in data.keys():
                        counter[k.strip().lower()] += 1

        trending = []
        for skill, freq in counter.most_common(50):
            trending.append({
                "skill": skill, "frequency": freq,
                "have": skill in user_skills,
            })

        rising = [t for t in trending if not t["have"]][:15]
        total = len(trending)
        have_count = sum(1 for t in trending if t["have"])
        coverage = round(have_count / total * 100, 1) if total else 0

        python_result = {"trending": trending, "rising": rising, "user_coverage_pct": coverage}

        def _python_trends(ctx):
            return ctx["r"]

        def _ai_trends(ctx):
            from ai_providers import get_provider
            provider = get_provider()
            skill_names = list(user_skills)
            rising_names = [r["skill"] for r in ctx["r"]["rising"][:10]]
            result = provider.analyze_skills(skill_names, [f"Trending: {', '.join(rising_names)}"])
            base = ctx["r"]
            base["ai_emerging"] = result.get("emerging", [])
            base["ai_declining"] = result.get("declining", [])
            return base

        return route_inference(
            task="skill_trend_analysis",
            context={"r": python_result},
            python_fallback=_python_trends,
            ai_handler=_ai_trends,
        )

    @mcp.tool()
    def certification_roi(role_type: str | None = None) -> dict:
        """Analyse certification ROI based on JD frequency.

        Args:
            role_type: Optional role type filter (e.g. 'engineering manager')

        Returns:
            dict with recommendations list ranked by priority
        """
        cert_patterns = [
            "PMP", "AWS", "Azure", "GCP", "Kubernetes", "CKAD", "CKA",
            "Scrum", "CSM", "CSPO", "SAFe", "ITIL", "Six Sigma",
            "CISSP", "CISM", "CompTIA", "Security+", "TOGAF",
            "Google Cloud", "Terraform", "Docker", "CCNA", "CCNP",
            "PMI-ACP", "Prince2", "Lean", "Agile", "MBA", "PhD",
            "Certified", "Certification",
        ]

        if role_type:
            jd_rows = db.query(
                "SELECT jd_text, fit_score FROM saved_jobs WHERE jd_text IS NOT NULL AND LOWER(title) LIKE %s",
                (f"%{role_type.lower()}%",),
            )
        else:
            jd_rows = db.query(
                "SELECT jd_text, fit_score FROM saved_jobs WHERE jd_text IS NOT NULL"
            )

        cert_counter = Counter()
        for row in jd_rows:
            jd_lower = row["jd_text"].lower()
            for pat in cert_patterns:
                if pat.lower() in jd_lower:
                    cert_counter[pat] += 1

        existing = db.query("SELECT LOWER(name) AS name FROM certifications WHERE is_active = TRUE")
        existing_names = {r["name"] for r in existing}

        recs = []
        for cert, freq in cert_counter.most_common():
            have = any(cert.lower() in en for en in existing_names)
            recs.append({
                "cert_name": cert, "jd_frequency": freq, "have": have,
                "estimated_unlock": freq if not have else 0,
                "priority": 1 if freq >= 5 and not have else (2 if freq >= 2 and not have else 3),
            })

        python_result = {"recommendations": recs}

        def _python_cert(ctx):
            return ctx["r"]

        def _ai_cert(ctx):
            from ai_providers import get_provider
            provider = get_provider()
            top_certs = [r["cert_name"] for r in ctx["r"]["recommendations"][:10] if not r["have"]]
            result = provider.generate_content("certification_advice", {
                "certs_to_evaluate": top_certs,
                "role_type": ctx.get("role_type"),
            })
            base = ctx["r"]
            base["ai_advice"] = result.get("content", "")
            return base

        return route_inference(
            task="certification_roi",
            context={"r": python_result, "role_type": role_type},
            python_fallback=_python_cert,
            ai_handler=_ai_cert,
        )

    @mcp.tool()
    def get_differentiator_analysis() -> dict:
        """Analyse user's unique skill combinations as competitive differentiators.

        Identifies cross-category expertise combinations and expert-level skills,
        plus the top skill gaps that would unlock the most JDs.

        Returns:
            dict with differentiators list and gaps_to_unlock list
        """
        user_skills_rows = db.query("SELECT name, category, proficiency FROM skills")
        user_skills = {r["name"].lower() for r in user_skills_rows}

        by_category = {}
        for r in user_skills_rows:
            by_category.setdefault(r.get("category", "other"), []).append(r["name"])

        differentiators = []
        categories = list(by_category.keys())
        for i, cat1 in enumerate(categories):
            for cat2 in categories[i + 1:]:
                combo_label = f"{cat1.title()} + {cat2.title()}"
                examples = by_category[cat1][:2] + by_category[cat2][:2]
                differentiators.append({
                    "combo": combo_label, "skills": examples,
                    "rarity_note": f"Cross-domain expertise in {cat1} and {cat2}",
                })

        experts = [r for r in user_skills_rows if r.get("proficiency") == "expert"]
        for e in experts:
            differentiators.append({
                "combo": f"Expert: {e['name']}", "skills": [e["name"]],
                "rarity_note": f"Expert-level {e.get('category', '')} skill",
            })

        gap_rows = db.query("SELECT gaps FROM gap_analyses WHERE gaps IS NOT NULL")
        gap_counter = Counter()
        for row in gap_rows:
            data = row["gaps"]
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(data, list):
                for item in data:
                    name = item.get("skill") or item.get("name") or (item if isinstance(item, str) else "")
                    if name and name.lower() not in user_skills:
                        gap_counter[name.strip()] += 1
            elif isinstance(data, dict):
                for name in data.keys():
                    if name.lower() not in user_skills:
                        gap_counter[name.strip()] += 1

        gaps_to_unlock = [
            {"skill": s, "unlock_count": c}
            for s, c in gap_counter.most_common(10)
        ]

        python_result = {"differentiators": differentiators[:15], "gaps_to_unlock": gaps_to_unlock}

        def _python_diff(ctx):
            return ctx["r"]

        def _ai_diff(ctx):
            from ai_providers import get_provider
            provider = get_provider()
            result = provider.generate_content("differentiator_analysis", {
                "differentiators": [d["combo"] for d in ctx["r"]["differentiators"][:5]],
                "gaps": [g["skill"] for g in ctx["r"]["gaps_to_unlock"][:5]],
            })
            base = ctx["r"]
            base["ai_narrative"] = result.get("content", "")
            return base

        return route_inference(
            task="differentiator_analysis",
            context={"r": python_result},
            python_fallback=_python_diff,
            ai_handler=_ai_diff,
        )

    @mcp.tool()
    def get_learning_path(top_n: int = 10) -> dict:
        """Generate learning path recommendations based on skill gaps and certification ROI.

        Combines gap analysis data with learning_plans and certifications to
        produce a prioritized action plan: quick wins first, then investments.

        Args:
            top_n: Maximum number of gap skills to surface (default 10)

        Returns:
            dict with learning_path list and existing_plans list
        """
        # Collect gap skills from gap_analyses
        gap_rows = db.query(
            "SELECT id, gaps FROM gap_analyses WHERE gaps IS NOT NULL"
        )
        user_rows = db.query("SELECT LOWER(name) AS name, category, proficiency FROM skills")
        user_skills = {r["name"] for r in user_rows}

        gap_counter: Counter = Counter()
        for row in gap_rows:
            data = row["gaps"]
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(data, list):
                for item in data:
                    name = item.get("skill") or item.get("name") or (item if isinstance(item, str) else "")
                    if name and name.lower() not in user_skills:
                        gap_counter[name.strip()] += 1
            elif isinstance(data, dict):
                for name in data.keys():
                    if name.lower() not in user_skills:
                        gap_counter[name.strip()] += 1

        # Existing learning plans
        plans = db.query(
            "SELECT id, title, status, target_date, notes FROM learning_plans ORDER BY created_at DESC"
        )
        plan_titles_lower = {p["title"].lower() for p in plans}

        # Build recommendations
        resource_map = {
            "aws": "AWS Skill Builder (free tier) + Udemy AWS SAA-C03",
            "azure": "Microsoft Learn (free) + AZ-900 prep",
            "gcp": "Google Cloud Skills Boost",
            "kubernetes": "KodeKloud free tier + CKA exam prep",
            "python": "Real Python, Python.org tutorials",
            "terraform": "HashiCorp Learn (free)",
            "docker": "Play With Docker + Docker Docs",
            "sql": "Mode Analytics SQL Tutorial (free)",
            "machine learning": "fast.ai (free) + Coursera ML Specialization",
            "data analysis": "Kaggle Learn (free)",
            "react": "react.dev official docs + Scrimba",
            "typescript": "TypeScript Handbook (free)",
            "scrum": "Scrum.org free learning path + PSM I",
            "pmp": "PMI PMBOK + Andrew Ramdayal Udemy course",
            "agile": "Atlassian Agile Coach (free)",
        }

        path = []
        for skill, jd_count in gap_counter.most_common(top_n):
            sl = skill.lower()
            # Check adjacency
            adjacent = []
            for r in user_rows:
                us = r["name"]
                if len(us) > 3 and (us in sl or sl in us):
                    adjacent.append(r["name"])

            resource = None
            for key, res in resource_map.items():
                if key in sl:
                    resource = res
                    break

            already_planned = sl in plan_titles_lower or any(sl in pt for pt in plan_titles_lower)

            path.append({
                "skill": skill,
                "jd_demand": jd_count,
                "difficulty": "quick_win" if adjacent else "investment",
                "adjacent_skills_you_have": adjacent[:3],
                "suggested_resources": resource or "Search Coursera, LinkedIn Learning, or official docs",
                "already_planned": already_planned,
                "action": "Add to learning plan" if not already_planned else "In progress",
            })

        python_result = {
            "learning_path": path,
            "existing_plans": plans,
            "total_gaps_found": len(gap_counter),
        }

        def _python_learn(ctx):
            return ctx["r"]

        def _ai_learn(ctx):
            from ai_providers import get_provider
            provider = get_provider()
            skills_to_learn = [p["skill"] for p in ctx["r"]["learning_path"][:5]]
            result = provider.generate_content("learning_path", {
                "skills_to_learn": skills_to_learn,
                "existing_skills": list(user_skills)[:20],
            })
            base = ctx["r"]
            base["ai_learning_narrative"] = result.get("content", "")
            return base

        return route_inference(
            task="learning_path_generation",
            context={"r": python_result},
            python_fallback=_python_learn,
            ai_handler=_ai_learn,
        )

    @mcp.tool()
    def check_skill_trend_alerts() -> dict:
        """Check for trending skills the user lacks and create notifications for new ones.

        Compares market_signals skill mentions against user's skills table.
        Creates a notification for each newly-trending skill not yet notified.

        Returns:
            dict with alerts_created count and alert list
        """
        user_rows = db.query("SELECT LOWER(name) AS name FROM skills")
        user_skills = {r["name"] for r in user_rows}

        # Pull recent market signals with skill references
        signals = db.query(
            """
            SELECT id, skill, signal_type, source, created_at
            FROM market_signals
            WHERE skill IS NOT NULL
              AND created_at >= NOW() - INTERVAL '30 days'
            ORDER BY created_at DESC
            """
        )

        if not signals:
            return {"alerts_created": 0, "alerts": [], "message": "No recent market signals found"}

        # Count skill demand from signals
        skill_counter: Counter = Counter()
        for sig in signals:
            sk = sig.get("skill", "").strip().lower()
            if sk:
                skill_counter[sk] += 1

        # Determine which trending skills the user lacks and hasn't been alerted about
        existing_alert_types = db.query(
            """
            SELECT DISTINCT title FROM notifications
            WHERE type = 'skill_trend'
              AND created_at >= NOW() - INTERVAL '7 days'
            """
        )
        recently_alerted = {r["title"].lower() for r in existing_alert_types}

        alerts_created = []
        for skill, freq in skill_counter.most_common(20):
            if skill in user_skills:
                continue  # User already has this skill
            alert_title = f"Trending skill: {skill.title()}"
            if alert_title.lower() in recently_alerted:
                continue  # Already notified this week

            db.execute(
                """
                INSERT INTO notifications (type, severity, title, body, entity_type)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    "skill_trend",
                    "info",
                    alert_title,
                    f"'{skill.title()}' appears in {freq} recent market signal(s). Consider adding to your learning plan.",
                    "skill",
                ),
            )
            db.execute(
                """
                INSERT INTO activity_log (action, entity_type, details)
                VALUES (%s, %s, %s)
                """,
                (
                    "skill_trend_alert_created",
                    "skill",
                    json.dumps({"skill": skill, "signal_count": freq}),
                ),
            )
            alerts_created.append({"skill": skill, "signal_count": freq, "alert": alert_title})

        return {
            "alerts_created": len(alerts_created),
            "alerts": alerts_created,
            "skills_checked": len(skill_counter),
        }

    @mcp.tool()
    def link_skill_evidence(skill_id: int, bullet_ids: list[int]) -> dict:
        """Link bullets as evidence for a skill.

        Updates skills.bullet_ids (array) to include the given bullet IDs,
        deduplicating against any already linked.

        Args:
            skill_id: ID of the skill to update
            bullet_ids: List of bullet IDs that demonstrate this skill

        Returns:
            dict with updated skill record
        """
        existing = db.query_one("SELECT id, name, bullet_ids FROM skills WHERE id = %s", (skill_id,))
        if not existing:
            return {"error": f"Skill {skill_id} not found"}

        current_ids = existing.get("bullet_ids") or []
        if isinstance(current_ids, str):
            try:
                current_ids = json.loads(current_ids)
            except (json.JSONDecodeError, TypeError):
                current_ids = []

        merged = list({*current_ids, *bullet_ids})

        updated = db.execute_returning(
            "UPDATE skills SET bullet_ids = %s WHERE id = %s RETURNING *",
            (merged, skill_id),
        )

        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, details) VALUES (%s, %s, %s, %s)",
            (
                "skill_evidence_linked",
                "skill",
                skill_id,
                json.dumps({"bullet_ids_added": bullet_ids, "total_linked": len(merged)}),
            ),
        )

        return {"skill": updated, "bullet_ids_linked": merged, "count": len(merged)}

    @mcp.tool()
    def get_skill_evidence(skill_id: int) -> dict:
        """Get bullets linked as evidence for a skill.

        Args:
            skill_id: ID of the skill

        Returns:
            dict with skill name and linked bullet texts
        """
        skill = db.query_one("SELECT id, name, category, proficiency, bullet_ids FROM skills WHERE id = %s", (skill_id,))
        if not skill:
            return {"error": f"Skill {skill_id} not found"}

        bullet_ids = skill.get("bullet_ids") or []
        if isinstance(bullet_ids, str):
            try:
                bullet_ids = json.loads(bullet_ids)
            except (json.JSONDecodeError, TypeError):
                bullet_ids = []

        bullets = []
        if bullet_ids:
            bullets = db.query(
                """
                SELECT b.id, b.text, b.type, b.tags, ch.employer, ch.title AS role_title
                FROM bullets b
                LEFT JOIN career_history ch ON ch.id = b.career_history_id
                WHERE b.id = ANY(%s)
                ORDER BY b.id
                """,
                (bullet_ids,),
            )

        return {
            "skill_id": skill_id,
            "skill_name": skill["name"],
            "category": skill.get("category"),
            "proficiency": skill.get("proficiency"),
            "evidence_count": len(bullets),
            "bullets": bullets,
        }
