"""MCP tool functions for the application pipeline: applications, saved jobs,
gap analyses, follow-ups, interview prep/debrief, and profile header.

Orchestrator note: call register_pipeline_tools(mcp) in mcp_server.py.
"""

from __future__ import annotations

import db


def register_pipeline_tools(mcp):
    """Register all pipeline MCP tools with the given MCP server instance."""

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
