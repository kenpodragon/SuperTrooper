"""MCP tool functions for mock interview generation and evaluation.

Orchestrator adds @mcp.tool() decorators and integrates into mcp_server.py.
All DB access via `import db`.
"""

import random
from typing import Optional
import db
from ai_providers.router import route_inference

# ---------------------------------------------------------------------------
# Question banks
# ---------------------------------------------------------------------------

_BEHAVIORAL_QUESTIONS = [
    ("Tell me about a time you led a team through a significant change.", "Leadership, change management, stakeholder communication, measurable outcome."),
    ("Describe a situation where you had to deliver difficult feedback to a direct report.", "Empathy, clarity, specific example, follow-through."),
    ("Give me an example of a time you failed and what you learned from it.", "Self-awareness, accountability, concrete lesson, applied learning."),
    ("Tell me about a time you had to influence without authority.", "Persuasion, relationship-building, outcome, cross-functional."),
    ("Describe a time you managed competing priorities under a tight deadline.", "Prioritization, trade-offs, communication, result."),
    ("Tell me about the most complex project you've managed end-to-end.", "Scope, stakeholders, risks, delivery, metrics."),
    ("Give an example of when you used data to drive a major decision.", "Data sources, analysis, decision, impact."),
    ("Describe a time you had to rebuild trust with a team or stakeholder.", "Root cause, action plan, follow-through, outcome."),
    ("Tell me about a time you disagreed with your manager and what happened.", "Respectful challenge, evidence, resolution, relationship intact."),
    ("Give an example of how you've developed a high-performing team member.", "Coaching method, specific actions, growth achieved, retention."),
    ("Describe a situation where you had to make a decision with incomplete information.", "Risk tolerance, assumptions made, how you validated, outcome."),
    ("Tell me about a time you drove cost savings or improved efficiency.", "Baseline, approach, savings achieved, sustainability."),
    ("Describe how you've handled a significant organizational conflict.", "Root cause, approach, resolution, systemic change."),
    ("Give an example of launching a product or initiative from zero to one.", "Problem framing, team assembly, milestones, launch result."),
    ("Tell me about a time you had to pivot strategy mid-execution.", "Trigger, decision process, communication, new outcome."),
    ("Describe a time you advocated for a customer or end-user internally.", "Customer insight, internal resistance, advocacy approach, outcome."),
    ("Give an example of hiring or building a team under pressure.", "Criteria, process shortcuts, quality vs speed, result."),
    ("Tell me about a time you navigated ambiguity at the organizational level.", "Context, how you created clarity, stakeholder alignment, result."),
    ("Describe a situation where you had to scale something quickly.", "Baseline, constraints, scaling levers, outcome."),
    ("Tell me about a cross-functional initiative you drove. What made it hard?", "Stakeholder map, friction points, how you aligned, business outcome."),
]

_TECHNICAL_QUESTIONS = [
    ("Walk me through how you would design a system to handle 1 million concurrent users.", "Horizontal scaling, load balancing, caching layers, database sharding, CDN."),
    ("How do you approach building a data pipeline from ingestion to reporting?", "Source systems, ETL/ELT, warehouse choice, transformation, monitoring."),
    ("Explain the trade-offs between SQL and NoSQL databases for a high-write workload.", "Consistency vs availability, schema flexibility, indexing, operational overhead."),
    ("How would you structure an ML model deployment pipeline for production?", "Model versioning, CI/CD for ML, monitoring drift, rollback strategy."),
    ("Describe your approach to API design for a public developer platform.", "REST vs GraphQL, versioning, auth, rate limiting, documentation."),
    ("How do you ensure data quality in a distributed data environment?", "Schema validation, lineage tracking, anomaly detection, SLA monitoring."),
    ("Walk me through a zero-downtime database migration strategy.", "Blue/green schema, backward-compatible changes, feature flags, rollback plan."),
    ("How would you architect a real-time analytics platform?", "Event streaming, OLAP store, query latency SLAs, hot vs cold path."),
    ("Explain how you'd implement role-based access control in a multi-tenant SaaS.", "Tenant isolation, permission model, attribute-based vs role-based, audit log."),
    ("How do you approach capacity planning for a new service?", "Baseline benchmarks, load testing, headroom %, alert thresholds, auto-scaling."),
    ("Describe your approach to reducing technical debt at scale.", "Debt taxonomy, prioritization framework, ring-fencing, refactor vs rewrite."),
    ("How would you design an observability stack for a microservices system?", "Metrics, logs, traces, correlation IDs, SLOs, alerting runbooks."),
    ("Explain the CAP theorem and how it guides architectural decisions.", "Consistency, availability, partition tolerance, trade-off examples."),
    ("How do you manage secrets and credentials across a large engineering org?", "Vault, rotation policy, least-privilege, audit trails, CI/CD integration."),
    ("Walk me through how you'd evaluate and select a third-party vendor's technology.", "Build vs buy criteria, evaluation rubric, POC scope, security review, TCO."),
]

_SITUATIONAL_QUESTIONS = [
    ("Your flagship product has a critical outage affecting enterprise customers. You're the most senior person online. What do you do?", "Immediate triage, customer communication, escalation chain, blameless postmortem."),
    ("You've just been handed a team with low morale and high attrition. What's your 90-day plan?", "Listen tour, quick wins, systemic diagnosis, retention levers, culture signals."),
    ("A key executive sponsor for your project leaves the company mid-delivery. How do you recover?", "New sponsor identification, relationship rebuild, re-scoping risk, communication plan."),
    ("Your board approves a 20% budget cut. How do you decide what gets cut?", "Portfolio triage, strategic alignment, people vs programs, stakeholder communication."),
    ("A competitor launches a feature that directly undermines your product roadmap. What's your response?", "Competitive analysis, differentiation strategy, customer perception, roadmap adjustments."),
    ("You discover a compliance risk in a shipped product feature. What do you do?", "Severity assessment, legal/compliance loop-in, user notification decision, remediation timeline."),
    ("Your highest performer wants to leave for a startup. How do you handle the conversation?", "Understand motivations, retention options, succession planning, transparent dialogue."),
    ("You're asked to deliver a project in half the time with the same scope. What do you do?", "Scope negotiation, risk surface, resource augmentation, definition of done."),
    ("A major customer is threatening to churn due to a service issue your team caused. You get the escalation call.", "Ownership, immediate relief, root cause timeline, relationship repair plan."),
    ("Your team is split 50/50 on a technical direction. You have to break the tie. How?", "Evidence gathering, reversibility test, time-box the debate, make the call, communicate."),
]

_CASE_QUESTIONS = [
    ("Estimate the total addressable market for a B2B SaaS HR platform targeting mid-market companies in the US.", "Company count by size, penetration rate, ACV assumption, bottoms-up vs tops-down."),
    ("A SaaS company's net revenue retention has dropped from 115% to 95% over 18 months. Diagnose and prescribe.", "Cohort analysis, expansion vs churn decomposition, product-market fit signals, remediation."),
    ("You're the CPO. Retention is flat. DAU is growing. What's your read and what do you do?", "Retention vs engagement decoupling, leading indicators, feature adoption analysis."),
    ("A sales team is hitting quota but NPS is 22. What do you investigate?", "Sales-to-delivery handoff, expectations vs reality, support ticket analysis, win/loss."),
    ("You have $5M and 18 months to grow ARR by 40%. How do you allocate?", "Unit economics, CAC payback, channel mix, headcount vs programs, scenario modeling."),
]

_QUESTION_BANK = {
    "behavioral": _BEHAVIORAL_QUESTIONS,
    "technical": _TECHNICAL_QUESTIONS,
    "situational": _SITUATIONAL_QUESTIONS,
    "case": _CASE_QUESTIONS,
}

_TYPE_MIX = {
    "behavioral": ["behavioral"],
    "technical": ["technical", "behavioral"],
    "situational": ["situational", "behavioral"],
    "case": ["case", "situational"],
    "mixed": ["behavioral", "technical", "situational"],
}

_DIFFICULTY_MULTIPLIER = {
    "easy": 0,    # pick from first half of bank
    "medium": 1,  # pick from full bank
    "hard": 2,    # bias toward later (harder) questions in bank
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pick_questions(qtype: str, count: int, difficulty: str) -> list[tuple[str, str]]:
    """Pick `count` questions from the bank for the given type and difficulty."""
    bank = _QUESTION_BANK.get(qtype, _BEHAVIORAL_QUESTIONS)
    if difficulty == "easy":
        pool = bank[: max(len(bank) // 2, count)]
    elif difficulty == "hard":
        pool = bank[max(0, len(bank) // 2 - count) :]
    else:
        pool = bank
    # Avoid duplicates; if pool is smaller than count, allow repeats via sample with replacement
    if len(pool) >= count:
        return random.sample(pool, count)
    return random.choices(pool, k=count)


def _build_suggested_answer(question_text: str, key_points: str, difficulty: str) -> str:
    """Build a suggested answer template from key points."""
    intro = {
        "easy": "A strong answer covers: ",
        "medium": "An ideal response demonstrates: ",
        "hard": "A compelling answer at this level integrates: ",
    }.get(difficulty, "Key elements: ")
    return f"{intro}{key_points} — Use the STAR format (Situation, Task, Action, Result) with concrete metrics."


def _generate_questions(
    interview_type: str,
    difficulty: str,
    count: int,
    start_number: int,
    interview_id: int,
) -> list[dict]:
    """Generate and persist questions for an interview. Returns list of question dicts."""
    types = _TYPE_MIX.get(interview_type, ["behavioral"])
    per_type = max(1, count // len(types))
    remainder = count - (per_type * len(types))

    picks: list[tuple[str, tuple[str, str]]] = []
    for i, qtype in enumerate(types):
        n = per_type + (1 if i < remainder else 0)
        for q in _pick_questions(qtype, n, difficulty):
            picks.append((qtype, q))

    # Shuffle so types are interleaved
    random.shuffle(picks)
    picks = picks[:count]

    inserted = []
    for idx, (qtype, (question_text, key_points)) in enumerate(picks):
        suggested = _build_suggested_answer(question_text, key_points, difficulty)
        row = db.execute_returning(
            """
            INSERT INTO mock_interview_questions
                (mock_interview_id, question_number, question_type, question_text, suggested_answer)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (interview_id, start_number + idx, qtype, question_text, suggested),
        )
        inserted.append(row)
    return inserted


def _score_answer(user_answer: str, suggested_answer: str) -> tuple[int, str]:
    """Simple keyword-coverage scoring. Returns (score 1-10, feedback str)."""
    if not user_answer or not user_answer.strip():
        return 0, "No answer provided."

    # Extract meaningful keywords from the suggested answer (skip stop words)
    stop = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "is", "are", "was", "were", "be", "been", "use", "using",
            "your", "you", "this", "that", "how", "what", "when", "where", "why"}
    keywords = [
        w.lower().strip(".,;:()-")
        for w in suggested_answer.split()
        if len(w) > 3 and w.lower() not in stop
    ]
    keywords = list(set(keywords))

    if not keywords:
        return 5, "Answer received. Unable to score automatically — review manually."

    answer_lower = user_answer.lower()
    hits = sum(1 for kw in keywords if kw in answer_lower)
    coverage = hits / len(keywords)

    # Length bonus: penalize very short answers
    word_count = len(user_answer.split())
    length_factor = min(1.0, word_count / 80)  # 80 words = full length credit

    raw = (coverage * 0.7 + length_factor * 0.3) * 10
    score = max(1, min(10, round(raw)))

    if score >= 8:
        feedback = "Strong answer — covers the key themes with depth. Ensure you quantify the outcome explicitly."
    elif score >= 6:
        feedback = "Solid answer. Strengthen it by adding specific metrics and a clearer result statement."
    elif score >= 4:
        feedback = "Partial answer. Missing several key themes. Use the STAR framework: Situation, Task, Action, Result."
    else:
        feedback = "Answer needs significant development. Review the suggested answer and rebuild using STAR format with concrete examples."

    return score, feedback


# ---------------------------------------------------------------------------
# Public MCP tool functions
# ---------------------------------------------------------------------------

def create_mock_interview(
    job_title: str,
    company: str,
    interview_type: str = "behavioral",
    difficulty: str = "medium",
    application_id: Optional[int] = None,
) -> dict:
    """Create a mock interview session and generate 5 starter questions.

    Args:
        job_title: Title of the role being interviewed for.
        company: Company name.
        interview_type: One of behavioral, technical, case, mixed.
        difficulty: One of easy, medium, hard.
        application_id: Optional link to an application row.

    Returns:
        Interview dict with nested `questions` list.
    """
    valid_types = {"behavioral", "technical", "case", "mixed", "situational"}
    valid_diffs = {"easy", "medium", "hard"}
    interview_type = interview_type if interview_type in valid_types else "behavioral"
    difficulty = difficulty if difficulty in valid_diffs else "medium"

    interview = db.execute_returning(
        """
        INSERT INTO mock_interviews
            (application_id, job_title, company, interview_type, difficulty, status)
        VALUES (%s, %s, %s, %s, %s, 'pending')
        RETURNING *
        """,
        (application_id, job_title, company, interview_type, difficulty),
    )

    questions = _generate_questions(
        interview_type=interview_type,
        difficulty=difficulty,
        count=5,
        start_number=1,
        interview_id=interview["id"],
    )
    interview["questions"] = questions
    return interview


def get_mock_interview(interview_id: int) -> Optional[dict]:
    """Fetch a mock interview with all its questions.

    Args:
        interview_id: Primary key of the mock_interviews row.

    Returns:
        Interview dict with nested `questions` list, or None if not found.
    """
    interview = db.query_one(
        "SELECT * FROM mock_interviews WHERE id = %s", (interview_id,)
    )
    if not interview:
        return None
    interview["questions"] = db.query(
        "SELECT * FROM mock_interview_questions WHERE mock_interview_id = %s ORDER BY question_number",
        (interview_id,),
    )
    return interview


def evaluate_mock_interview(interview_id: int, answers: dict) -> dict:
    """Score all questions, compute overall score, and mark interview complete.

    Args:
        interview_id: Primary key of the mock_interviews row.
        answers: Optional dict of {question_id (str or int): answer_text} overrides.
                 Questions already having a user_answer in the DB are scored too.

    Returns:
        Full interview dict with evaluated questions and overall_score.
    """
    interview = db.query_one(
        "SELECT * FROM mock_interviews WHERE id = %s", (interview_id,)
    )
    if not interview:
        return {"error": "Interview not found"}

    questions = db.query(
        "SELECT * FROM mock_interview_questions WHERE mock_interview_id = %s ORDER BY question_number",
        (interview_id,),
    )

    scores = []
    evaluated = []
    for q in questions:
        qid = q["id"]
        # Accept answer override from caller, fall back to stored answer
        user_answer = answers.get(str(qid)) or answers.get(qid) or q.get("user_answer") or ""
        score, feedback = _score_answer(user_answer, q.get("suggested_answer") or "")

        db.execute(
            """
            UPDATE mock_interview_questions
            SET user_answer = %s, score = %s, feedback = %s
            WHERE id = %s
            """,
            (user_answer if user_answer else q.get("user_answer"), score, feedback, qid),
        )
        scores.append(score)
        evaluated.append({**q, "user_answer": user_answer, "score": score, "feedback": feedback})

    # overall_score = average of question scores * 10 (normalized to 1-100)
    if scores:
        avg = sum(scores) / len(scores)
        overall_score = max(1, min(100, round(avg * 10)))
    else:
        overall_score = None

    def _python_interview_feedback(ctx):
        score = ctx["overall_score"]
        if score is None:
            return {"overall_feedback": "No answers were submitted for evaluation."}
        if score >= 80:
            fb = "Strong performance. You demonstrated clear command of the subject with structured, metric-driven responses. Focus on tightening any remaining vague answers."
        elif score >= 60:
            fb = "Solid performance with room to grow. Your answers showed good instincts but lacked consistent specificity. Add more quantified outcomes and tighten your STAR structure."
        elif score >= 40:
            fb = "Developing performance. Several answers need more depth and concrete examples. Practice the STAR framework and prepare 2-3 strong stories per competency."
        else:
            fb = "Needs significant preparation. Focus on building a library of specific, metric-backed stories. Review the suggested answers and practice delivering structured responses."
        return {"overall_feedback": fb}

    feedback_ctx = {
        "overall_score": overall_score,
        "evaluated_questions": [
            {"question": q.get("question_text", ""), "score": q.get("score"), "answer": q.get("user_answer", "")}
            for q in evaluated
        ],
        "interview_type": interview.get("interview_type"),
        "role": interview.get("role"),
    }
    fb_result = route_inference(
        task="evaluate_mock_interview_feedback",
        context=feedback_ctx,
        python_fallback=_python_interview_feedback,
    )
    overall_feedback = fb_result.get("overall_feedback", "")

    db.execute(
        """
        UPDATE mock_interviews
        SET status = 'completed', overall_score = %s, overall_feedback = %s,
            completed_at = NOW()
        WHERE id = %s
        """,
        (overall_score, overall_feedback, interview_id),
    )

    result = {**interview, "overall_score": overall_score, "overall_feedback": overall_feedback,
              "status": "completed", "questions": evaluated}
    return result
