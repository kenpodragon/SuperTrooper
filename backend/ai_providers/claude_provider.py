"""Claude CLI adapter using `claude -p` for non-interactive prompts."""
import subprocess
import json
import re

from .base import AIProvider

PARSE_PROMPT = """You are a resume parser. Extract structured data from the resume text below.

Return ONLY valid JSON matching this exact schema:
{
  "career_history": [
    {
      "company": "string",
      "title": "string",
      "start_date": "YYYY-MM or null",
      "end_date": "YYYY-MM or null (null if current)",
      "is_current": true/false,
      "description": "string or null"
    }
  ],
  "bullets": [
    {
      "company": "string",
      "title": "string",
      "text": "string (the bullet point)",
      "has_metric": true/false
    }
  ],
  "skills": ["string", ...],
  "confidence": 0.0
}

Rules:
- confidence is 0.0-1.0, reflecting how complete/clean the parse is
- has_metric is true if the bullet contains a number, percentage, dollar amount, or measurable outcome
- Include ALL bullet points found under each role
- skills is a flat list of all technical and soft skills mentioned

Resume text:
---
{resume_text}
---

Return ONLY the JSON object, no explanation."""

DUPLICATE_PROMPT = """You are evaluating two resume bullet points that may be duplicates.

Bullet A: {bullet_a}

Bullet B: {bullet_b}

Decide what to do. Return ONLY valid JSON matching this schema:
{
  "action": "keep_a" | "keep_b" | "merge",
  "result": "the winning bullet text or merged text",
  "reason": "one sentence explanation"
}

Rules:
- keep_a: Bullet A is clearly better (more specific, stronger metric, better wording)
- keep_b: Bullet B is clearly better
- merge: Both have unique value — combine into one stronger bullet
- result must be a complete, standalone bullet point ready for a resume
- reason must be concise (under 20 words)

Return ONLY the JSON object."""

ATS_PROMPT = """You are an ATS (Applicant Tracking System) scoring expert. Analyze how well this resume matches the job description.

Resume:
---
{resume_text}
---

Job Description:
---
{jd_text}
---

Return ONLY valid JSON:
{{
  "score": 0-100,
  "strengths": ["strength1", "strength2", ...],
  "weaknesses": ["weakness1", "weakness2", ...],
  "suggestions": ["actionable suggestion1", ...],
  "keyword_matches": ["keyword1", "keyword2", ...],
  "missing_keywords": ["missing1", "missing2", ...]
}}

Rules:
- score is 0-100 based on keyword density, experience alignment, and skills match
- strengths: what the resume does well for this role
- weaknesses: gaps or misalignments
- suggestions: specific, actionable improvements
- keyword_matches: JD keywords found in resume
- missing_keywords: important JD keywords NOT in resume

Return ONLY the JSON object."""

SCORE_ANSWER_PROMPT = """You are an interview coach evaluating a candidate's answer to an interview question.

Question: {question}

Candidate's Answer:
---
{answer}
---

Suggested/Model Answer:
---
{suggested_answer}
---

Return ONLY valid JSON:
{{
  "score": 1-10,
  "feedback": "2-3 sentence evaluation",
  "strengths": ["what they did well"],
  "improvements": ["specific improvements"],
  "revised_answer": "improved version of their answer incorporating the feedback"
}}

Rules:
- score 1-10 (10 = perfect STAR answer with metrics)
- feedback should be constructive and specific
- revised_answer should sound natural, not robotic

Return ONLY the JSON object."""

BUILD_ANSWER_PROMPT = """You are an interview coach building a model STAR answer for a behavioral interview question.

Question: {question}

Candidate Context:
{context_json}

Return ONLY valid JSON:
{{
  "suggested_answer": "full STAR-formatted answer (2-3 paragraphs, conversational tone)",
  "key_points": ["point to emphasize 1", "point 2", ...],
  "star_breakdown": {{
    "situation": "the context/challenge",
    "task": "what needed to be done",
    "action": "specific steps taken",
    "result": "measurable outcome"
  }}
}}

Rules:
- Use specific details from the candidate context when available
- Include concrete metrics or measurable outcomes in the result
- Keep the tone conversational, not corporate
- Use ellipses not em dashes

Return ONLY the JSON object."""

STRATEGY_PROMPT = """You are a job search strategist analyzing a candidate's campaign data.

Campaign Data:
{rollup_json}

Return ONLY valid JSON:
{{
  "recommendations": ["strategic recommendation 1", ...],
  "priority_actions": ["urgent action 1", ...],
  "insights": ["data-driven insight 1", ...],
  "risk_areas": ["risk or concern 1", ...]
}}

Rules:
- recommendations: strategic moves based on the data (3-5)
- priority_actions: things to do this week (2-3)
- insights: patterns or trends in the data
- risk_areas: pipeline gaps, stale applications, timing concerns

Return ONLY the JSON object."""

SEMANTIC_MATCH_PROMPT = """You are a career alignment expert. Analyze the semantic fit between this resume and job description, going beyond keyword matching.

Resume:
---
{resume_text}
---

Job Description:
---
{jd_text}
---

Return ONLY valid JSON:
{{
  "match_score": 0.0-1.0,
  "aligned_themes": ["theme where resume and JD align", ...],
  "gaps": ["area where JD wants something resume lacks", ...],
  "positioning_suggestions": ["how to better position for this role", ...]
}}

Rules:
- match_score: 0.0-1.0 semantic alignment (not just keywords)
- aligned_themes: conceptual areas of strong fit
- gaps: meaningful capability gaps (not just missing buzzwords)
- positioning_suggestions: concrete ways to reframe experience

Return ONLY the JSON object."""

CHECK_VOICE_PROMPT = """You are an editorial voice analyst. Check this text against writing rules to find subtle violations that simple pattern matching would miss.

Text to check:
---
{text}
---

Voice rules:
{rules_json}

Return ONLY valid JSON:
{{
  "violations": [
    {{"text": "the offending phrase", "rule": "which rule it violates", "suggestion": "rewrite suggestion"}}
  ],
  "overall_score": 0.0-1.0,
  "passes": true/false
}}

Rules:
- Find SUBTLE violations: corporate jargon disguised in context, passive voice buried in clauses, overly complex sentence structures
- overall_score: 1.0 = perfect adherence, 0.0 = total violation
- passes: true if score >= 0.8

Return ONLY the JSON object."""

SCORE_FIT_PROMPT = """You are a recruiter evaluating candidate-job fit. Score how well these skills match the job description semantically.

Candidate Skills:
{skills_json}

Job Description:
---
{jd_text}
---

Return ONLY valid JSON:
{{
  "fit_score": 0.0-1.0,
  "matched_skills": ["skill that directly matches JD need", ...],
  "missing_skills": ["JD requirement candidate lacks", ...],
  "transferable_skills": ["candidate skill that could transfer to JD need", ...]
}}

Rules:
- fit_score: semantic match, not just keyword overlap
- matched_skills: direct matches (skill name or clear equivalent)
- missing_skills: hard requirements the candidate lacks
- transferable_skills: adjacent skills that could bridge gaps

Return ONLY the JSON object."""

ANALYZE_EMAIL_PROMPT = """You are an email intelligence analyst for a job seeker. Categorize this email.

Email:
---
{email_text}
---

Return ONLY valid JSON:
{{
  "intent": "recruiter_outreach|rejection|offer|interview_invite|follow_up|status_update|newsletter|spam|other",
  "confidence": 0.0-1.0,
  "entities": {{
    "company": "company name or null",
    "role": "job title or null",
    "sender_type": "recruiter|hiring_manager|hr|automated|unknown"
  }},
  "suggested_action": "reply|archive|track_application|schedule_interview|negotiate|ignore"
}}

Return ONLY the JSON object."""

GENERATE_CONTENT_PROMPT = """You are a career content writer. Generate {task_type} content.

Context:
{context_json}

Return ONLY valid JSON:
{{
  "content": "the generated text",
  "metadata": {{
    "word_count": 0,
    "tone": "professional|conversational|formal",
    "task_type": "{task_type}"
  }}
}}

Rules for each task_type:
- cover_letter: 3-4 paragraphs, specific to the role, mention company by name, connect experience to requirements
- thank_you: brief, reference specific interview discussion points, reaffirm interest
- outreach: short, personalized, clear ask, not salesy
- linkedin_post: conversational, insight-driven, no hashtag spam (3 max), hook in first line
- headline: under 120 chars, keyword-rich, value proposition clear

Style rules:
- Conversational and direct, not corporate
- Use ellipses not em dashes
- Fifth-grade reading level
- No buzzwords: leverage, synergy, spearhead, utilize, cutting-edge, passionate

Return ONLY the JSON object."""

AUDIT_PROFILE_PROMPT = """You are a LinkedIn optimization expert. Audit this profile against target job descriptions.

Profile:
{profile_json}

Target JDs:
{jds_json}

Return ONLY valid JSON:
{{
  "overall_score": 0.0-1.0,
  "sections": [
    {{"name": "headline|about|experience|skills|education", "score": 0.0-1.0, "suggestions": ["improvement 1", ...]}}
  ],
  "keyword_gaps": ["keyword missing from profile but common in target JDs", ...],
  "headline_suggestions": ["suggested headline 1", "suggested headline 2", ...]
}}

Rules:
- Score each section independently
- keyword_gaps: terms that appear in 2+ target JDs but not in profile
- headline_suggestions: 3 options, each under 120 chars

Return ONLY the JSON object."""

PARSE_JD_PROMPT = """You are a job description parser. Extract structured data from this JD.

Job Description:
---
{jd_text}
---

Return ONLY valid JSON:
{{
  "title": "job title",
  "company": "company name or null",
  "requirements": ["hard requirement 1", ...],
  "nice_to_haves": ["preferred qualification 1", ...],
  "responsibilities": ["key responsibility 1", ...],
  "skills": ["technical or soft skill 1", ...],
  "experience_years": null or integer,
  "education": "degree requirement or null",
  "salary_range": "salary info or null"
}}

Rules:
- requirements vs nice_to_haves: "must have" / "required" → requirements; "preferred" / "nice to have" / "bonus" → nice_to_haves
- experience_years: extract the minimum years mentioned, null if not stated
- skills: flat list of all technical and soft skills mentioned
- salary_range: extract if mentioned, null otherwise

Return ONLY the JSON object."""

ANALYZE_SKILLS_PROMPT = """You are a labor market analyst. Analyze skill demand patterns across these job descriptions.

Candidate Skills:
{skills_json}

Job Descriptions:
{jds_json}

Return ONLY valid JSON:
{{
  "in_demand": [{{"skill": "name", "frequency": 0, "context": "how it's used"}}],
  "gaps": [{{"skill": "name", "importance": "critical|high|medium", "recommendation": "how to acquire"}}],
  "emerging": ["skill trending up in these JDs"],
  "declining": ["skill becoming less relevant"],
  "recommendations": ["strategic skill development suggestion"]
}}

Rules:
- in_demand: skills appearing in multiple JDs, sorted by frequency
- gaps: skills the candidate lacks but JDs want
- emerging/declining: based on JD language patterns

Return ONLY the JSON object."""

COMPARE_OFFERS_PROMPT = """You are a compensation analyst comparing job offers.

Offers:
{offers_json}

Return ONLY valid JSON:
{{
  "ranking": [{{"company": "name", "rank": 1, "rationale": "why this rank"}}],
  "comparison_matrix": [{{"dimension": "base_salary|total_comp|growth|culture|remote|benefits", "values": {{"Company A": "value", "Company B": "value"}}}}],
  "trade_offs": ["key trade-off to consider"],
  "recommendation": "1-2 sentence recommendation"
}}

Rules:
- ranking: best to worst based on total value (not just salary)
- comparison_matrix: cover at least 5 dimensions
- trade_offs: honest, specific trade-offs between top options

Return ONLY the JSON object."""

BENCHMARK_OFFER_PROMPT = """You are a salary negotiation coach. Benchmark this offer against market data.

Offer:
{offer_json}

Market/Salary Data:
{salary_json}

Return ONLY valid JSON:
{{
  "assessment": "above_market|at_market|below_market",
  "percentile": 0-100,
  "negotiation_points": ["specific negotiation talking point 1", ...],
  "counter_suggestion": {{
    "base_salary": 0,
    "rationale": "why this counter is reasonable",
    "non_salary_asks": ["signing bonus", "extra PTO", "remote flexibility", ...]
  }}
}}

Rules:
- percentile: where this offer falls in the market data range
- negotiation_points: 3-5 specific, data-backed points
- counter_suggestion: realistic, not aggressive

Return ONLY the JSON object."""

SUMMARIZE_MARKET_PROMPT = """You are a market intelligence analyst for job seekers. Summarize these market signals into an actionable narrative.

Signals:
{signals_json}

Return ONLY valid JSON:
{{
  "summary": "2-3 paragraph market narrative",
  "trends": [{{"trend": "description", "direction": "up|down|stable", "impact": "how it affects job search"}}],
  "opportunities": ["opportunity to act on"],
  "threats": ["risk or headwind"],
  "action_items": ["specific thing to do this week"]
}}

Rules:
- summary: conversational, data-grounded narrative
- trends: 3-5 key trends with direction
- action_items: concrete, time-bound actions

Return ONLY the JSON object."""


class ClaudeProvider(AIProvider):
    """Adapter for the Claude CLI (claude -p)."""
    name = "claude"
    cli_command = "claude"

    def _run_cli(self, prompt: str, expect_json: bool = True) -> "str | dict":
        """Run claude -p <prompt> --output-format json."""
        try:
            cmd = [self.cli_command, "-p", prompt]
            if expect_json:
                cmd += ["--output-format", "json"]
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Claude CLI error: {result.stderr.strip()}")
            output = result.stdout.strip()
            if expect_json:
                # Claude --output-format json wraps in {"type":"result","result":"..."}
                # Try direct parse first, then unwrap
                try:
                    parsed = json.loads(output)
                    if isinstance(parsed, dict) and "result" in parsed:
                        inner = parsed["result"]
                        if isinstance(inner, str):
                            return json.loads(inner)
                        return inner
                    return parsed
                except json.JSONDecodeError:
                    # Try extracting JSON block from plain text
                    match = re.search(r'\{.*\}', output, re.DOTALL)
                    if match:
                        return json.loads(match.group())
                    raise RuntimeError(f"Claude returned invalid JSON: {output[:200]}")
            return output
        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude CLI timed out after 120s")

    def parse_resume(self, text: str) -> dict:
        """Parse resume text into structured JSON."""
        prompt = PARSE_PROMPT.format(resume_text=text)
        result = self._run_cli(prompt, expect_json=True)
        # Validate expected keys are present
        for key in ("career_history", "bullets", "skills", "confidence"):
            if key not in result:
                raise RuntimeError(f"Claude parse_resume missing key: {key}")
        return result

    def resolve_duplicate(self, bullet_a: str, bullet_b: str) -> dict:
        """Ask Claude which bullet is better or to merge them."""
        prompt = DUPLICATE_PROMPT.format(bullet_a=bullet_a, bullet_b=bullet_b)
        result = self._run_cli(prompt, expect_json=True)
        for key in ("action", "result", "reason"):
            if key not in result:
                raise RuntimeError(f"Claude resolve_duplicate missing key: {key}")
        if result["action"] not in ("keep_a", "keep_b", "merge"):
            raise RuntimeError(f"Claude returned invalid action: {result['action']}")
        return result

    def ats_analysis(self, resume_text: str, jd_text: str) -> dict:
        prompt = ATS_PROMPT.format(resume_text=resume_text, jd_text=jd_text)
        result = self._run_cli(prompt, expect_json=True)
        for key in ("score", "strengths", "weaknesses", "suggestions", "keyword_matches", "missing_keywords"):
            if key not in result:
                result[key] = [] if key != "score" else 0
        return result

    def score_answer(self, question: str, answer: str, suggested_answer: str) -> dict:
        prompt = SCORE_ANSWER_PROMPT.format(question=question, answer=answer, suggested_answer=suggested_answer)
        result = self._run_cli(prompt, expect_json=True)
        for key in ("score", "feedback", "strengths", "improvements", "revised_answer"):
            if key not in result:
                result[key] = [] if key in ("strengths", "improvements") else ""
        return result

    def build_suggested_answer(self, question: str, context: dict) -> dict:
        prompt = BUILD_ANSWER_PROMPT.format(question=question, context_json=json.dumps(context, indent=2))
        result = self._run_cli(prompt, expect_json=True)
        if "suggested_answer" not in result:
            result["suggested_answer"] = ""
        return result

    def analyze_strategy(self, rollup_data: dict) -> dict:
        prompt = STRATEGY_PROMPT.format(rollup_json=json.dumps(rollup_data, indent=2))
        result = self._run_cli(prompt, expect_json=True)
        for key in ("recommendations", "priority_actions", "insights", "risk_areas"):
            if key not in result:
                result[key] = []
        return result

    def semantic_match(self, resume_text: str, jd_text: str) -> dict:
        prompt = SEMANTIC_MATCH_PROMPT.format(resume_text=resume_text, jd_text=jd_text)
        result = self._run_cli(prompt, expect_json=True)
        for key in ("match_score", "aligned_themes", "gaps", "positioning_suggestions"):
            if key not in result:
                result[key] = [] if key != "match_score" else 0.0
        return result

    def check_voice_ai(self, text: str, rules: list) -> dict:
        prompt = CHECK_VOICE_PROMPT.format(text=text, rules_json=json.dumps(rules, indent=2))
        result = self._run_cli(prompt, expect_json=True)
        if "violations" not in result:
            result["violations"] = []
        if "overall_score" not in result:
            result["overall_score"] = 1.0
        if "passes" not in result:
            result["passes"] = len(result["violations"]) == 0
        return result

    def score_fit(self, skills: list, jd_text: str) -> dict:
        prompt = SCORE_FIT_PROMPT.format(skills_json=json.dumps(skills), jd_text=jd_text)
        result = self._run_cli(prompt, expect_json=True)
        for key in ("fit_score", "matched_skills", "missing_skills", "transferable_skills"):
            if key not in result:
                result[key] = [] if key != "fit_score" else 0.0
        return result

    def analyze_email(self, email_text: str) -> dict:
        prompt = ANALYZE_EMAIL_PROMPT.format(email_text=email_text)
        result = self._run_cli(prompt, expect_json=True)
        if "intent" not in result:
            result["intent"] = "other"
        if "confidence" not in result:
            result["confidence"] = 0.0
        return result

    def generate_content(self, task_type: str, context: dict) -> dict:
        prompt = GENERATE_CONTENT_PROMPT.format(task_type=task_type, context_json=json.dumps(context, indent=2))
        result = self._run_cli(prompt, expect_json=True)
        if "content" not in result:
            result["content"] = ""
        if "metadata" not in result:
            result["metadata"] = {"task_type": task_type}
        return result

    def audit_profile(self, profile_data: dict, target_jds: list) -> dict:
        prompt = AUDIT_PROFILE_PROMPT.format(
            profile_json=json.dumps(profile_data, indent=2),
            jds_json=json.dumps(target_jds, indent=2),
        )
        result = self._run_cli(prompt, expect_json=True)
        for key in ("overall_score", "sections", "keyword_gaps", "headline_suggestions"):
            if key not in result:
                result[key] = [] if key != "overall_score" else 0.0
        return result

    def parse_jd(self, jd_text: str) -> dict:
        prompt = PARSE_JD_PROMPT.format(jd_text=jd_text)
        result = self._run_cli(prompt, expect_json=True)
        if "title" not in result:
            result["title"] = ""
        return result

    def analyze_skills(self, skills: list, jd_texts: list) -> dict:
        prompt = ANALYZE_SKILLS_PROMPT.format(
            skills_json=json.dumps(skills),
            jds_json=json.dumps(jd_texts, indent=2),
        )
        result = self._run_cli(prompt, expect_json=True)
        for key in ("in_demand", "gaps", "emerging", "declining", "recommendations"):
            if key not in result:
                result[key] = []
        return result

    def compare_offers(self, offers: list) -> dict:
        prompt = COMPARE_OFFERS_PROMPT.format(offers_json=json.dumps(offers, indent=2))
        result = self._run_cli(prompt, expect_json=True)
        for key in ("ranking", "comparison_matrix", "trade_offs", "recommendation"):
            if key not in result:
                result[key] = [] if key != "recommendation" else ""
        return result

    def benchmark_offer(self, offer: dict, salary_data: dict) -> dict:
        prompt = BENCHMARK_OFFER_PROMPT.format(
            offer_json=json.dumps(offer, indent=2),
            salary_json=json.dumps(salary_data, indent=2),
        )
        result = self._run_cli(prompt, expect_json=True)
        if "assessment" not in result:
            result["assessment"] = "at_market"
        return result

    def summarize_market(self, signals: list) -> dict:
        prompt = SUMMARIZE_MARKET_PROMPT.format(signals_json=json.dumps(signals, indent=2))
        result = self._run_cli(prompt, expect_json=True)
        for key in ("summary", "trends", "opportunities", "threats", "action_items"):
            if key not in result:
                result[key] = [] if key != "summary" else ""
        return result

    def health_check(self) -> dict:
        """Check if Claude CLI is available and return version info."""
        if not self.is_available():
            return {"available": False, "version": None, "model": None}
        try:
            result = subprocess.run(
                [self.cli_command, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            version = result.stdout.strip() or result.stderr.strip()
            return {
                "available": True,
                "version": version,
                "model": "claude-3-5-sonnet-20241022",  # default; overridable via env
            }
        except Exception as e:
            return {"available": False, "version": None, "model": None, "error": str(e)}
