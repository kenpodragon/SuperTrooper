"""MCP tool functions for career knowledge base: bullets, career history, skills, JD matching,
salary data, voice rules, candidate profile, and resume data.

Orchestrator note: call register_knowledge_tools(mcp) in mcp_server.py.
"""

from __future__ import annotations

import re
import sys
import os
from collections import Counter
from pathlib import Path

import db
from ai_providers.router import route_inference


def register_knowledge_tools(mcp):
    """Register all knowledge-base MCP tools with the given MCP server instance."""

    @mcp.tool()
    def search_bullets(
        query: str = "",
        tags: list[str] | None = None,
        role_type: str = "",
        industry: str = "",
        limit: int = 20,
    ) -> dict:
        """Search resume bullets by text, tags, role_type, or industry.

        Args:
            query: Text to search for in bullet text (ILIKE).
            tags: List of tags to filter by (array overlap).
            role_type: Filter by role suitability (e.g. CTO, VP Eng, Director).
            industry: Filter by industry suitability (e.g. defense, manufacturing).
            limit: Max results to return (default 20).
        """
        clauses, params = [], []
        if query:
            clauses.append("b.text ILIKE %s")
            params.append(f"%{query}%")
        if tags:
            clauses.append("b.tags && %s")
            params.append(tags)
        if role_type:
            clauses.append("%s = ANY(b.role_suitability)")
            params.append(role_type)
        if industry:
            clauses.append("%s = ANY(b.industry_suitability)")
            params.append(industry)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = db.query(
            f"""
            SELECT b.id, b.text, b.type, b.tags, b.role_suitability,
                   b.industry_suitability, b.metrics_json, b.detail_recall,
                   ch.employer, ch.title
            FROM bullets b
            LEFT JOIN career_history ch ON ch.id = b.career_history_id
            {where}
            ORDER BY b.id
            LIMIT %s
            """,
            params + [limit],
        )
        return {"count": len(rows), "bullets": rows}

    @mcp.tool()
    def get_career_history(employer: str = "") -> dict:
        """Get career history for an employer (or all if blank).

        Args:
            employer: Employer name to search (ILIKE match). Leave blank for all.
        """
        if employer:
            rows = db.query(
                """
                SELECT ch.*, array_agg(json_build_object(
                    'id', b.id, 'text', b.text, 'type', b.type, 'tags', b.tags
                )) FILTER (WHERE b.id IS NOT NULL) AS bullets
                FROM career_history ch
                LEFT JOIN bullets b ON b.career_history_id = ch.id
                WHERE ch.employer ILIKE %s
                GROUP BY ch.id
                ORDER BY ch.start_date DESC NULLS LAST
                """,
                (f"%{employer}%",),
            )
        else:
            rows = db.query(
                """
                SELECT id, employer, title, start_date, end_date, location,
                       industry, team_size, budget_usd, revenue_impact, is_current
                FROM career_history
                ORDER BY start_date DESC NULLS LAST
                """
            )
        return {"count": len(rows), "career_history": rows}

    @mcp.tool()
    def get_summary_variant(role_type: str) -> dict:
        """Get a professional summary variant for a target role type.

        Args:
            role_type: Target role (e.g. CTO, VP Eng, Director, AI Architect, SW Architect, PM, Sr SWE).
        """
        row = db.query_one(
            "SELECT id, role_type, text, updated_at FROM summary_variants WHERE role_type = %s",
            (role_type,),
        )
        if not row:
            row = db.query_one(
                "SELECT id, role_type, text, updated_at FROM summary_variants WHERE role_type ILIKE %s",
                (f"%{role_type}%",),
            )
        return row or {"error": f"No summary variant found for role_type '{role_type}'"}

    @mcp.tool()
    def get_skills(category: str = "") -> dict:
        """List skills, optionally filtered by category.

        Args:
            category: Skill category filter (language, framework, platform, methodology, tool).
        """
        if category:
            rows = db.query(
                "SELECT id, name, category, proficiency, last_used_year FROM skills WHERE category = %s ORDER BY name",
                (category,),
            )
        else:
            rows = db.query(
                "SELECT id, name, category, proficiency, last_used_year FROM skills ORDER BY category, name"
            )
        return {"count": len(rows), "skills": rows}

    @mcp.tool()
    def match_jd(jd_text: str) -> dict:
        """Match a job description against resume bullets. Returns best matches and gaps.

        Args:
            jd_text: Full job description text to analyze.
        """
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "shall", "can", "need", "must",
            "that", "this", "these", "those", "it", "its", "we", "our", "you",
            "your", "they", "their", "them", "he", "she", "his", "her", "as",
            "if", "not", "no", "so", "up", "out", "about", "into", "over",
            "after", "before", "between", "through", "during", "such", "each",
            "which", "who", "whom", "what", "where", "when", "how", "all", "any",
            "both", "few", "more", "most", "other", "some", "than", "too", "very",
            "just", "also", "well", "able", "etc", "including", "experience",
            "work", "working", "role", "position", "team", "company", "years",
            "strong", "required", "preferred", "requirements", "qualifications",
            "responsibilities", "job", "description", "candidate", "ideal",
        }

        words = re.findall(r"[a-z][a-z+#/.]+", jd_text.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        top_keywords = [k for k, _ in Counter(keywords).most_common(30)]

        matched_bullets = []
        seen_ids = set()
        for kw in top_keywords[:15]:
            rows = db.query(
                """
                SELECT b.id, b.text, b.type, b.tags, b.role_suitability,
                       ch.employer, ch.title
                FROM bullets b
                LEFT JOIN career_history ch ON ch.id = b.career_history_id
                WHERE b.text ILIKE %s
                LIMIT 5
                """,
                (f"%{kw}%",),
            )
            for row in rows:
                if row["id"] not in seen_ids:
                    seen_ids.add(row["id"])
                    row["matched_keyword"] = kw
                    matched_bullets.append(row)

        matched_skills = []
        for kw in top_keywords:
            skills = db.query(
                "SELECT id, name, category, proficiency FROM skills WHERE name ILIKE %s",
                (f"%{kw}%",),
            )
            for s in skills:
                if s["id"] not in {ms["id"] for ms in matched_skills}:
                    s["matched_keyword"] = kw
                    matched_skills.append(s)

        covered = {b["matched_keyword"] for b in matched_bullets} | {s["matched_keyword"] for s in matched_skills}
        gaps = [kw for kw in top_keywords if kw not in covered]

        python_result = {
            "jd_keywords": top_keywords,
            "matched_bullets": matched_bullets[:30],
            "matched_skills": matched_skills,
            "gaps": gaps,
            "coverage_pct": round(len(covered) / max(len(top_keywords), 1) * 100, 1),
        }

        def _python_match(ctx):
            return ctx["python_result"]

        def _ai_match(ctx):
            from ai_providers import get_provider
            provider = get_provider()
            resume_text = "\n".join(b["text"] for b in ctx["python_result"]["matched_bullets"][:10])
            result = provider.semantic_match(resume_text=resume_text, jd_text=ctx["jd_text"][:3000])
            base = ctx["python_result"]
            base["semantic_score"] = result.get("match_score", 0)
            base["aligned_themes"] = result.get("aligned_themes", [])
            base["positioning_suggestions"] = result.get("positioning_suggestions", [])
            return base

        return route_inference(
            task="match_jd_semantic",
            context={"python_result": python_result, "jd_text": jd_text},
            python_fallback=_python_match,
            ai_handler=_ai_match,
        )

    @mcp.tool()
    def get_candidate_profile(section: str = "", format: str = "sections") -> dict:
        """Get candidate profile data. Returns full profile or specific sections.

        Args:
            section: Filter by section name (e.g. "Identity", "Career Narrative", "Target Roles", "Compensation", "References"). Leave blank for all.
            format: "sections" for structured data, "text" for reconstructed markdown.
        """
        return _get_content_document("candidate_profile", section, format)

    @mcp.tool()
    def get_rejection_analysis(section: str = "", format: str = "sections") -> dict:
        """Get rejection and ghosting analysis data.

        Args:
            section: Filter by section (e.g. "Companies with Confirmed Interview Activity", "Pattern Analysis"). Leave blank for all.
            format: "sections" for structured data, "text" for reconstructed markdown.
        """
        return _get_content_document("rejection_analysis", section, format)

    @mcp.tool()
    def get_voice_rules(category: str = "", part: int = 0, format: str = "rules") -> dict:
        """Get voice guide rules for content generation. Use to check writing quality.

        Args:
            category: Filter by rule type: banned_word, banned_construction, caution_word, structural_tell, resume_rule, cover_letter_rule, final_check, linkedin_pattern, stephen_ism, context_pattern, quick_reference. Leave blank for all.
            part: Filter by Voice Guide part number (1-8). 0 = all parts.
            format: "rules" for structured data, "text" for reconstructed guide.
        """
        clauses, params = [], []
        if category:
            clauses.append("category = %s")
            params.append(category)
        if part:
            clauses.append("part = %s")
            params.append(part)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = db.query(
            f"""
            SELECT id, part, part_title, category, subcategory, rule_text,
                   explanation, examples_bad, examples_good
            FROM voice_rules
            {where}
            ORDER BY sort_order
            """,
            params,
        )

        if format == "text":
            parts = {}
            for row in rows:
                key = f"Part {row['part']}: {row['part_title']}"
                if key not in parts:
                    parts[key] = []
                parts[key].append(row)

            text_parts = []
            for key, rules_list in parts.items():
                text_parts.append(f"## {key}\n")
                for r in rules_list:
                    if r["category"] == "banned_word":
                        text_parts.append(f"- {r['rule_text']}")
                    else:
                        text_parts.append(f"### {r['rule_text']}")
                        if r["explanation"]:
                            text_parts.append(r["explanation"])
                    text_parts.append("")
            return {"text": "\n".join(text_parts), "rule_count": len(rows)}

        return {"count": len(rows), "rules": rows}

    @mcp.tool()
    def check_voice(text: str) -> dict:
        """Check text against voice guide banned words and constructions. Returns violations.

        Args:
            text: The text to check against voice rules.
        """
        text_lower = text.lower()
        violations = []

        banned_words = db.query(
            "SELECT rule_text, subcategory FROM voice_rules WHERE category = 'banned_word'"
        )
        for bw in banned_words:
            word = bw["rule_text"].lower()
            if word in text_lower:
                violations.append({
                    "type": "banned_word",
                    "match": bw["rule_text"],
                    "subcategory": bw["subcategory"],
                })

        banned_constructions = db.query(
            "SELECT rule_text, subcategory, explanation FROM voice_rules WHERE category = 'banned_construction'"
        )
        for bc in banned_constructions:
            pattern = bc["rule_text"].lower()
            if pattern in text_lower:
                violations.append({
                    "type": "banned_construction",
                    "match": bc["rule_text"],
                    "subcategory": bc["subcategory"],
                    "explanation": bc["explanation"],
                })

        python_result = {
            "text_length": len(text),
            "violations": violations,
            "violation_count": len(violations),
            "clean": len(violations) == 0,
        }

        def _python_voice(ctx):
            return ctx["python_result"]

        def _ai_voice(ctx):
            from ai_providers import get_provider
            provider = get_provider()
            rules_list = [{"rule_text": v["match"], "category": v["type"]} for v in ctx["python_result"]["violations"]]
            all_rules = db.query("SELECT rule_text, category FROM voice_rules WHERE category IN ('banned_word', 'banned_construction') LIMIT 50")
            result = provider.check_voice_ai(ctx["text"], [{"rule_text": r["rule_text"], "category": r["category"]} for r in all_rules])
            base = ctx["python_result"]
            ai_violations = result.get("violations", [])
            if ai_violations:
                existing_matches = {v["match"].lower() for v in base["violations"]}
                for av in ai_violations:
                    if av.get("text", "").lower() not in existing_matches:
                        base["violations"].append({
                            "type": "ai_detected",
                            "match": av.get("text", ""),
                            "subcategory": av.get("rule", ""),
                            "suggestion": av.get("suggestion", ""),
                        })
                base["violation_count"] = len(base["violations"])
                base["clean"] = len(base["violations"]) == 0
            base["ai_voice_score"] = result.get("overall_score", 1.0)
            return base

        return route_inference(
            task="check_voice_ai",
            context={"python_result": python_result, "text": text},
            python_fallback=_python_voice,
            ai_handler=_ai_voice,
        )

    @mcp.tool()
    def get_salary_data(role: str = "", tier: int = 0) -> dict:
        """Get salary benchmarks and COLA market data for target roles.

        Args:
            role: Search by role title (e.g. "CTO", "VP", "Director"). Leave blank for all.
            tier: Filter by tier (1=Executive, 2=Director, 3=Senior IC, 4=PM, 5=Academia). 0 = all.
        """
        clauses, params = [], []
        if role:
            clauses.append("role_title ILIKE %s")
            params.append(f"%{role}%")
        if tier:
            clauses.append("tier = %s")
            params.append(tier)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        benchmarks = db.query(
            f"""
            SELECT role_title, tier, tier_name, national_median_range,
                   melbourne_range, remote_range, hcol_range, target_realistic
            FROM salary_benchmarks
            {where}
            ORDER BY sort_order
            """,
            params,
        )

        markets = db.query(
            "SELECT market_name, col_index_approx, cola_factor, melbourne_200k_equiv, melbourne_250k_equiv FROM cola_markets ORDER BY cola_factor"
        )

        return {
            "benchmarks": benchmarks,
            "benchmark_count": len(benchmarks),
            "cola_markets": markets,
            "cola_formula": "Melbourne-equivalent = Posted Salary x (97 / Market COL Index)",
        }

    @mcp.tool()
    def get_resume_data(version: str = "v32", variant: str = "base", section: str = "") -> dict:
        """Get full resume data for reconstruction or querying. Returns header, spec, experience, education, certs.

        Args:
            version: Resume version (default v32).
            variant: Resume variant (default base).
            section: Optional filter: "header", "education", "certifications", "experience", "spec", "keywords". Leave blank for all.
        """
        import json as _json

        if section == "header":
            return db.query_one("SELECT * FROM resume_header LIMIT 1") or {"error": "No header"}

        if section == "education":
            rows = db.query("SELECT * FROM education ORDER BY sort_order")
            return {"education": rows, "count": len(rows)}

        if section == "certifications":
            rows = db.query("SELECT * FROM certifications WHERE is_active = TRUE ORDER BY sort_order")
            return {"certifications": rows, "count": len(rows)}

        rv = db.query_one(
            "SELECT * FROM resume_versions WHERE version = %s AND variant = %s AND spec IS NOT NULL",
            (version, variant),
        )
        if not rv:
            return {"error": f"No spec found for {version}/{variant}"}

        spec = rv["spec"] if isinstance(rv["spec"], dict) else _json.loads(rv["spec"])

        if section == "spec":
            return {"version": version, "variant": variant, "spec": spec}

        if section == "keywords":
            return {
                "keywords": spec.get("keywords", []),
                "executive_keywords": spec.get("executive_keywords", []),
                "technical_keywords": spec.get("technical_keywords", []),
            }

        if section == "experience":
            experience = []
            for employer_name in spec.get("experience_employers", []):
                ch = db.query_one(
                    "SELECT * FROM career_history WHERE employer ILIKE %s",
                    (f"%{employer_name}%",),
                )
                if ch:
                    bullets = db.query(
                        "SELECT id, text, type, tags FROM bullets WHERE career_history_id = %s ORDER BY id",
                        (ch["id"],),
                    )
                    ch["bullets"] = bullets
                    experience.append(ch)
            return {"experience": experience, "count": len(experience)}

        # Full data
        header = db.query_one("SELECT * FROM resume_header LIMIT 1")
        education = db.query("SELECT * FROM education ORDER BY sort_order")
        certifications = db.query("SELECT * FROM certifications WHERE is_active = TRUE ORDER BY sort_order")

        experience = []
        for employer_name in spec.get("experience_employers", []):
            ch = db.query_one(
                "SELECT * FROM career_history WHERE employer ILIKE %s",
                (f"%{employer_name}%",),
            )
            if ch:
                bullets = db.query(
                    "SELECT id, text, type, tags FROM bullets WHERE career_history_id = %s ORDER BY id",
                    (ch["id"],),
                )
                ch["bullets"] = bullets
                experience.append(ch)

        return {
            "version": version,
            "variant": variant,
            "header": header,
            "spec": spec,
            "experience": experience,
            "education": education,
            "certifications": certifications,
        }


def _get_content_document(doc_name: str, section: str, format: str) -> dict:
    """Shared helper for content section retrieval."""
    clauses = ["source_document = %s"]
    params = [doc_name]

    if section:
        clauses.append("(section ILIKE %s OR subsection ILIKE %s)")
        params.extend([f"%{section}%", f"%{section}%"])

    where = f"WHERE {' AND '.join(clauses)}"
    rows = db.query(
        f"""
        SELECT id, section, subsection, sort_order, content, content_format
        FROM content_sections
        {where}
        ORDER BY sort_order
        """,
        params,
    )

    if not rows:
        return {"error": f"No content found for '{doc_name}'" + (f" section '{section}'" if section else "")}

    if format == "text":
        parts = []
        for row in rows:
            if row["subsection"]:
                parts.append(f"### {row['subsection']}\n\n{row['content']}")
            else:
                parts.append(f"## {row['section']}\n\n{row['content']}")
        return {
            "document": doc_name,
            "text": "\n\n---\n\n".join(parts),
            "section_count": len(rows),
        }

    return {
        "document": doc_name,
        "sections": rows,
        "count": len(rows),
    }
