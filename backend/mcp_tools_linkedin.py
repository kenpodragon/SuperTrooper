"""MCP tool functions for LinkedIn Profile & Brand Management.

These are standalone functions using `import db` for database access.
The orchestrator will integrate them into mcp_server.py.
"""

import json
import db


def run_profile_audit(audit_type: str = "full", target_jd_ids: list | None = None) -> dict:
    """Create a LinkedIn profile audit record.

    Generates placeholder scores (real AI scoring will be added later).
    Returns the audit record.

    Args:
        audit_type: full, headline, about, experience, skills, featured
        target_jd_ids: optional list of saved_job IDs for match scoring
    """
    # Placeholder section scores — AI scoring to be added later
    section_scores = {
        "headline": 65,
        "about": 60,
        "experience": 75,
        "skills": 55,
        "featured": 40,
    }
    overall_score = sum(section_scores.values()) / len(section_scores)

    recommendations = [
        {"section": "headline", "priority": "high", "suggestion": "Add target role title and key differentiator."},
        {"section": "about", "priority": "high", "suggestion": "Lead with your value proposition, not your history."},
        {"section": "skills", "priority": "medium", "suggestion": "Reorder skills to match target role requirements."},
        {"section": "featured", "priority": "medium", "suggestion": "Add 3-5 featured items showcasing recent work."},
    ]

    # If target JDs provided, compute placeholder match scores
    match_scores = {}
    keyword_gaps = {"missing": [], "section_suggestions": {}}
    if target_jd_ids:
        for jd_id in target_jd_ids:
            match_scores[f"jd_{jd_id}"] = round(55 + (hash(str(jd_id)) % 30), 1)

    row = db.execute_returning(
        """
        INSERT INTO linkedin_profile_audits
            (audit_type, overall_score, section_scores, recommendations,
             target_jd_ids, match_scores, keyword_gaps)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            audit_type,
            overall_score,
            json.dumps(section_scores),
            json.dumps(recommendations),
            json.dumps(target_jd_ids) if target_jd_ids else None,
            json.dumps(match_scores) if match_scores else None,
            json.dumps(keyword_gaps),
        ),
    )
    return {"audit": row}


def generate_headline_variants(target_role: str | None = None, count: int = 3) -> dict:
    """Generate LinkedIn headline variant suggestions.

    Uses candidate profile data from the database.

    Args:
        target_role: optional target role to tailor headlines for
        count: number of variants to generate (default 3)
    """
    # Pull candidate profile data
    profile = db.query_one(
        "SELECT * FROM candidate_profile ORDER BY id LIMIT 1"
    )

    # Pull skills for keyword inclusion
    skills = db.query(
        "SELECT name, proficiency FROM skills ORDER BY proficiency DESC LIMIT 10"
    )
    top_skills = [s["name"] for s in skills] if skills else ["Leadership", "Strategy", "Technology"]

    name = profile["full_name"] if profile else "Professional"
    current_title = profile.get("current_title", "Technology Leader") if profile else "Technology Leader"

    variants = []
    templates = [
        "{title} | {skill1} & {skill2} | Building High-Performance Teams",
        "{title} | Driving {skill1} Innovation | {skill2} Enthusiast",
        "{title} who turns {skill1} into business outcomes | {skill2}",
        "Former {title} | Now helping teams scale with {skill1} & {skill2}",
        "{title} | {skill1} | {skill2} | Measurable Results > Buzzwords",
    ]

    role = target_role or current_title
    for i in range(min(count, len(templates))):
        s1 = top_skills[i % len(top_skills)] if top_skills else "Technology"
        s2 = top_skills[(i + 1) % len(top_skills)] if top_skills else "Leadership"
        variant = templates[i].format(title=role, skill1=s1, skill2=s2)
        variants.append({"variant": i + 1, "headline": variant, "char_count": len(variant)})

    return {
        "target_role": role,
        "variants": variants,
        "note": "These are template-based suggestions. AI-powered variants will be added later.",
    }


def generate_linkedin_post(topic: str, theme_pillar_id: int | None = None, style: str = "text") -> dict:
    """Create a draft LinkedIn post record.

    Args:
        topic: the topic or idea for the post
        theme_pillar_id: optional theme pillar ID
        style: post_type — text, article, poll, carousel, video, document
    """
    # Create a placeholder draft with the topic as content
    content = f"[DRAFT] Topic: {topic}\n\nThis is a draft post. Use the AI content generation to expand this into a full post."
    hook_text = content[:210]

    row = db.execute_returning(
        """
        INSERT INTO linkedin_posts
            (content, post_type, theme_pillar_id, status, hook_text, char_count)
        VALUES (%s, %s, %s, 'draft', %s, %s)
        RETURNING *
        """,
        (content, style, theme_pillar_id, hook_text, len(content)),
    )
    return {"post": row}


def check_linkedin_voice(text: str) -> dict:
    """Validate text against LinkedIn voice rules.

    Checks the text against all active linkedin_voice_rules and returns
    any violations found.

    Args:
        text: the text to validate
    """
    rules = db.query(
        "SELECT * FROM linkedin_voice_rules WHERE active = TRUE ORDER BY category"
    )

    text_lower = text.lower()
    violations = []

    for rule in rules:
        if rule["category"] == "banned_patterns":
            rule_text = rule["rule_text"]
            if ":" in rule_text:
                phrases_part = rule_text.split(":", 1)[1]
                phrases = [p.strip().strip("'\"") for p in phrases_part.split(",")]
                for phrase in phrases:
                    clean = phrase.strip().rstrip(".")
                    if clean and clean.lower() in text_lower:
                        violations.append({
                            "rule_id": rule["id"],
                            "category": rule["category"],
                            "found": clean,
                            "rule_text": rule["rule_text"],
                        })

    return {
        "text_length": len(text),
        "rules_checked": len(rules),
        "violations": violations,
        "passed": len(violations) == 0,
    }


def run_skills_audit(target_jd_ids: list | None = None) -> dict:
    """Create a LinkedIn skills audit comparing DB skills to target JDs.

    Args:
        target_jd_ids: optional list of saved_job IDs to compare against
    """
    # Get current skills from DB
    skills = db.query("SELECT name, proficiency, category FROM skills ORDER BY proficiency DESC")
    current_skills = {s["name"]: s for s in skills} if skills else {}

    # Placeholder audit data — AI-powered analysis to be added later
    skills_keep = [
        {"skill": s["name"], "relevance": "high" if s.get("proficiency", 0) >= 80 else "medium",
         "jd_frequency": 70}
        for s in (skills[:10] if skills else [])
    ]

    skills_add = [
        {"skill": "Cloud Architecture", "reason": "Frequently requested in target roles"},
        {"skill": "AI/ML Strategy", "reason": "Emerging requirement for leadership roles"},
    ]

    skills_remove = []
    skills_reprioritize = []

    top_50 = [s["name"] for s in (skills[:50] if skills else [])]

    row = db.execute_returning(
        """
        INSERT INTO linkedin_skills_audits
            (target_jd_ids, skills_keep, skills_add, skills_remove,
             skills_reprioritize, top_50_recommended, endorsement_gaps, skill_role_mapping)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            json.dumps(target_jd_ids) if target_jd_ids else None,
            json.dumps(skills_keep),
            json.dumps(skills_add),
            json.dumps(skills_remove),
            json.dumps(skills_reprioritize),
            json.dumps(top_50),
            json.dumps([]),
            json.dumps({}),
        ),
    )
    return {"audit": row}


def get_linkedin_analytics(days: int = 30) -> dict:
    """Return LinkedIn content performance analytics.

    Aggregates post counts, average engagement, best types, and best themes
    over the specified lookback window.

    Args:
        days: lookback period in days (default 30)
    """
    overall = db.query_one(
        """
        SELECT
            COUNT(*) AS total_posts,
            COUNT(*) FILTER (WHERE status = 'published') AS published,
            COUNT(*) FILTER (WHERE status = 'draft') AS drafts,
            AVG(char_count) AS avg_char_count
        FROM linkedin_posts
        WHERE created_at >= NOW() - INTERVAL '%s days'
        """,
        (days,),
    )

    by_type = db.query(
        """
        SELECT p.post_type,
               COUNT(DISTINCT p.id) AS post_count,
               AVG(e.engagement_rate) AS avg_engagement_rate,
               SUM(e.impressions) AS total_impressions
        FROM linkedin_posts p
        LEFT JOIN linkedin_post_engagement e ON e.post_id = p.id
        WHERE p.created_at >= NOW() - INTERVAL '%s days'
        GROUP BY p.post_type
        ORDER BY avg_engagement_rate DESC NULLS LAST
        """,
        (days,),
    )

    by_theme = db.query(
        """
        SELECT tp.name,
               COUNT(DISTINCT p.id) AS post_count,
               AVG(e.engagement_rate) AS avg_engagement_rate
        FROM linkedin_posts p
        JOIN linkedin_theme_pillars tp ON tp.id = p.theme_pillar_id
        LEFT JOIN linkedin_post_engagement e ON e.post_id = p.id
        WHERE p.created_at >= NOW() - INTERVAL '%s days'
        GROUP BY tp.name
        ORDER BY avg_engagement_rate DESC NULLS LAST
        """,
        (days,),
    )

    return {
        "days": days,
        "overall": overall,
        "by_type": by_type,
        "by_theme": by_theme,
    }


def get_linkedin_profile_scorecard() -> dict:
    """Return the latest profile audit as a scorecard summary.

    Formats the most recent linkedin_profile_audits record into a
    human-readable scorecard with section grades and top recommendations.
    """
    audit = db.query_one(
        "SELECT * FROM linkedin_profile_audits ORDER BY created_at DESC LIMIT 1"
    )
    if not audit:
        return {"error": "No profile audits found. Run run_profile_audit() first."}

    section_scores = audit.get("section_scores") or {}
    recommendations = audit.get("recommendations") or []

    # Convert scores to letter grades
    def score_to_grade(score):
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    scorecard = {
        "audit_id": audit["id"],
        "audit_type": audit["audit_type"],
        "audit_date": audit["created_at"],
        "overall_score": audit.get("overall_score"),
        "overall_grade": score_to_grade(audit.get("overall_score") or 0),
        "sections": {
            section: {"score": score, "grade": score_to_grade(score)}
            for section, score in section_scores.items()
            if isinstance(score, (int, float))
        },
        "top_recommendations": [
            r for r in recommendations if r.get("priority") == "high"
        ][:5],
        "keyword_gaps": audit.get("keyword_gaps"),
        "match_scores": audit.get("match_scores"),
    }

    return scorecard
