"""Routes for interview_prep, interview_debriefs, and interview analytics."""

import json
import logging
from flask import Blueprint, request, jsonify
import db
from ai_providers.router import route_inference

logger = logging.getLogger(__name__)

bp = Blueprint("interview_extras", __name__)


# ---------------------------------------------------------------------------
# Interview Prep
# ---------------------------------------------------------------------------

@bp.route("/api/interviews/<int:interview_id>/prep", methods=["GET"])
def get_interview_prep(interview_id):
    """Get prep materials for an interview."""
    row = db.query_one(
        "SELECT * FROM interview_prep WHERE interview_id = %s", (interview_id,)
    )
    if not row:
        return jsonify({"error": "No prep found for this interview"}), 404
    return jsonify(row), 200


@bp.route("/api/interviews/<int:interview_id>/prep", methods=["POST"])
def create_interview_prep(interview_id):
    """Create prep materials for an interview."""
    # Verify interview exists
    interview = db.query_one("SELECT id FROM interviews WHERE id = %s", (interview_id,))
    if not interview:
        return jsonify({"error": "Interview not found"}), 404

    data = request.get_json(force=True)
    row = db.execute_returning(
        """
        INSERT INTO interview_prep (interview_id, company_dossier, prepared_questions,
            talking_points, star_stories_selected, questions_to_ask, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            interview_id,
            json.dumps(data["company_dossier"]) if data.get("company_dossier") else None,
            json.dumps(data["prepared_questions"]) if data.get("prepared_questions") else None,
            json.dumps(data["talking_points"]) if data.get("talking_points") else None,
            json.dumps(data["star_stories_selected"]) if data.get("star_stories_selected") else None,
            json.dumps(data["questions_to_ask"]) if data.get("questions_to_ask") else None,
            data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/interview-prep/<int:prep_id>", methods=["PATCH"])
def update_interview_prep(prep_id):
    """Update interview prep materials."""
    data = request.get_json(force=True)
    allowed = [
        "company_dossier", "prepared_questions", "talking_points",
        "star_stories_selected", "questions_to_ask", "notes",
    ]
    json_fields = {"company_dossier", "prepared_questions", "talking_points",
                   "star_stories_selected", "questions_to_ask"}
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            if key in json_fields:
                params.append(json.dumps(data[key]) if data[key] else None)
            else:
                params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(prep_id)
    row = db.execute_returning(
        f"UPDATE interview_prep SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Interview Debriefs
# ---------------------------------------------------------------------------

@bp.route("/api/interviews/<int:interview_id>/debrief", methods=["GET"])
def get_interview_debrief(interview_id):
    """Get debrief for an interview."""
    row = db.query_one(
        "SELECT * FROM interview_debriefs WHERE interview_id = %s", (interview_id,)
    )
    if not row:
        return jsonify({"error": "No debrief found for this interview"}), 404
    return jsonify(row), 200


@bp.route("/api/interviews/<int:interview_id>/debrief", methods=["POST"])
def create_interview_debrief(interview_id):
    """Create a debrief for an interview."""
    interview = db.query_one("SELECT id FROM interviews WHERE id = %s", (interview_id,))
    if not interview:
        return jsonify({"error": "Interview not found"}), 404

    data = request.get_json(force=True)
    row = db.execute_returning(
        """
        INSERT INTO interview_debriefs (interview_id, went_well, went_poorly,
            questions_asked, next_steps, overall_feeling, lessons_learned, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            interview_id,
            json.dumps(data["went_well"]) if data.get("went_well") else None,
            json.dumps(data["went_poorly"]) if data.get("went_poorly") else None,
            json.dumps(data["questions_asked"]) if data.get("questions_asked") else None,
            data.get("next_steps"),
            data.get("overall_feeling"),
            data.get("lessons_learned"),
            data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/interview-debriefs/<int:debrief_id>", methods=["PATCH"])
def update_interview_debrief(debrief_id):
    """Update an interview debrief."""
    data = request.get_json(force=True)
    allowed = [
        "went_well", "went_poorly", "questions_asked",
        "next_steps", "overall_feeling", "lessons_learned", "notes",
    ]
    json_fields = {"went_well", "went_poorly", "questions_asked"}
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            if key in json_fields:
                params.append(json.dumps(data[key]) if data[key] else None)
            else:
                params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(debrief_id)
    row = db.execute_returning(
        f"UPDATE interview_debriefs SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Interview Analytics
# ---------------------------------------------------------------------------

@bp.route("/api/interviews/analytics", methods=["GET"])
def interview_analytics():
    """Cross-interview pattern analysis: win rates, question themes, prep effectiveness."""
    from mcp_tools_reporting import get_interview_analytics
    result = get_interview_analytics()
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# Cross-Interview Pattern Analysis
# ---------------------------------------------------------------------------

@bp.route("/api/interviews/cross-analysis", methods=["GET"])
def cross_interview_analysis():
    """Cross-interview pattern analysis.

    Returns:
      - Most common question types across all interviews
      - Average performance by question category
      - Company comparison (which companies have hardest interviews)
      - Improvement trajectory over time
    """
    # 1. Most common question types from mock interviews
    question_types = db.query(
        """
        SELECT miq.question_type, COUNT(*) AS count,
               ROUND(AVG(miq.score)::numeric, 1) AS avg_score
        FROM mock_interview_questions miq
        GROUP BY miq.question_type
        ORDER BY count DESC
        """
    ) or []

    # 2. Average performance by question category from debriefs
    debrief_stats = db.query(
        """
        SELECT a.company_name,
               COUNT(id2.id) AS debrief_count,
               ROUND(AVG(CASE id2.overall_feeling
                   WHEN 'great' THEN 5
                   WHEN 'good' THEN 4
                   WHEN 'okay' THEN 3
                   WHEN 'poor' THEN 2
                   WHEN 'terrible' THEN 1
                   ELSE 3 END)::numeric, 1) AS avg_feeling_score
        FROM interview_debriefs id2
        JOIN interviews i ON i.id = id2.interview_id
        JOIN applications a ON a.id = i.application_id
        GROUP BY a.company_name
        ORDER BY avg_feeling_score ASC
        """
    ) or []

    # 3. Company comparison: interview counts, pass rates
    company_comparison = db.query(
        """
        SELECT a.company_name,
               COUNT(i.id) AS total_interviews,
               SUM(CASE WHEN i.outcome = 'pass' THEN 1 ELSE 0 END) AS passed,
               SUM(CASE WHEN i.outcome = 'fail' THEN 1 ELSE 0 END) AS failed,
               SUM(CASE WHEN i.outcome = 'pending' THEN 1 ELSE 0 END) AS pending,
               ROUND(
                   CASE WHEN SUM(CASE WHEN i.outcome IN ('pass','fail') THEN 1 ELSE 0 END) > 0
                   THEN SUM(CASE WHEN i.outcome = 'pass' THEN 1 ELSE 0 END)::numeric /
                        SUM(CASE WHEN i.outcome IN ('pass','fail') THEN 1 ELSE 0 END) * 100
                   ELSE 0 END, 1
               ) AS pass_rate_pct
        FROM interviews i
        JOIN applications a ON a.id = i.application_id
        GROUP BY a.company_name
        HAVING COUNT(i.id) > 0
        ORDER BY total_interviews DESC
        """
    ) or []

    # 4. Improvement trajectory: performance over time (monthly)
    trajectory = db.query(
        """
        SELECT DATE_TRUNC('month', i.date) AS month,
               COUNT(i.id) AS interview_count,
               SUM(CASE WHEN i.outcome = 'pass' THEN 1 ELSE 0 END) AS passed,
               SUM(CASE WHEN i.outcome = 'fail' THEN 1 ELSE 0 END) AS failed,
               ROUND(
                   CASE WHEN SUM(CASE WHEN i.outcome IN ('pass','fail') THEN 1 ELSE 0 END) > 0
                   THEN SUM(CASE WHEN i.outcome = 'pass' THEN 1 ELSE 0 END)::numeric /
                        SUM(CASE WHEN i.outcome IN ('pass','fail') THEN 1 ELSE 0 END) * 100
                   ELSE 0 END, 1
               ) AS pass_rate_pct
        FROM interviews i
        WHERE i.date IS NOT NULL
        GROUP BY DATE_TRUNC('month', i.date)
        ORDER BY month ASC
        """
    ) or []

    # 5. Mock interview difficulty and performance
    mock_performance = db.query(
        """
        SELECT mi.difficulty,
               COUNT(mi.id) AS session_count,
               ROUND(AVG(mi.overall_score)::numeric, 1) AS avg_overall_score
        FROM mock_interviews mi
        WHERE mi.overall_score IS NOT NULL
        GROUP BY mi.difficulty
        ORDER BY CASE mi.difficulty
            WHEN 'easy' THEN 1
            WHEN 'medium' THEN 2
            WHEN 'hard' THEN 3
            ELSE 4 END
        """
    ) or []

    return jsonify({
        "question_types": question_types,
        "company_debrief_scores": debrief_stats,
        "company_comparison": company_comparison,
        "monthly_trajectory": trajectory,
        "mock_performance_by_difficulty": mock_performance,
    }), 200


@bp.route("/api/interviews/<int:interview_id>/prep/generate", methods=["POST"])
def generate_interview_prep_package(interview_id):
    """Auto-generate a full interview prep package from application context.
    Pulls company dossier, STAR stories, mock questions, and suggested questions to ask.
    """
    # Verify interview exists
    interview = db.query_one(
        """
        SELECT i.*, a.role, a.company_name
        FROM interviews i
        LEFT JOIN applications a ON a.id = i.application_id
        WHERE i.id = %s
        """,
        (interview_id,),
    )
    if not interview:
        return jsonify({"error": "Interview not found"}), 404

    company_name = interview.get("company_name", "")
    role = interview.get("role", "")

    # Fetch company dossier
    company_info = {}
    if company_name:
        co = db.query_one(
            """
            SELECT name, sector, hq_location, size, stage, glassdoor_rating,
                   employee_count, funding_stage, key_differentiator, notes
            FROM companies WHERE name ILIKE %s
            """,
            (f"%{company_name}%",),
        )
        if co:
            company_info = co

    # Fetch contacts at company (warm intros / insiders)
    contacts = []
    if company_name:
        contacts = db.query(
            """
            SELECT name, title, relationship, relationship_strength, last_contact
            FROM contacts WHERE company ILIKE %s
            ORDER BY CASE relationship_strength WHEN 'strong' THEN 1 WHEN 'warm' THEN 2 ELSE 3 END
            LIMIT 5
            """,
            (f"%{company_name}%",),
        )

    # Fetch recent STAR bullets
    keyword = role.split()[0] if role else ""
    star_stories = db.query(
        """
        SELECT b.id, b.text, b.tags, ch.employer, ch.title
        FROM bullets b
        LEFT JOIN career_history ch ON ch.id = b.career_history_id
        WHERE b.type = 'achievement'
        ORDER BY b.id DESC LIMIT 6
        """
    ) if not keyword else db.query(
        """
        SELECT b.id, b.text, b.tags, ch.employer, ch.title
        FROM bullets b
        LEFT JOIN career_history ch ON ch.id = b.career_history_id
        WHERE b.type = 'achievement' AND (b.text ILIKE %s OR b.tags::text ILIKE %s)
        ORDER BY b.id DESC LIMIT 6
        """,
        (f"%{keyword}%", f"%{keyword}%"),
    )
    if not star_stories:
        star_stories = db.query(
            """
            SELECT b.id, b.text, b.tags, ch.employer, ch.title
            FROM bullets b
            LEFT JOIN career_history ch ON ch.id = b.career_history_id
            WHERE b.type = 'achievement'
            ORDER BY b.id DESC LIMIT 6
            """
        )

    # Fetch mock interview questions for this role
    mock_questions = []
    if role:
        mock_questions = db.query(
            """
            SELECT miq.question_text AS question, miq.question_type, mi.difficulty
            FROM mock_interview_questions miq
            JOIN mock_interviews mi ON mi.id = miq.mock_interview_id
            WHERE mi.job_title ILIKE %s
            ORDER BY miq.created_at DESC LIMIT 10
            """,
            (f"%{keyword}%",),
        )

    # Generate questions to ask (Python fallback default)
    default_questions_to_ask = [
        f"What does success look like in the first 90 days for this role?",
        f"How does the team handle disagreement on direction?",
        f"What are the biggest challenges the team is facing right now?",
        f"How do you measure performance for this position?",
        f"What's the career path from this role?",
    ]
    if company_name:
        default_questions_to_ask.insert(1, f"What's the culture like at {company_name} day-to-day?")

    # Recent email thread with this company (news talking points)
    recent_emails = []
    if company_name:
        recent_emails = db.query(
            """
            SELECT date, from_name, subject, snippet
            FROM emails
            WHERE subject ILIKE %s OR from_name ILIKE %s
            ORDER BY date DESC LIMIT 5
            """,
            (f"%{company_name}%", f"%{company_name}%"),
        )

    # --- AI routing: enhance interview prep package ---
    ai_context = {
        "task_type": "interview_prep_package",
        "company_name": company_name,
        "role": role,
        "company_info": company_info,
        "star_stories": star_stories,
        "mock_questions": mock_questions,
        "default_questions_to_ask": default_questions_to_ask,
        "interview_type": interview.get("type", ""),
    }

    def _python_prep_package(ctx):
        return {"questions_to_ask": ctx["default_questions_to_ask"]}

    def _ai_prep_package(ctx):
        from ai_providers import get_provider
        provider = get_provider()
        company_ctx = ""
        if ctx.get("company_info"):
            company_ctx = f"\nCompany info: {json.dumps(ctx['company_info'], default=str)[:500]}"
        prompt = (
            f"Generate 6-8 thoughtful questions a candidate should ask during a "
            f"{ctx.get('interview_type', 'general')} interview for the {ctx['role'] or 'open'} "
            f"role at {ctx['company_name'] or 'the company'}.{company_ctx}\n\n"
            f"Requirements: specific to the role and company, show research, "
            f"conversational tone. Return as a JSON array of strings."
        )
        response = provider.generate(prompt)
        try:
            ai_questions = json.loads(response)
            if isinstance(ai_questions, list) and len(ai_questions) > 0:
                return {"questions_to_ask": ai_questions}
        except (ValueError, TypeError):
            pass
        return {"questions_to_ask": ctx["default_questions_to_ask"]}

    gen_result = route_inference(
        task="generate_interview_prep_package",
        context=ai_context,
        python_fallback=_python_prep_package,
        ai_handler=_ai_prep_package,
    )
    questions_to_ask = gen_result["questions_to_ask"]

    package = {
        "interview_id": interview_id,
        "role": role,
        "company_name": company_name,
        "interview_date": str(interview.get("date", "")),
        "interview_type": interview.get("type", ""),
        "company_dossier": company_info,
        "insider_contacts": contacts,
        "star_stories": star_stories,
        "mock_questions": mock_questions,
        "questions_to_ask": questions_to_ask,
        "recent_email_threads": recent_emails,
    }
    if isinstance(gen_result, dict) and gen_result.get("analysis_mode"):
        package["analysis_mode"] = gen_result["analysis_mode"]
    return jsonify(package), 200


# ---------------------------------------------------------------------------
# GET /api/interviews/upcoming — Upcoming interviews
# ---------------------------------------------------------------------------

@bp.route("/api/interviews/upcoming", methods=["GET"])
def upcoming_interviews():
    """Return upcoming interviews (future date or today).

    Query params:
        days: how many days ahead to look (default: 30)
        include_past_today: if 'true', include today's interviews (default: true)
    """
    days = int(request.args.get("days", 30))
    include_today = request.args.get("include_past_today", "true").lower() != "false"

    date_start = "CURRENT_DATE" if include_today else "CURRENT_DATE + INTERVAL '1 day'"
    rows = db.query(
        f"""
        SELECT i.id, i.application_id, i.date, i.type,
               i.interviewers, i.outcome, i.notes, i.calendar_event_id,
               i.thank_you_sent,
               a.company_name, a.role, a.status AS application_status
        FROM interviews i
        JOIN applications a ON a.id = i.application_id
        WHERE i.date >= {date_start}
          AND i.date <= CURRENT_DATE + INTERVAL '%s days'
        ORDER BY i.date ASC, i.id ASC
        """,
        (days,),
    )
    return jsonify({
        "interviews": rows,
        "count": len(rows),
        "window_days": days,
    }), 200


# ---------------------------------------------------------------------------
# POST /api/interviews/schedule — Create an interview record
# ---------------------------------------------------------------------------

@bp.route("/api/interviews/schedule", methods=["POST"])
def schedule_interview():
    """Create an interview record with date, time, company, type, contacts.

    Body (JSON):
        application_id (required): ID of the application
        date (required): interview date (ISO format)
        type (required): phone_screen, technical, behavioral, panel, final, etc.
        interviewers: list of interviewer names
        calendar_event_id: optional calendar event ID
        notes: additional notes
    """
    data = request.get_json(force=True)

    if not data.get("application_id"):
        return jsonify({"error": "application_id is required"}), 400
    if not data.get("date"):
        return jsonify({"error": "date is required"}), 400
    if not data.get("type"):
        return jsonify({"error": "type is required"}), 400

    # Verify application exists
    app = db.query_one(
        "SELECT id, company_name, role FROM applications WHERE id = %s",
        (data["application_id"],),
    )
    if not app:
        return jsonify({"error": "Application not found"}), 404

    # Build interviewers as PostgreSQL text array
    interviewers = data.get("interviewers")
    if isinstance(interviewers, list):
        interviewers = interviewers  # psycopg2 handles list -> text[]
    else:
        interviewers = None

    row = db.execute_returning(
        """
        INSERT INTO interviews (application_id, date, type, interviewers,
            calendar_event_id, notes, outcome)
        VALUES (%s, %s, %s, %s, %s, %s, 'pending')
        RETURNING *
        """,
        (
            data["application_id"],
            data["date"],
            data["type"],
            interviewers,
            data.get("calendar_event_id"),
            data.get("notes"),
        ),
    )

    # Update application status if it's still at Applied
    if app:
        current = db.query_one(
            "SELECT status FROM applications WHERE id = %s", (data["application_id"],)
        )
        if current and current["status"] == "Applied":
            db.execute(
                """
                UPDATE applications SET status = 'Interview', last_status_change = NOW()
                WHERE id = %s
                """,
                (data["application_id"],),
            )
            db.execute(
                """
                INSERT INTO application_status_history (application_id, old_status, new_status, notes)
                VALUES (%s, 'Applied', 'Interview', 'Auto-updated: interview scheduled')
                """,
                (data["application_id"],),
            )

    return jsonify({
        "interview": row,
        "company": app.get("company_name"),
        "role": app.get("role"),
    }), 201


# ---------------------------------------------------------------------------
# POST /api/interviews/auto-prep — Auto-generate full prep package
# ---------------------------------------------------------------------------

@bp.route("/api/interviews/auto-prep", methods=["POST"])
def auto_prep():
    """Given application_id, auto-generate a comprehensive interview prep package.

    Body (JSON):
        application_id (required): ID of the application

    Returns: company research, role-specific questions, STAR stories, salary talking points.
    """
    data = request.get_json(force=True)
    application_id = data.get("application_id")
    if not application_id:
        return jsonify({"error": "application_id is required"}), 400

    app = db.query_one(
        "SELECT * FROM applications WHERE id = %s", (application_id,)
    )
    if not app:
        return jsonify({"error": "Application not found"}), 404

    company_name = app.get("company_name", "")
    role = app.get("role", "")
    keyword = role.split()[0] if role else ""

    # 1. Company research summary (from dossier)
    company_dossier = {}
    if company_name:
        co = db.query_one(
            """
            SELECT name, sector, hq_location, size, stage, glassdoor_rating,
                   employee_count, funding_stage, key_differentiator, notes
            FROM companies WHERE name ILIKE %s
            """,
            (f"%{company_name}%",),
        )
        if co:
            company_dossier = dict(co)

    # Company contacts (insider intel)
    insider_contacts = []
    if company_name:
        insider_contacts = db.query(
            """
            SELECT name, title, relationship, relationship_strength, notes
            FROM contacts WHERE company ILIKE %s
            ORDER BY CASE relationship_strength
                WHEN 'strong' THEN 1 WHEN 'warm' THEN 2 ELSE 3 END
            LIMIT 5
            """,
            (f"%{company_name}%",),
        ) or []

    # 2. Role-specific questions from question bank
    role_questions = []
    if keyword:
        role_questions = db.query(
            """
            SELECT miq.question_text, miq.question_type,
                   mi.difficulty
            FROM mock_interview_questions miq
            JOIN mock_interviews mi ON mi.id = miq.mock_interview_id
            WHERE mi.job_title ILIKE %s OR miq.question_text ILIKE %s
            ORDER BY miq.created_at DESC LIMIT 15
            """,
            (f"%{keyword}%", f"%{keyword}%"),
        ) or []

    # Fallback to general questions
    if not role_questions:
        role_questions = db.query(
            """
            SELECT miq.question_text, miq.question_type,
                   mi.difficulty
            FROM mock_interview_questions miq
            JOIN mock_interviews mi ON mi.id = miq.mock_interview_id
            ORDER BY miq.created_at DESC LIMIT 10
            """
        ) or []

    # 3. STAR stories matching role requirements
    star_stories = []
    if keyword:
        star_stories = db.query(
            """
            SELECT b.id, b.text, b.tags, ch.employer, ch.title
            FROM bullets b
            LEFT JOIN career_history ch ON ch.id = b.career_history_id
            WHERE b.type = 'achievement'
              AND (b.text ILIKE %s OR b.tags::text ILIKE %s)
            ORDER BY b.id DESC LIMIT 8
            """,
            (f"%{keyword}%", f"%{keyword}%"),
        ) or []

    if not star_stories:
        star_stories = db.query(
            """
            SELECT b.id, b.text, b.tags, ch.employer, ch.title
            FROM bullets b
            LEFT JOIN career_history ch ON ch.id = b.career_history_id
            WHERE b.type = 'achievement'
            ORDER BY b.id DESC LIMIT 8
            """
        ) or []

    # Also pull from gap analysis if available
    gap_insights = {}
    if app.get("gap_analysis_id"):
        gap = db.query_one(
            "SELECT strengths, gaps, recommendations FROM gap_analyses WHERE id = %s",
            (app["gap_analysis_id"],),
        )
        if gap:
            gap_insights = {
                "strengths": gap.get("strengths"),
                "gaps": gap.get("gaps"),
                "recommendations": gap.get("recommendations"),
            }

    # 4. Salary talking points
    salary_data = {}
    if role:
        bench = db.query_one(
            "SELECT * FROM salary_benchmarks WHERE role_title ILIKE %s LIMIT 1",
            (f"%{keyword}%",),
        )
        if bench:
            salary_data = {
                "role_title": bench.get("role_title"),
                "national_median_range": bench.get("national_median_range"),
                "melbourne_range": bench.get("melbourne_range"),
                "remote_range": bench.get("remote_range"),
                "target_realistic": bench.get("target_realistic"),
            }

    # Questions to ask the interviewer
    questions_to_ask = [
        "What does success look like in the first 90 days for this role?",
        "How does the team handle disagreement on technical direction?",
        "What are the biggest challenges the team is facing right now?",
        "How do you measure performance for this position?",
        "What's the career growth path from this role?",
    ]
    if company_name:
        questions_to_ask.insert(1, f"What's the day-to-day culture like at {company_name}?")

    # Save as interview_prep if there's a scheduled interview
    interview = db.query_one(
        "SELECT id FROM interviews WHERE application_id = %s ORDER BY date DESC LIMIT 1",
        (application_id,),
    )

    package = {
        "application_id": application_id,
        "company_name": company_name,
        "role": role,
        "company_dossier": company_dossier,
        "insider_contacts": insider_contacts,
        "role_questions": role_questions,
        "star_stories": star_stories,
        "gap_insights": gap_insights,
        "salary_talking_points": salary_data,
        "questions_to_ask": questions_to_ask,
    }

    # Persist if interview exists
    if interview:
        existing_prep = db.query_one(
            "SELECT id FROM interview_prep WHERE interview_id = %s",
            (interview["id"],),
        )
        if existing_prep:
            db.execute(
                """
                UPDATE interview_prep
                SET company_dossier = %s, prepared_questions = %s, talking_points = %s,
                    star_stories_selected = %s, questions_to_ask = %s, notes = %s
                WHERE interview_id = %s
                """,
                (
                    json.dumps(company_dossier),
                    json.dumps(role_questions),
                    json.dumps(salary_data),
                    json.dumps(star_stories),
                    json.dumps(questions_to_ask),
                    f"Auto-generated prep for {company_name} - {role}",
                    interview["id"],
                ),
            )
        else:
            db.execute_returning(
                """
                INSERT INTO interview_prep
                    (interview_id, company_dossier, prepared_questions, talking_points,
                     star_stories_selected, questions_to_ask, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    interview["id"],
                    json.dumps(company_dossier),
                    json.dumps(role_questions),
                    json.dumps(salary_data),
                    json.dumps(star_stories),
                    json.dumps(questions_to_ask),
                    f"Auto-generated prep for {company_name} - {role}",
                ),
            )
        package["interview_id"] = interview["id"]
        package["saved_to_interview_prep"] = True
    else:
        package["saved_to_interview_prep"] = False

    return jsonify(package), 200
