"""SuperTroopers MCP Server — exposes DB tools for Claude Code.

Run:  python mcp_server.py   # starts MCP server on stdio
"""

import sys
import os
import re
from collections import Counter
from pathlib import Path

# Ensure the backend directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP
import db

mcp = FastMCP(
    "supertroopers",
    instructions="SuperTroopers hiring platform database tools.",
    host="0.0.0.0",
    port=int(os.environ.get("MCP_PORT", 8056)),
)


# ---------------------------------------------------------------------------
# Career / Bullets / Skills
# ---------------------------------------------------------------------------

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
        # Try ILIKE fallback
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


# ---------------------------------------------------------------------------
# JD Matching / Gap Analysis
# ---------------------------------------------------------------------------

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

    return {
        "jd_keywords": top_keywords,
        "matched_bullets": matched_bullets[:30],
        "matched_skills": matched_skills,
        "gaps": gaps,
        "coverage_pct": round(len(covered) / max(len(top_keywords), 1) * 100, 1),
    }


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

@mcp.tool()
def search_applications(
    status: str = "",
    company: str = "",
    source: str = "",
    limit: int = 50,
) -> dict:
    """Search job applications by status, company, or source.

    Args:
        status: Filter by status (Applied, Interview, Rejected, etc.).
        company: Filter by company name (ILIKE match).
        source: Filter by source (Indeed, LinkedIn, etc.).
        limit: Max results (default 50).
    """
    clauses, params = [], []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if company:
        clauses.append("company_name ILIKE %s")
        params.append(f"%{company}%")
    if source:
        clauses.append("source = %s")
        params.append(source)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT id, company_id, company_name, role, date_applied, source, status,
               resume_version, jd_url, contact_name, notes,
               last_status_change, created_at
        FROM applications
        {where}
        ORDER BY date_applied DESC NULLS LAST
        LIMIT %s
        """,
        params + [limit],
    )
    return {"count": len(rows), "applications": rows}


@mcp.tool()
def add_application(
    company_name: str,
    role: str,
    source: str = "Direct",
    status: str = "Applied",
    notes: str = "",
    company_id: int | None = None,
    date_applied: str | None = None,
    jd_url: str = "",
    jd_text: str = "",
) -> dict:
    """Add a new job application to the tracker.

    Args:
        company_name: Company name.
        role: Job title / role applied for.
        source: Application source (Indeed, LinkedIn, Dice, ZipRecruiter, Direct, Recruiter, Referral).
        status: Initial status (default Applied).
        notes: Any notes.
        company_id: Optional company ID if known.
        date_applied: Date applied (YYYY-MM-DD). Defaults to today.
        jd_url: Job description URL.
        jd_text: Job description text.
    """
    row = db.execute_returning(
        """
        INSERT INTO applications (company_id, company_name, role, date_applied,
            source, status, jd_url, jd_text, notes, last_status_change)
        VALUES (%s, %s, %s, COALESCE(%s::date, CURRENT_DATE), %s, %s, %s, %s, %s, NOW())
        RETURNING *
        """,
        (company_id, company_name, role, date_applied, source, status, jd_url, jd_text, notes),
    )
    return row


@mcp.tool()
def update_application(
    id: int,
    status: str = "",
    notes: str = "",
) -> dict:
    """Update an application's status and/or notes.

    Args:
        id: Application ID.
        status: New status value.
        notes: Updated notes (replaces existing).
    """
    sets, params = [], []
    if status:
        sets.append("status = %s")
        params.append(status)
        sets.append("last_status_change = NOW()")
    if notes:
        sets.append("notes = %s")
        params.append(notes)
    if not sets:
        return {"error": "Provide status or notes to update"}

    params.append(id)
    row = db.execute_returning(
        f"UPDATE applications SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    return row or {"error": f"Application {id} not found"}


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Emails
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Content Sections (Candidate Profile, Rejection Analysis, etc.)
# ---------------------------------------------------------------------------

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

    return {
        "text_length": len(text),
        "violations": violations,
        "violation_count": len(violations),
        "clean": len(violations) == 0,
    }


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


# ---------------------------------------------------------------------------
# Resume Data
# ---------------------------------------------------------------------------

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

    # Get the spec
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


# ---------------------------------------------------------------------------
# Resume Generation
# ---------------------------------------------------------------------------

@mcp.tool()
def list_recipes(template_id: int = 0, is_active: bool = True) -> dict:
    """List available resume recipes.

    Args:
        template_id: Filter by template ID (0 = all templates).
        is_active: Filter by active status (default True).
    """
    sql = "SELECT id, name, description, headline, template_id, application_id, is_active, created_at FROM resume_recipes WHERE 1=1"
    params = []
    if template_id > 0:
        sql += " AND template_id = %s"
        params.append(template_id)
    if is_active:
        sql += " AND is_active = TRUE"
    sql += " ORDER BY id"
    rows = db.query(sql, params)
    return {"recipes": rows, "count": len(rows)}


@mcp.tool()
def get_recipe(recipe_id: int = 0) -> dict:
    """Get a single resume recipe with full JSON.

    Args:
        recipe_id: Recipe ID to fetch.
    """
    if recipe_id <= 0:
        return {"error": "recipe_id is required"}
    row = db.query_one("SELECT * FROM resume_recipes WHERE id = %s", (recipe_id,))
    if not row:
        return {"error": f"Recipe id={recipe_id} not found"}
    return row


@mcp.tool()
def create_recipe(name: str = "", headline: str = "", template_id: int = 0,
                  recipe_json: str = "", description: str = "", application_id: int = 0) -> dict:
    """Create a new resume recipe.

    Args:
        name: Recipe name (e.g. "V32 AI Architect - Optum").
        headline: Resume headline text.
        template_id: ID of the template to use.
        recipe_json: JSON string of slot-to-source mappings.
        description: Optional description.
        application_id: Optional linked application ID (0 = none).
    """
    if not name or not template_id or not recipe_json:
        return {"error": "name, template_id, and recipe_json are required"}
    import json as _json
    try:
        recipe = _json.loads(recipe_json) if isinstance(recipe_json, str) else recipe_json
    except _json.JSONDecodeError as e:
        return {"error": f"Invalid recipe JSON: {e}"}

    app_id = application_id if application_id > 0 else None
    row = db.execute_returning(
        """INSERT INTO resume_recipes (name, description, headline, template_id, recipe, application_id)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
        (name, description or None, headline or None, template_id, _json.dumps(recipe), app_id),
    )
    return row or {"error": "Failed to create recipe"}


@mcp.tool()
def update_recipe(recipe_id: int = 0, name: str = "", headline: str = "",
                  recipe_json: str = "", description: str = "", is_active: bool = True) -> dict:
    """Update an existing resume recipe.

    Args:
        recipe_id: Recipe ID to update.
        name: New name (empty = keep current).
        headline: New headline (empty = keep current).
        recipe_json: New recipe JSON (empty = keep current).
        description: New description (empty = keep current).
        is_active: Active status.
    """
    if recipe_id <= 0:
        return {"error": "recipe_id is required"}
    existing = db.query_one("SELECT * FROM resume_recipes WHERE id = %s", (recipe_id,))
    if not existing:
        return {"error": f"Recipe id={recipe_id} not found"}

    import json as _json
    updates = {}
    if name:
        updates["name"] = name
    if headline:
        updates["headline"] = headline
    if description:
        updates["description"] = description
    if recipe_json:
        try:
            updates["recipe"] = _json.dumps(
                _json.loads(recipe_json) if isinstance(recipe_json, str) else recipe_json
            )
        except _json.JSONDecodeError as e:
            return {"error": f"Invalid recipe JSON: {e}"}
    updates["is_active"] = is_active

    if not updates:
        return existing

    set_clauses = ", ".join(f"{k} = %s" for k in updates)
    set_clauses += ", updated_at = NOW()"
    values = list(updates.values()) + [recipe_id]
    row = db.execute_returning(
        f"UPDATE resume_recipes SET {set_clauses} WHERE id = %s RETURNING *",
        values,
    )
    return row or {"error": "Failed to update recipe"}


def _resolve_recipe_db(recipe_json: dict) -> dict:
    """Resolve a recipe JSON into a content_map using db module.

    Shared helper for MCP tool and Flask route.
    """
    ALLOWED = {"bullets", "career_history", "skills", "summary_variants",
               "education", "certifications", "resume_header"}
    content = {}
    for slot_name, ref in recipe_json.items():
        if "literal" in ref:
            content[slot_name] = ref["literal"]
        elif "ids" in ref:
            table = ref["table"]
            if table not in ALLOWED:
                continue
            ids = ref["ids"]
            column = ref.get("column", "name")
            rows = db.query(
                f"SELECT id, {column} FROM {table} WHERE id = ANY(%s)",
                (ids,),
            )
            by_id = {r["id"]: r[column] for r in rows}
            values = [by_id.get(i, "") for i in ids]
            content[slot_name] = " | ".join(v for v in values if v)
        elif "table" in ref:
            table = ref["table"]
            if table not in ALLOWED:
                continue
            row_id = ref.get("id", 1)
            column = ref.get("column") or ref.get("slot")

            if table == "resume_header":
                h = db.query_one("SELECT * FROM resume_header WHERE id = %s", (row_id,))
                if not h:
                    content[slot_name] = ""
                    continue
                if column in ("name",) or slot_name == "HEADER_NAME":
                    content[slot_name] = f"{h['full_name']}, {h['credentials']}"
                elif column in ("contact",) or slot_name == "HEADER_CONTACT":
                    parts = [h["location"]]
                    if h.get("location_note"):
                        parts[0] += f" ({h['location_note']})"
                    parts.append(h["email"])
                    parts.append(h["phone"])
                    if h.get("linkedin_url"):
                        parts.append(h["linkedin_url"])
                    content[slot_name] = " \u2022 ".join(parts)
                else:
                    row = db.query_one(f"SELECT {column} FROM {table} WHERE id = %s", (row_id,))
                    content[slot_name] = row[column] if row else ""
            elif column is None or column == "":
                if table == "career_history":
                    r = db.query_one("SELECT employer, location, industry FROM career_history WHERE id = %s", (row_id,))
                    if r:
                        parts = [r["employer"]]
                        if r.get("location"):
                            parts.append(f", {r['location']}")
                        if r.get("industry"):
                            parts.append(f" {{{r['industry']}}}")
                        content[slot_name] = "".join(parts)
                elif table == "education":
                    r = db.query_one("SELECT degree, field, institution, location FROM education WHERE id = %s", (row_id,))
                    if r:
                        parts = [p for p in [r.get("degree"), r.get("field")] if p]
                        result = ", ".join(parts)
                        if r.get("institution"):
                            result += f" | {r['institution']}"
                        if r.get("location"):
                            result += f" \u2014 {r['location']}"
                        content[slot_name] = result
                elif table == "certifications":
                    r = db.query_one("SELECT name, issuer FROM certifications WHERE id = %s", (row_id,))
                    if r:
                        content[slot_name] = f"{r['name']} | {r['issuer']}" if r.get("issuer") else r["name"]
                else:
                    content[slot_name] = ""
            else:
                row = db.query_one(f"SELECT {column} FROM {table} WHERE id = %s", (row_id,))
                content[slot_name] = row[column] if row and row.get(column) else ""
    return content


@mcp.tool()
def generate_resume(version: str = "v32", variant: str = "base", output_path: str = "",
                    recipe_id: int = 0) -> dict:
    """Generate a .docx resume from a recipe or legacy spec.

    When recipe_id is provided, uses recipe-based generation (pointer references).
    Otherwise falls back to legacy spec-based generation.

    Args:
        version: Resume version for legacy path (default v32).
        variant: Resume variant for legacy path (default base).
        output_path: Where to save the .docx. Defaults to Output/resume_{version}_{variant}.docx.
        recipe_id: Recipe ID from resume_recipes (0 = use legacy spec path).
    """
    import io as _io
    import json as _json
    import re as _re
    from pathlib import Path
    from docx import Document

    PLACEHOLDER_RE = _re.compile(r"\{\{([A-Z0-9_]+)\}\}")
    BOLD_SEPS = {
        "highlight": ": ", "job_bullet": ": ", "education": " | ",
        "certification": " | ", "additional_exp": " | ", "ref_link": " | ",
        "job_header": ", ",
    }

    # === RECIPE PATH ===
    if recipe_id > 0:
        recipe_row = db.query_one("SELECT * FROM resume_recipes WHERE id = %s", (recipe_id,))
        if not recipe_row:
            return {"error": f"Recipe id={recipe_id} not found"}

        # Load template from recipe's template_id
        tmpl = db.query_one(
            "SELECT name, template_blob, template_map FROM resume_templates WHERE id = %s AND is_active = TRUE",
            (recipe_row["template_id"],),
        )
        if not tmpl:
            return {"error": f"Template id={recipe_row['template_id']} not found"}

        template_blob = bytes(tmpl["template_blob"])
        template_map = tmpl["template_map"] or {}
        recipe_json = recipe_row["recipe"]
        if isinstance(recipe_json, str):
            recipe_json = _json.loads(recipe_json)

        content = _resolve_recipe_db(recipe_json)
        if recipe_row.get("headline"):
            content["HEADLINE"] = recipe_row["headline"]

        # Build slot info and fill template (same as legacy path below)
        slot_info = {}
        for slot in template_map.get("slots", []):
            if slot.get("placeholder"):
                slot_info[slot["placeholder"]] = {
                    "slot_type": slot.get("slot_type", ""),
                    "formatting": slot.get("formatting", {}),
                }

        doc = Document(_io.BytesIO(template_blob))
        filled = 0
        for para in doc.paragraphs:
            match = PLACEHOLDER_RE.search(para.text)
            if not match:
                continue
            placeholder = match.group(1)
            if placeholder not in content:
                if para.runs:
                    para.runs[0].text = ""
                    for run in para.runs[1:]:
                        run.text = ""
                continue
            text = content[placeholder]
            info = slot_info.get(placeholder, {})
            slot_type = info.get("slot_type", "")
            formatting = info.get("formatting", {})
            if formatting.get("bold_label") and slot_type in BOLD_SEPS:
                sep = BOLD_SEPS[slot_type]
                idx = text.find(sep)
                if idx >= 0 and para.runs:
                    para.runs[0].text = text[:idx]
                    para.runs[0].bold = True
                    if len(para.runs) > 1:
                        para.runs[1].text = text[idx:]
                        para.runs[1].bold = None
                        for run in para.runs[2:]:
                            run.text = ""
                            run.bold = None
                    else:
                        para.runs[0].text = text
                else:
                    if para.runs:
                        para.runs[0].text = text
                        for run in para.runs[1:]:
                            run.text = ""
            else:
                if para.runs:
                    para.runs[0].text = text
                    for run in para.runs[1:]:
                        run.text = ""
                else:
                    para.text = text
            filled += 1

        if not output_path:
            # Organize output by company/role/date when application_id linked
            if recipe_row.get("application_id"):
                app = db.query_one("SELECT company_name, role, date_applied FROM applications WHERE id = %s",
                                   (recipe_row["application_id"],))
                if app:
                    import datetime
                    company = (app.get("company_name") or "Unknown").replace(" ", "_").replace("/", "_")
                    role = (app.get("role") or "Role").replace(" ", "_").replace("/", "_")
                    date = (app.get("date_applied") or datetime.date.today()).isoformat()
                    output_path = f"Output/{company}_{role}_{date}/resume.docx"
                else:
                    output_path = f"Output/resume_recipe_{recipe_id}.docx"
            else:
                output_path = f"Output/resume_recipe_{recipe_id}.docx"
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out))

        return {
            "status": "generated",
            "output_path": str(out),
            "recipe_id": recipe_id,
            "recipe_name": recipe_row["name"],
            "slots_filled": filled,
            "total_content": len(content),
        }

    # === LEGACY SPEC PATH ===
    # Load template
    tmpl = db.query_one(
        "SELECT template_blob, template_map FROM resume_templates "
        "WHERE name = 'V32 Placeholder' AND is_active = TRUE"
    )
    if not tmpl:
        return {"error": "Placeholder template not found in DB"}

    template_blob = bytes(tmpl["template_blob"])
    template_map = tmpl["template_map"] or {}

    # Load spec
    rv = db.query_one(
        "SELECT spec FROM resume_versions WHERE version = %s AND variant = %s AND spec IS NOT NULL",
        (version, variant),
    )
    if not rv:
        return {"error": f"No spec found for {version}/{variant}"}
    spec = rv["spec"] if isinstance(rv["spec"], dict) else _json.loads(rv["spec"])

    # Load supporting data
    header = db.query_one("SELECT * FROM resume_header LIMIT 1")
    education = db.query("SELECT * FROM education ORDER BY sort_order")
    certifications = db.query("SELECT * FROM certifications WHERE is_active = TRUE ORDER BY sort_order")

    employers = spec.get("experience_employers", [])
    career = {}
    for emp in employers:
        ch = db.query_one(
            "SELECT * FROM career_history WHERE employer ILIKE %s ORDER BY start_date DESC LIMIT 1",
            (f"%{emp}%",),
        )
        if ch:
            career[emp] = ch

    # Build content map (seed from template_map, overlay with spec)
    content = {}
    for slot in template_map.get("slots", []):
        ph = slot.get("placeholder")
        orig = slot.get("original_text")
        if ph and orig:
            content[ph] = orig

    # Overlay dynamic content from spec
    if header:
        content["HEADER_NAME"] = f"{header['full_name']}, {header['credentials']}"
        parts = [header["location"]]
        if header.get("location_note"):
            parts[0] += f" ({header['location_note']})"
        parts.append(header["email"])
        parts.append(header["phone"])
        if header.get("linkedin_url"):
            parts.append(header["linkedin_url"])
        content["HEADER_CONTACT"] = " \u2022 ".join(parts)

    for key in ["headline", "summary_text"]:
        if key in spec:
            target = "HEADLINE" if key == "headline" else "SUMMARY"
            content[target] = spec[key]

    for i, b in enumerate(spec.get("highlight_bullets", []), 1):
        content[f"HIGHLIGHT_{i}"] = b

    if "keywords" in spec:
        content["KEYWORDS"] = " | ".join(spec["keywords"])
    if "executive_keywords" in spec:
        content["EXEC_KEYWORDS"] = " | ".join(spec["executive_keywords"])
    if "technical_keywords" in spec:
        content["TECH_KEYWORDS"] = " | ".join(spec["technical_keywords"])

    exp_bullets = spec.get("experience_bullets", {})
    for job_n, emp_name in enumerate(employers, 1):
        emp_data = career.get(emp_name, {})
        bullets_raw = exp_bullets.get(emp_name, [])

        if emp_data.get("intro_text"):
            content[f"JOB_{job_n}_INTRO"] = emp_data["intro_text"]

        subtitle_texts = {content.get(f"JOB_{job_n}_SUBTITLE_1", ""),
                          content.get(f"JOB_{job_n}_SUBTITLE_2", "")}
        bullet_texts = [b for b in bullets_raw
                        if b != content.get(f"JOB_{job_n}_INTRO") and b not in subtitle_texts]
        for i, bt in enumerate(bullet_texts, 1):
            content[f"JOB_{job_n}_BULLET_{i}"] = bt

    for i, ref in enumerate(spec.get("references", []), 1):
        for j, link in enumerate(ref.get("links", []), 1):
            content[f"REF_{i}_LINK_{j}"] = f"{link['text']} | {link['desc']}"

    # Build slot info
    slot_info = {}
    for slot in template_map.get("slots", []):
        if slot.get("placeholder"):
            slot_info[slot["placeholder"]] = {
                "slot_type": slot.get("slot_type", ""),
                "formatting": slot.get("formatting", {}),
            }

    # Fill template
    doc = Document(_io.BytesIO(template_blob))
    filled = 0
    for para in doc.paragraphs:
        match = PLACEHOLDER_RE.search(para.text)
        if not match:
            continue
        placeholder = match.group(1)
        if placeholder not in content:
            if para.runs:
                para.runs[0].text = ""
                for run in para.runs[1:]:
                    run.text = ""
            continue

        text = content[placeholder]
        info = slot_info.get(placeholder, {})
        slot_type = info.get("slot_type", "")
        formatting = info.get("formatting", {})

        if formatting.get("bold_label") and slot_type in BOLD_SEPS:
            sep = BOLD_SEPS[slot_type]
            idx = text.find(sep)
            if idx >= 0 and para.runs:
                para.runs[0].text = text[:idx]
                para.runs[0].bold = True
                if len(para.runs) > 1:
                    para.runs[1].text = text[idx:]
                    para.runs[1].bold = None
                    for run in para.runs[2:]:
                        run.text = ""
                        run.bold = None
                else:
                    para.runs[0].text = text
            else:
                if para.runs:
                    para.runs[0].text = text
                    for run in para.runs[1:]:
                        run.text = ""
        else:
            if para.runs:
                para.runs[0].text = text
                for run in para.runs[1:]:
                    run.text = ""
            else:
                para.text = text
        filled += 1

    # Save
    if not output_path:
        output_path = f"Output/resume_{version}_{variant}.docx"
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))

    return {
        "status": "generated",
        "output_path": str(out),
        "version": version,
        "variant": variant,
        "slots_filled": filled,
        "total_content": len(content),
    }


# ---------------------------------------------------------------------------
# Saved Jobs
# ---------------------------------------------------------------------------

@mcp.tool()
def save_job(title: str, company: str = "", url: str = "", jd_text: str = "",
             source: str = "manual", fit_score: float = 0, notes: str = "") -> dict:
    """Save a job to the evaluation queue.

    Args:
        title: Job title (required).
        company: Company name.
        url: Job posting URL.
        jd_text: Full job description text.
        source: Where the job was found (indeed, linkedin, manual, etc.).
        fit_score: Initial fit score (0-10).
        notes: Any notes about the job.
    """
    # Try to find matching company
    company_id = None
    if company:
        co = db.query_one("SELECT id FROM companies WHERE name ILIKE %s", (f"%{company}%",))
        if co:
            company_id = co["id"]

    row = db.execute_returning(
        """
        INSERT INTO saved_jobs (title, company, company_id, url, jd_text, source, fit_score, status, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,'saved',%s)
        RETURNING id, title, company, status, fit_score, created_at
        """,
        (title, company, company_id, url, jd_text, source, fit_score, notes),
    )
    return row


@mcp.tool()
def list_saved_jobs(status: str = "", limit: int = 20) -> list:
    """List saved jobs in the evaluation queue.

    Args:
        status: Filter by status (saved, evaluating, applying, applied, passed). Empty = all.
        limit: Max results (default 20).
    """
    if status:
        rows = db.query(
            "SELECT id, title, company, source, fit_score, status, created_at FROM saved_jobs WHERE status = %s ORDER BY fit_score DESC NULLS LAST LIMIT %s",
            (status, limit),
        )
    else:
        rows = db.query(
            "SELECT id, title, company, source, fit_score, status, created_at FROM saved_jobs ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )
    return rows


@mcp.tool()
def update_saved_job(job_id: int, status: str = "", fit_score: float = 0, notes: str = "") -> dict:
    """Update a saved job's status, score, or notes.

    Args:
        job_id: Saved job ID (required).
        status: New status (saved, evaluating, applying, applied, passed).
        fit_score: Updated fit score (0-10).
        notes: Updated notes.
    """
    sets, params = [], []
    if status:
        sets.append("status = %s")
        params.append(status)
    if fit_score > 0:
        sets.append("fit_score = %s")
        params.append(fit_score)
    if notes:
        sets.append("notes = %s")
        params.append(notes)
    if not sets:
        return {"error": "No fields to update"}
    params.append(job_id)
    row = db.execute_returning(
        f"UPDATE saved_jobs SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    return row or {"error": f"Saved job id={job_id} not found"}


# ---------------------------------------------------------------------------
# Gap Analysis Persistence
# ---------------------------------------------------------------------------

@mcp.tool()
def save_gap_analysis(jd_text: str = "", application_id: int = 0, saved_job_id: int = 0,
                      strong_matches: str = "", partial_matches: str = "", gaps: str = "",
                      bonus_value: str = "", fit_scores: str = "",
                      overall_score: float = 0, recommendation: str = "",
                      notes: str = "") -> dict:
    """Save a gap analysis result to the database.

    All JSON fields (strong_matches, partial_matches, gaps, bonus_value, fit_scores)
    should be passed as JSON strings.

    Args:
        jd_text: The job description text analyzed.
        application_id: Link to an application (0 = none).
        saved_job_id: Link to a saved job (0 = none).
        strong_matches: JSON string of strong match items.
        partial_matches: JSON string of partial match items.
        gaps: JSON string of gap items.
        bonus_value: JSON string of bonus value items.
        fit_scores: JSON string of fit score breakdown.
        overall_score: Overall fit score (0-10).
        recommendation: strong_apply, apply_with_tailoring, stretch, or pass.
        notes: Additional notes.
    """
    import json as _json

    row = db.execute_returning(
        """
        INSERT INTO gap_analyses (application_id, saved_job_id, jd_text,
            strong_matches, partial_matches, gaps, bonus_value,
            fit_scores, overall_score, recommendation, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id, overall_score, recommendation, created_at
        """,
        (
            application_id or None, saved_job_id or None, jd_text,
            strong_matches or None, partial_matches or None,
            gaps or None, bonus_value or None, fit_scores or None,
            overall_score or None, recommendation or None, notes or None,
        ),
    )

    # Link to application
    if application_id and row:
        db.execute(
            "UPDATE applications SET gap_analysis_id = %s WHERE id = %s",
            (row["id"], application_id),
        )

    return row


@mcp.tool()
def get_gap_analysis(gap_id: int = 0, application_id: int = 0, saved_job_id: int = 0) -> dict:
    """Retrieve a gap analysis by ID or by linked application/saved job.

    Args:
        gap_id: Gap analysis ID (direct lookup).
        application_id: Find gap analysis linked to this application.
        saved_job_id: Find gap analysis linked to this saved job.
    """
    if gap_id:
        row = db.query_one("SELECT * FROM gap_analyses WHERE id = %s", (gap_id,))
    elif application_id:
        row = db.query_one(
            "SELECT * FROM gap_analyses WHERE application_id = %s ORDER BY created_at DESC LIMIT 1",
            (application_id,),
        )
    elif saved_job_id:
        row = db.query_one(
            "SELECT * FROM gap_analyses WHERE saved_job_id = %s ORDER BY created_at DESC LIMIT 1",
            (saved_job_id,),
        )
    else:
        return {"error": "Provide gap_id, application_id, or saved_job_id"}
    return row or {"error": "Gap analysis not found"}


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------

@mcp.tool()
def log_follow_up(application_id: int, method: str = "email",
                  date_sent: str = "", notes: str = "") -> dict:
    """Log a follow-up attempt for an application.

    Args:
        application_id: Application ID (required).
        method: Contact method (email, linkedin, phone).
        date_sent: Date sent (YYYY-MM-DD). Defaults to today.
        notes: Notes about the follow-up.
    """
    last = db.query_one(
        "SELECT MAX(attempt_number) AS max_num FROM follow_ups WHERE application_id = %s",
        (application_id,),
    )
    next_num = (last["max_num"] or 0) + 1 if last else 1

    row = db.execute_returning(
        """
        INSERT INTO follow_ups (application_id, attempt_number, date_sent, method, notes)
        VALUES (%s, %s, COALESCE(%s::date, CURRENT_DATE), %s, %s)
        RETURNING *
        """,
        (application_id, next_num, date_sent or None, method, notes or None),
    )
    return row


@mcp.tool()
def get_stale_applications(days: int = 14) -> list:
    """Find applications with no activity for N days.

    Args:
        days: Number of days without activity to consider stale (default 14).
    """
    rows = db.query(
        """
        SELECT a.id, a.company_name, a.role, a.status, a.last_status_change,
               a.date_applied,
               EXTRACT(DAY FROM NOW() - COALESCE(a.last_status_change, a.date_applied::timestamp))::int AS days_stale,
               (SELECT COUNT(*) FROM follow_ups f WHERE f.application_id = a.id) AS follow_up_count
        FROM applications a
        WHERE a.status NOT IN ('Rejected', 'Ghosted', 'Withdrawn', 'Accepted', 'Rescinded')
          AND COALESCE(a.last_status_change, a.date_applied::timestamp) < NOW() - INTERVAL '%s days'
        ORDER BY days_stale DESC
        """,
        (days,),
    )
    return rows


# ---------------------------------------------------------------------------
# Interview Prep & Debrief
# ---------------------------------------------------------------------------

@mcp.tool()
def save_interview_prep(interview_id: int, company_dossier: str = "",
                        prepared_questions: str = "", talking_points: str = "",
                        star_stories_selected: str = "", questions_to_ask: str = "",
                        notes: str = "") -> dict:
    """Save interview prep materials. JSON fields should be passed as JSON strings.

    Args:
        interview_id: Interview ID (required).
        company_dossier: JSON string of company research snapshot.
        prepared_questions: JSON string of prepared Q&A items.
        talking_points: JSON string of talking points.
        star_stories_selected: JSON string of selected STAR stories.
        questions_to_ask: JSON string of questions to ask the interviewer.
        notes: Additional notes.
    """
    row = db.execute_returning(
        """
        INSERT INTO interview_prep (interview_id, company_dossier, prepared_questions,
            talking_points, star_stories_selected, questions_to_ask, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        RETURNING id, interview_id, created_at
        """,
        (
            interview_id,
            company_dossier or None, prepared_questions or None,
            talking_points or None, star_stories_selected or None,
            questions_to_ask or None, notes or None,
        ),
    )
    return row


@mcp.tool()
def save_interview_debrief(interview_id: int, went_well: str = "", went_poorly: str = "",
                           questions_asked: str = "", next_steps: str = "",
                           overall_feeling: str = "", lessons_learned: str = "",
                           notes: str = "") -> dict:
    """Save a structured interview debrief. JSON fields as JSON strings.

    Args:
        interview_id: Interview ID (required).
        went_well: JSON string of things that went well.
        went_poorly: JSON string of things that went poorly.
        questions_asked: JSON string of questions asked and answers given.
        next_steps: Free-text next steps.
        overall_feeling: great, good, neutral, concerned, or poor.
        lessons_learned: Free-text lessons learned.
        notes: Additional notes.
    """
    row = db.execute_returning(
        """
        INSERT INTO interview_debriefs (interview_id, went_well, went_poorly,
            questions_asked, next_steps, overall_feeling, lessons_learned, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id, interview_id, overall_feeling, created_at
        """,
        (
            interview_id,
            went_well or None, went_poorly or None,
            questions_asked or None, next_steps or None,
            overall_feeling or None, lessons_learned or None,
            notes or None,
        ),
    )
    return row


# ---------------------------------------------------------------------------
# Profile Management
# ---------------------------------------------------------------------------

@mcp.tool()
def update_header(full_name: str = "", credentials: str = "", email: str = "",
                  phone: str = "", location: str = "", linkedin_url: str = "") -> dict:
    """Update resume header / candidate contact info.

    Args:
        full_name: Full name.
        credentials: Credentials string (e.g. "PhD, CSM, PMP, MBA").
        email: Email address.
        phone: Phone number.
        location: Location.
        linkedin_url: LinkedIn profile URL.
    """
    sets, params = [], []
    for field, val in [("full_name", full_name), ("credentials", credentials),
                       ("email", email), ("phone", phone), ("location", location),
                       ("linkedin_url", linkedin_url)]:
        if val:
            sets.append(f"{field} = %s")
            params.append(val)
    if not sets:
        return {"error": "No fields to update"}

    existing = db.query_one("SELECT id FROM resume_header LIMIT 1")
    if existing:
        params.append(existing["id"])
        row = db.execute_returning(
            f"UPDATE resume_header SET {', '.join(sets)} WHERE id = %s RETURNING *",
            params,
        )
    else:
        row = db.execute_returning(
            f"INSERT INTO resume_header ({', '.join(s.split(' = ')[0] for s in sets)}) VALUES ({', '.join(['%s'] * len(params))}) RETURNING *",
            params,
        )
    return row


# ---------------------------------------------------------------------------
# Document tools
# ---------------------------------------------------------------------------


@mcp.tool()
def mcp_read_docx(file_path: str) -> dict:
    """Extract text from a .docx file.

    Args:
        file_path: Path to the .docx file.

    Returns:
        {"text": str, "paragraphs": int}
    """
    sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
    from read_docx import read_full_text
    text = read_full_text(file_path)
    return {"text": text, "paragraphs": len([p for p in text.split("\n") if p.strip()])}


@mcp.tool()
def mcp_read_pdf(file_path: str, pages: str | None = None) -> dict:
    """Extract text from a .pdf file.

    Args:
        file_path: Path to the .pdf file.
        pages: Optional page range (e.g., "1-5"). Default reads all.

    Returns:
        {"text": str}
    """
    sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
    from read_pdf import read_pdf_text
    text = read_pdf_text(file_path, pages=pages)
    return {"text": text}


@mcp.tool()
def mcp_templatize_resume(file_path: str, output_dir: str = "/tmp", layout: str = "auto") -> dict:
    """Convert a .docx resume into a placeholder template.

    Args:
        file_path: Path to the .docx resume.
        output_dir: Directory for output files. Defaults to /tmp.
        layout: Template layout name. Default 'auto'.

    Returns:
        {"template_path": str, "map_path": str, "slots": int}
    """
    import json
    sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
    from templatize_resume import templatize

    stem = Path(file_path).stem
    out_docx = os.path.join(output_dir, f"{stem}_placeholder.docx")
    out_map = os.path.join(output_dir, f"{stem}_map.json")
    templatize(file_path, out_docx, out_map, layout_name=layout)

    with open(out_map) as f:
        tmap = json.load(f)
    return {"template_path": out_docx, "map_path": out_map, "slots": len(tmap)}


@mcp.tool()
def mcp_compare_docs(file_a: str, file_b: str) -> dict:
    """Compare two .docx documents and return a match score + diff.

    Args:
        file_a: Path to first .docx document.
        file_b: Path to second .docx document.

    Returns:
        {"match_percentage": float, "diff_count": int, "diff_text": str}
    """
    sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
    from compare_docs import extract_paragraphs, compare_text

    paras_a = extract_paragraphs(file_a)
    paras_b = extract_paragraphs(file_b)
    diff = compare_text(paras_a, paras_b)
    total = max(len(paras_a), len(paras_b), 1)
    matching = sum(1 for a, b in zip(paras_a, paras_b) if a.strip() == b.strip())
    return {
        "match_percentage": round((matching / total) * 100, 1),
        "diff_count": len([l for l in diff.split("\n") if l.startswith("+") or l.startswith("-")]),
        "diff_text": diff,
    }


@mcp.tool()
def mcp_docx_to_pdf(file_path: str, output_path: str | None = None) -> dict:
    """Convert a .docx file to .pdf.

    Args:
        file_path: Path to the .docx file.
        output_path: Optional output path. Defaults to same name with .pdf extension.

    Returns:
        {"pdf_path": str}
    """
    sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
    from docx_to_pdf import docx_to_pdf as _docx_to_pdf
    pdf_path = _docx_to_pdf(file_path, output_path=output_path)
    return {"pdf_path": pdf_path}


@mcp.tool()
def mcp_edit_docx(file_path: str, find_text: str, replace_text: str, output_path: str | None = None, replace_all: bool = False) -> dict:
    """Find and replace text in a .docx file.

    Args:
        file_path: Path to the .docx file.
        find_text: Text to find.
        replace_text: Replacement text.
        output_path: Optional output path. Defaults to overwriting original.
        replace_all: Replace all occurrences. Default False.

    Returns:
        {"replacements": int}
    """
    sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
    from edit_docx import find_replace
    count = find_replace(file_path, find_text, replace_text, output_path=output_path, replace_all=replace_all)
    return {"replacements": count}


@mcp.tool()
def onboard_resume(file_path: str) -> dict:
    """Run the full onboarding pipeline on a resume file.

    Parses resume into career data, creates template + recipe, verifies reconstruction.

    Args:
        file_path: Path to .docx or .pdf resume file.

    Returns:
        Full pipeline report with inserted row counts, template/recipe IDs, match score.
    """
    from pathlib import PurePath

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    filename = PurePath(file_path).name
    file_ext = PurePath(file_path).suffix.lower()

    from routes.onboard import _process_file
    return _process_file(filename, file_bytes, file_ext)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sse", action="store_true", help="Run as SSE server (for Docker)")
    parser.add_argument("--port", type=int, default=8056, help="SSE server port")
    args = parser.parse_args()

    if args.sse:
        mcp.settings.port = args.port
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
