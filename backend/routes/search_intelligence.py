"""Routes for Search Intelligence & Email Intelligence (S4.4, S4.5, S4.6, S6.3)."""

import json
import re
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("search_intelligence", __name__)


# ---------------------------------------------------------------------------
# Quick Fit Score
# ---------------------------------------------------------------------------

@bp.route("/api/search/quick-score", methods=["POST"])
def quick_score():
    """Quick fit score for a JD against candidate skill profile.

    Body (JSON):
        jd_text: raw JD text to score
        fresh_job_id: OR pull JD from fresh_jobs table
    """
    data = request.get_json(force=True)
    jd_text = data.get("jd_text")
    fresh_job_id = data.get("fresh_job_id")

    if not jd_text and not fresh_job_id:
        return jsonify({"error": "Provide jd_text or fresh_job_id"}), 400

    # Pull JD from fresh_jobs if needed
    if not jd_text and fresh_job_id:
        job = db.query_one(
            "SELECT jd_full FROM fresh_jobs WHERE id = %s", (fresh_job_id,)
        )
        if not job:
            return jsonify({"error": "Fresh job not found"}), 404
        jd_text = job.get("jd_full") or ""

    if not jd_text:
        return jsonify({"error": "No JD text available"}), 400

    # Get candidate skills
    skills = db.query("SELECT name, category, proficiency FROM skills")
    skill_names = {s["name"].lower(): s for s in skills}

    # Extract words from JD and match against skills
    jd_lower = jd_text.lower()
    jd_words = set(re.findall(r"[a-z][a-z0-9+#.-]+", jd_lower))

    matched = []
    missing = []

    for s in skills:
        name_lower = s["name"].lower()
        if name_lower in jd_lower or name_lower in jd_words:
            matched.append({
                "skill": s["name"],
                "category": s["category"],
                "proficiency": s["proficiency"],
            })

    # Also check for multi-word skill matches
    for s in skills:
        name_lower = s["name"].lower()
        if len(name_lower.split()) > 1 and name_lower in jd_lower:
            already = any(m["skill"] == s["name"] for m in matched)
            if not already:
                matched.append({
                    "skill": s["name"],
                    "category": s["category"],
                    "proficiency": s["proficiency"],
                })

    # Find demanded skills we don't have (common tech keywords)
    common_skills = [
        "python", "java", "javascript", "typescript", "react", "node",
        "aws", "azure", "gcp", "docker", "kubernetes", "sql", "nosql",
        "machine learning", "ai", "data science", "agile", "scrum",
        "leadership", "strategy", "product management", "devops",
        "terraform", "ci/cd", "microservices", "rest", "graphql",
        "pandas", "spark", "kafka", "redis", "mongodb", "postgresql",
    ]
    matched_names = {m["skill"].lower() for m in matched}
    for kw in common_skills:
        if kw in jd_lower and kw not in matched_names:
            missing.append(kw)

    total_relevant = len(matched) + len(missing)
    score = round((len(matched) / max(total_relevant, 1)) * 100)

    return jsonify({
        "score": score,
        "matched_skills": matched,
        "missing_skills": missing,
        "total_candidate_skills": len(skills),
    }), 200


# ---------------------------------------------------------------------------
# Skill Demand Analysis
# ---------------------------------------------------------------------------

@bp.route("/api/search/skill-demand", methods=["POST"])
def skill_demand():
    """Analyze skill demand across saved JDs.

    Pulls jd_text from saved_jobs and fresh_jobs, extracts mentioned skills,
    ranks by frequency, cross-references against candidate skills.
    """
    # Gather all JD texts
    saved = db.query("SELECT jd_text FROM saved_jobs WHERE jd_text IS NOT NULL AND jd_text != ''")
    fresh = db.query("SELECT jd_full AS jd_text FROM fresh_jobs WHERE jd_full IS NOT NULL AND jd_full != ''")

    jd_texts = [r["jd_text"] for r in saved + fresh if r.get("jd_text")]

    if not jd_texts:
        return jsonify({"error": "No JD texts found in saved_jobs or fresh_jobs"}), 404

    # Get candidate skills
    skills = db.query("SELECT name, category, proficiency FROM skills")
    skill_set = {s["name"].lower(): s for s in skills}

    # Count skill mentions across all JDs
    skill_counts = {}
    common_skills = [
        "python", "java", "javascript", "typescript", "react", "node.js",
        "aws", "azure", "gcp", "docker", "kubernetes", "sql", "nosql",
        "machine learning", "ai", "data science", "agile", "scrum",
        "leadership", "strategy", "product management", "devops",
        "terraform", "ci/cd", "microservices", "rest api", "graphql",
        "pandas", "spark", "kafka", "redis", "mongodb", "postgresql",
        "go", "rust", "c++", "c#", ".net", "ruby", "php", "swift",
        "flutter", "angular", "vue", "svelte", "next.js", "django",
        "flask", "spring", "fastapi", "elasticsearch", "tableau",
        "power bi", "snowflake", "databricks", "airflow", "dbt",
    ]

    # Check both candidate skills and common keywords
    all_check = set(common_skills) | {s["name"].lower() for s in skills}

    for kw in all_check:
        count = 0
        for jd in jd_texts:
            if kw in jd.lower():
                count += 1
        if count > 0:
            skill_counts[kw] = count

    # Build results
    demanded = []
    for skill_name, count in sorted(skill_counts.items(), key=lambda x: -x[1]):
        have = skill_name in skill_set
        demanded.append({
            "skill": skill_name,
            "count": count,
            "have": have,
            "proficiency": skill_set[skill_name]["proficiency"] if have else None,
        })

    missing_top = [d for d in demanded if not d["have"]][:20]

    return jsonify({
        "total_jds_analyzed": len(jd_texts),
        "demanded": demanded[:50],
        "missing_top": missing_top,
    }), 200


# ---------------------------------------------------------------------------
# Saved Searches CRUD
# ---------------------------------------------------------------------------

@bp.route("/api/saved-searches", methods=["POST"])
def create_saved_search():
    """Create a new saved search.

    Body (JSON):
        name: search name (required)
        keywords, location, role_type, salary_min, salary_max,
        sources (array), filters (object), schedule
    """
    data = request.get_json(force=True)
    name = data.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO saved_searches (name, keywords, location, role_type,
            salary_min, salary_max, sources, filters, schedule)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            name,
            data.get("keywords"),
            data.get("location"),
            data.get("role_type"),
            data.get("salary_min"),
            data.get("salary_max"),
            data.get("sources"),
            json.dumps(data.get("filters")) if data.get("filters") else None,
            data.get("schedule", "daily"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/saved-searches", methods=["GET"])
def list_saved_searches():
    """List all saved searches, optionally filtered by is_active."""
    active_only = request.args.get("active", "true").lower() == "true"

    if active_only:
        rows = db.query(
            "SELECT * FROM saved_searches WHERE is_active = TRUE ORDER BY created_at DESC"
        )
    else:
        rows = db.query("SELECT * FROM saved_searches ORDER BY created_at DESC")

    return jsonify(rows), 200


@bp.route("/api/saved-searches/<int:search_id>", methods=["GET"])
def get_saved_search(search_id):
    """Get a single saved search."""
    row = db.query_one("SELECT * FROM saved_searches WHERE id = %s", (search_id,))
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/saved-searches/<int:search_id>", methods=["PUT"])
def update_saved_search(search_id):
    """Update a saved search."""
    data = request.get_json(force=True)

    existing = db.query_one("SELECT * FROM saved_searches WHERE id = %s", (search_id,))
    if not existing:
        return jsonify({"error": "Not found"}), 404

    fields = []
    params = []
    for col in ["name", "keywords", "location", "role_type", "salary_min",
                 "salary_max", "schedule"]:
        if col in data:
            fields.append(f"{col} = %s")
            params.append(data[col])

    if "sources" in data:
        fields.append("sources = %s")
        params.append(data["sources"])

    if "filters" in data:
        fields.append("filters = %s")
        params.append(json.dumps(data["filters"]))

    if "is_active" in data:
        fields.append("is_active = %s")
        params.append(data["is_active"])

    if not fields:
        return jsonify({"error": "No fields to update"}), 400

    fields.append("updated_at = NOW()")
    params.append(search_id)

    row = db.execute_returning(
        f"UPDATE saved_searches SET {', '.join(fields)} WHERE id = %s RETURNING *",
        params,
    )
    return jsonify(row), 200


@bp.route("/api/saved-searches/<int:search_id>", methods=["DELETE"])
def delete_saved_search(search_id):
    """Soft-delete a saved search (set is_active=false)."""
    existing = db.query_one("SELECT * FROM saved_searches WHERE id = %s", (search_id,))
    if not existing:
        return jsonify({"error": "Not found"}), 404

    row = db.execute_returning(
        "UPDATE saved_searches SET is_active = FALSE, updated_at = NOW() WHERE id = %s RETURNING *",
        (search_id,),
    )
    return jsonify(row), 200


@bp.route("/api/saved-searches/<int:search_id>/run", methods=["POST"])
def run_saved_search(search_id):
    """Manually trigger a saved search run.

    Marks the search as run and updates timestamps.
    Actual search integration happens via MCP/cron.
    """
    existing = db.query_one(
        "SELECT * FROM saved_searches WHERE id = %s AND is_active = TRUE",
        (search_id,),
    )
    if not existing:
        return jsonify({"error": "Not found or inactive"}), 404

    schedule_days = {"daily": 1, "twice_weekly": 3, "weekly": 7, "manual": None}
    days = schedule_days.get(existing.get("schedule", "daily"), 1)
    next_run = (datetime.utcnow() + timedelta(days=days)) if days else None

    row = db.execute_returning(
        """
        UPDATE saved_searches
        SET last_run_at = NOW(), next_run_at = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (next_run, search_id),
    )
    return jsonify({"message": "Search run triggered", "search": row}), 200


# ---------------------------------------------------------------------------
# Email Intelligence
# ---------------------------------------------------------------------------

EMAIL_PATTERNS = {
    "confirmation": [
        r"received your application",
        r"thank you for applying",
        r"application has been received",
        r"we have received",
        r"successfully submitted",
        r"application confirmed",
    ],
    "rejection": [
        r"unfortunately",
        r"not moving forward",
        r"decided not to proceed",
        r"other candidates",
        r"not a match",
        r"position has been filled",
        r"will not be moving",
        r"regret to inform",
    ],
    "interview": [
        r"schedule.*interview",
        r"interview.*schedule",
        r"your availability",
        r"like to invite you",
        r"phone screen",
        r"technical interview",
        r"onsite interview",
        r"video call",
        r"meet the team",
    ],
    "offer": [
        r"pleased to offer",
        r"congratulations",
        r"offer letter",
        r"compensation package",
        r"start date",
        r"welcome aboard",
    ],
}


@bp.route("/api/email/scan", methods=["POST"])
def scan_emails():
    """Scan unscanned emails for application status signals.

    Categorizes by pattern matching against subject + body.
    Updates email records with scan_status, scan_confidence, auto_categorized.
    Links to application_id if company name matches.
    """
    unscanned = db.query(
        """
        SELECT id, from_address, from_name, subject, snippet, body, application_id
        FROM emails
        WHERE scan_status = 'unscanned' OR scan_status IS NULL
        ORDER BY date DESC
        LIMIT 200
        """
    )

    if not unscanned:
        return jsonify({
            "scanned": 0,
            "categorized": {"confirmation": 0, "rejection": 0, "interview": 0, "offer": 0, "unknown": 0},
        }), 200

    # Get applications for company matching
    applications = db.query(
        "SELECT id, company_name, role FROM applications"
    )

    results = {"confirmation": 0, "rejection": 0, "interview": 0, "offer": 0, "unknown": 0}

    for email in unscanned:
        text = " ".join(filter(None, [
            email.get("subject", ""),
            email.get("snippet", ""),
            email.get("body", ""),
        ])).lower()

        best_category = "unknown"
        best_confidence = 0.0
        match_counts = {}

        for category, patterns in EMAIL_PATTERNS.items():
            hits = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
            if hits > 0:
                confidence = min(hits / len(patterns) * 1.5, 0.99)
                match_counts[category] = confidence
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_category = category

        # Try to link to application by company name match
        app_id = email.get("application_id")
        if not app_id:
            from_name = (email.get("from_name") or "").lower()
            from_addr = (email.get("from_address") or "").lower()
            for app in applications:
                company = (app.get("company_name") or "").lower()
                if company and (company in from_name or company in from_addr or company in text):
                    app_id = app["id"]
                    break

        scan_status = best_category if best_category != "unknown" else "scanned"

        db.execute(
            """
            UPDATE emails
            SET scan_status = %s, scan_confidence = %s,
                auto_categorized = TRUE, application_id = COALESCE(application_id, %s)
            WHERE id = %s
            """,
            (scan_status, round(best_confidence, 2), app_id, email["id"]),
        )

        results[best_category] += 1

    return jsonify({
        "scanned": len(unscanned),
        "categorized": results,
    }), 200


# ---------------------------------------------------------------------------
# Recruiter Detection
# ---------------------------------------------------------------------------

RECRUITER_KEYWORDS = [
    "opportunity", "position", "role", "hiring", "recruit",
    "talent", "candidate", "resume", "experience", "team",
    "interested in your", "your background", "your profile",
    "reach out", "touching base",
]


@bp.route("/api/email/detect-recruiters", methods=["POST"])
def detect_recruiters():
    """Detect recruiter emails and create fresh jobs + contacts.

    Scans emails for recruiter patterns (unknown sender + job keywords).
    Creates fresh_jobs entries for detected opportunities.
    Creates contacts for unknown recruiters.
    """
    # Get emails not yet categorized as recruiter
    emails = db.query(
        """
        SELECT id, from_address, from_name, subject, snippet, body, date
        FROM emails
        WHERE (scan_status = 'unscanned' OR scan_status = 'scanned' OR scan_status IS NULL)
          AND (auto_categorized = FALSE OR auto_categorized IS NULL)
        ORDER BY date DESC
        LIMIT 200
        """
    )

    if not emails:
        return jsonify({"detected": 0, "jobs_created": 0, "contacts_created": 0}), 200

    # Get existing contacts to avoid duplicates
    existing_contacts = db.query("SELECT email FROM contacts WHERE email IS NOT NULL")
    known_emails = {c["email"].lower() for c in existing_contacts if c.get("email")}

    jobs_created = 0
    contacts_created = 0
    detected = 0

    for email in emails:
        text = " ".join(filter(None, [
            email.get("subject", ""),
            email.get("snippet", ""),
            email.get("body", ""),
        ])).lower()

        # Count recruiter keyword hits
        hits = sum(1 for kw in RECRUITER_KEYWORDS if kw in text)

        if hits < 3:
            continue

        detected += 1
        from_addr = email.get("from_address") or ""
        from_name = email.get("from_name") or ""

        # Extract company from email domain
        domain = from_addr.split("@")[-1] if "@" in from_addr else ""
        company = domain.split(".")[0].title() if domain else ""
        # Skip common email providers
        if company.lower() in ("gmail", "yahoo", "hotmail", "outlook", "aol", "icloud"):
            company = ""

        # Extract role title from subject if possible
        subject = email.get("subject", "")
        title = subject if len(subject) < 150 else subject[:150]

        # Create fresh job entry
        db.execute_returning(
            """
            INSERT INTO fresh_jobs (title, company, source_type, jd_full, status,
                                    discovery_source, discovery_url, created_at)
            VALUES (%s, %s, %s, %s, 'new', 'email_parsed', %s, NOW())
            RETURNING id
            """,
            (
                title or "Recruiter Outreach",
                company,
                "email",
                text[:2000],
                from_addr,
            ),
        )
        jobs_created += 1

        # Create contact if unknown
        if from_addr.lower() not in known_emails and from_addr:
            db.execute_returning(
                """
                INSERT INTO contacts (name, company, email, title, relationship, created_at)
                VALUES (%s, %s, %s, 'Recruiter', 'new', NOW())
                RETURNING id
                """,
                (from_name or from_addr, company, from_addr),
            )
            contacts_created += 1
            known_emails.add(from_addr.lower())

        # Mark email as processed
        db.execute(
            """
            UPDATE emails
            SET scan_status = 'recruiter', scan_confidence = %s,
                auto_categorized = TRUE
            WHERE id = %s
            """,
            (min(hits / len(RECRUITER_KEYWORDS), 0.99), email["id"]),
        )

    return jsonify({
        "detected": detected,
        "jobs_created": jobs_created,
        "contacts_created": contacts_created,
    }), 200


# ---------------------------------------------------------------------------
# Search Analytics
# ---------------------------------------------------------------------------

@bp.route("/api/search/analytics", methods=["GET"])
def search_analytics():
    """Search effectiveness analytics.

    Returns jobs found per source, conversion rates, search activity.
    """
    # Jobs by source
    by_source = db.query(
        """
        SELECT source_type AS source, COUNT(*) as count,
               AVG(auto_score) as avg_fit_score
        FROM fresh_jobs
        GROUP BY source_type
        ORDER BY count DESC
        """
    )

    # Conversion: fresh_jobs -> saved_jobs
    total_fresh = db.query_one("SELECT COUNT(*) as count FROM fresh_jobs")
    total_saved = db.query_one("SELECT COUNT(*) as count FROM saved_jobs")
    total_applied = db.query_one(
        "SELECT COUNT(*) as count FROM applications WHERE status != 'draft'"
    )

    # Saved search stats
    search_stats = db.query(
        """
        SELECT id, name, results_count, last_run_at, schedule, is_active
        FROM saved_searches
        WHERE is_active = TRUE
        ORDER BY last_run_at DESC NULLS LAST
        """
    )

    # Email scan stats
    email_scan = db.query_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE scan_status = 'unscanned' OR scan_status IS NULL) as unscanned,
            COUNT(*) FILTER (WHERE scan_status = 'confirmation') as confirmations,
            COUNT(*) FILTER (WHERE scan_status = 'rejection') as rejections,
            COUNT(*) FILTER (WHERE scan_status = 'interview') as interviews,
            COUNT(*) FILTER (WHERE scan_status = 'offer') as offers,
            COUNT(*) FILTER (WHERE scan_status = 'recruiter') as recruiter
        FROM emails
        """
    )

    fresh_count = total_fresh["count"] if total_fresh else 0
    saved_count = total_saved["count"] if total_saved else 0
    applied_count = total_applied["count"] if total_applied else 0

    return jsonify({
        "jobs_by_source": by_source,
        "funnel": {
            "fresh": fresh_count,
            "saved": saved_count,
            "applied": applied_count,
            "conversion_fresh_to_saved": round(saved_count / max(fresh_count, 1) * 100, 1),
            "conversion_saved_to_applied": round(applied_count / max(saved_count, 1) * 100, 1),
        },
        "saved_searches": search_stats,
        "email_intelligence": email_scan or {},
    }), 200
