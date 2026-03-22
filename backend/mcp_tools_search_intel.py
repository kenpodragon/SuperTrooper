"""MCP tool functions for Search Intelligence & Email Intelligence.

Orchestrator note: call register_search_intel_tools(mcp) in mcp_server.py.
"""

from __future__ import annotations

import re

import db


RECRUITER_KEYWORDS = [
    "opportunity", "position", "role", "hiring", "recruit",
    "talent", "candidate", "resume", "experience", "team",
    "interested in your", "your background", "your profile",
    "reach out", "touching base",
]

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


def register_search_intel_tools(mcp):
    """Register all search intelligence MCP tools with the given MCP server instance."""

    @mcp.tool()
    def quick_fit_score(jd_text: str | None = None, fresh_job_id: int | None = None) -> dict:
        """Quick keyword-based fit score for a JD against candidate skills.

        Args:
            jd_text: Raw JD text to score against candidate skills
            fresh_job_id: OR pull JD from fresh_jobs table by ID

        Returns:
            dict with score (0-100), matched_skills, missing_skills
        """
        if not jd_text and not fresh_job_id:
            return {"error": "Provide jd_text or fresh_job_id"}

        if not jd_text and fresh_job_id:
            job = db.query_one("SELECT jd_full AS jd_text FROM fresh_jobs WHERE id = %s", (fresh_job_id,))
            if not job:
                return {"error": "Fresh job not found"}
            jd_text = job.get("jd_text") or ""

        if not jd_text:
            return {"error": "No JD text available"}

        skills = db.query("SELECT name, category, proficiency FROM skills")
        jd_lower = jd_text.lower()

        matched = []
        for s in skills:
            if s["name"].lower() in jd_lower:
                matched.append({
                    "skill": s["name"],
                    "category": s["category"],
                    "proficiency": s["proficiency"],
                })

        common_skills = [
            "python", "java", "javascript", "typescript", "react", "node",
            "aws", "azure", "gcp", "docker", "kubernetes", "sql",
            "machine learning", "ai", "agile", "scrum", "leadership",
            "product management", "devops", "terraform", "ci/cd",
        ]
        matched_names = {m["skill"].lower() for m in matched}
        missing = [kw for kw in common_skills if kw in jd_lower and kw not in matched_names]

        total = len(matched) + len(missing)
        score = round((len(matched) / max(total, 1)) * 100)

        return {
            "score": score,
            "matched_skills": matched,
            "missing_skills": missing,
            "total_candidate_skills": len(skills),
        }

    @mcp.tool()
    def analyze_skill_demand() -> dict:
        """Analyze skill demand across all saved JDs.

        Pulls jd_text from saved_jobs and fresh_jobs, extracts skills,
        ranks by frequency, cross-references against candidate skills.

        Returns:
            dict with demanded skills ranked by frequency, missing_top list
        """
        saved = db.query("SELECT jd_text FROM saved_jobs WHERE jd_text IS NOT NULL AND jd_text != ''")
        fresh = db.query("SELECT jd_full AS jd_text FROM fresh_jobs WHERE jd_full IS NOT NULL AND jd_full != ''")
        jd_texts = [r["jd_text"] for r in saved + fresh if r.get("jd_text")]

        if not jd_texts:
            return {"error": "No JD texts found", "demanded": [], "missing_top": []}

        skills = db.query("SELECT name, category, proficiency FROM skills")
        skill_set = {s["name"].lower(): s for s in skills}

        common_skills = [
            "python", "java", "javascript", "typescript", "react", "node.js",
            "aws", "azure", "gcp", "docker", "kubernetes", "sql",
            "machine learning", "ai", "data science", "agile", "scrum",
            "leadership", "product management", "devops", "terraform",
            "go", "rust", "c++", "ruby", "angular", "vue", "django",
            "flask", "spring", "fastapi", "elasticsearch", "tableau",
            "power bi", "snowflake", "databricks", "airflow",
        ]
        all_check = set(common_skills) | set(skill_set.keys())

        skill_counts = {}
        for kw in all_check:
            count = sum(1 for jd in jd_texts if kw in jd.lower())
            if count > 0:
                skill_counts[kw] = count

        demanded = []
        for name, count in sorted(skill_counts.items(), key=lambda x: -x[1]):
            have = name in skill_set
            demanded.append({
                "skill": name,
                "count": count,
                "have": have,
                "proficiency": skill_set[name]["proficiency"] if have else None,
            })

        missing_top = [d for d in demanded if not d["have"]][:20]

        return {
            "total_jds_analyzed": len(jd_texts),
            "demanded": demanded[:50],
            "missing_top": missing_top,
        }

    @mcp.tool()
    def scan_emails_for_status() -> dict:
        """Scan unscanned emails for application status signals.

        Categorizes emails by pattern matching: confirmation, rejection,
        interview, offer. Links to applications by company name match.

        Returns:
            dict with scanned count and categorized breakdown
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
            return {"scanned": 0, "categorized": {
                "confirmation": 0, "rejection": 0, "interview": 0, "offer": 0, "unknown": 0
            }}

        applications = db.query("SELECT id, company_name, role FROM applications")
        results = {"confirmation": 0, "rejection": 0, "interview": 0, "offer": 0, "unknown": 0}

        for email in unscanned:
            text = " ".join(filter(None, [
                email.get("subject", ""),
                email.get("snippet", ""),
                email.get("body", ""),
            ])).lower()

            best_category = "unknown"
            best_confidence = 0.0

            for category, patterns in EMAIL_PATTERNS.items():
                hits = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
                if hits > 0:
                    confidence = min(hits / len(patterns) * 1.5, 0.99)
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_category = category

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

        return {"scanned": len(unscanned), "categorized": results}

    @mcp.tool()
    def detect_recruiter_emails() -> dict:
        """Detect recruiter emails and create fresh jobs + contacts.

        Scans emails for recruiter patterns (unknown sender + job keywords).
        Creates fresh_jobs entries and contacts for detected recruiters.

        Returns:
            dict with detected count, jobs_created, contacts_created
        """
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
            return {"detected": 0, "jobs_created": 0, "contacts_created": 0}

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

            hits = sum(1 for kw in RECRUITER_KEYWORDS if kw in text)
            if hits < 3:
                continue

            detected += 1
            from_addr = email.get("from_address") or ""
            from_name = email.get("from_name") or ""

            domain = from_addr.split("@")[-1] if "@" in from_addr else ""
            company = domain.split(".")[0].title() if domain else ""
            if company.lower() in ("gmail", "yahoo", "hotmail", "outlook", "aol", "icloud"):
                company = ""

            subject = email.get("subject", "")
            title = subject if len(subject) < 150 else subject[:150]

            db.execute_returning(
                """
                INSERT INTO fresh_jobs (title, company, source_type, jd_full, status,
                                        discovery_source, discovery_url, created_at)
                VALUES (%s, %s, %s, %s, 'new', 'email_parsed', %s, NOW())
                RETURNING id
                """,
                (title or "Recruiter Outreach", company, "email", text[:2000], from_addr),
            )
            jobs_created += 1

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

            db.execute(
                """
                UPDATE emails
                SET scan_status = 'recruiter', scan_confidence = %s, auto_categorized = TRUE
                WHERE id = %s
                """,
                (min(hits / len(RECRUITER_KEYWORDS), 0.99), email["id"]),
            )

        return {"detected": detected, "jobs_created": jobs_created, "contacts_created": contacts_created}
