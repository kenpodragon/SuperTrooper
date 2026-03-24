"""Abstract base class for AI provider adapters."""
import shutil
import subprocess
import json
from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Base class for AI CLI adapters. Each wraps a locally-installed CLI tool."""
    name: str = ""
    cli_command: str = ""

    def is_available(self) -> bool:
        """Check if the CLI is installed and on PATH."""
        return shutil.which(self.cli_command) is not None

    @abstractmethod
    def parse_resume(self, text: str) -> dict:
        """Parse resume text into structured JSON.
        Returns: {"career_history": [], "bullets": [], "skills": [], "confidence": float}
        """

    @abstractmethod
    def resolve_duplicate(self, bullet_a: str, bullet_b: str) -> dict:
        """Ask AI which bullet is better or merge them.
        Returns: {"action": "keep_a"|"keep_b"|"merge", "result": str, "reason": str}
        """

    @abstractmethod
    def ats_analysis(self, resume_text: str, jd_text: str) -> dict:
        """ATS scoring with strengths/weaknesses/suggestions.
        Returns: {"score": int, "strengths": [], "weaknesses": [], "suggestions": [], "keyword_matches": [], "missing_keywords": []}
        """

    @abstractmethod
    def score_answer(self, question: str, answer: str, suggested_answer: str) -> dict:
        """Evaluate a mock interview answer against a suggested answer.
        Returns: {"score": int, "feedback": str, "strengths": [], "improvements": [], "revised_answer": str}
        """

    @abstractmethod
    def build_suggested_answer(self, question: str, context: dict) -> dict:
        """Generate a model STAR answer for an interview question.
        Returns: {"suggested_answer": str, "key_points": [], "star_breakdown": {"situation": str, "task": str, "action": str, "result": str}}
        """

    @abstractmethod
    def analyze_strategy(self, rollup_data: dict) -> dict:
        """Generate campaign strategy recommendations from weekly rollup data.
        Returns: {"recommendations": [], "priority_actions": [], "insights": [], "risk_areas": []}
        """

    @abstractmethod
    def semantic_match(self, resume_text: str, jd_text: str) -> dict:
        """Semantic JD matching beyond keywords.
        Returns: {"match_score": float, "aligned_themes": [], "gaps": [], "positioning_suggestions": []}
        """

    @abstractmethod
    def check_voice_ai(self, text: str, rules: list) -> dict:
        """Detect subtle voice violations that rule-based checks miss.
        Returns: {"violations": [{"text": str, "rule": str, "suggestion": str}], "overall_score": float, "passes": bool}
        """

    @abstractmethod
    def score_fit(self, skills: list, jd_text: str) -> dict:
        """Semantic fit scoring between candidate skills and a JD.
        Returns: {"fit_score": float, "matched_skills": [], "missing_skills": [], "transferable_skills": []}
        """

    @abstractmethod
    def analyze_email(self, email_text: str) -> dict:
        """Categorize email intent (recruiter outreach, rejection, offer, follow-up, etc.).
        Returns: {"intent": str, "confidence": float, "entities": {"company": str, "role": str, "sender_type": str}, "suggested_action": str}
        """

    @abstractmethod
    def generate_content(self, task_type: str, context: dict) -> dict:
        """Generate content: cover_letter, thank_you, outreach, linkedin_post, headline.
        Returns: {"content": str, "metadata": dict}
        """

    @abstractmethod
    def audit_profile(self, profile_data: dict, target_jds: list) -> dict:
        """LinkedIn profile audit against target JDs.
        Returns: {"overall_score": float, "sections": [{"name": str, "score": float, "suggestions": []}], "keyword_gaps": [], "headline_suggestions": []}
        """

    @abstractmethod
    def parse_jd(self, jd_text: str) -> dict:
        """Parse a job description into structured fields.
        Returns: {"title": str, "company": str, "requirements": [], "nice_to_haves": [], "responsibilities": [], "skills": [], "experience_years": int, "education": str, "salary_range": str}
        """

    @abstractmethod
    def analyze_skills(self, skills: list, jd_texts: list) -> dict:
        """Skill demand/gap/trend analysis across multiple JDs.
        Returns: {"in_demand": [], "gaps": [], "emerging": [], "declining": [], "recommendations": []}
        """

    @abstractmethod
    def compare_offers(self, offers: list) -> dict:
        """Compare multiple job offers with qualitative analysis.
        Returns: {"ranking": [], "comparison_matrix": [], "trade_offs": [], "recommendation": str}
        """

    @abstractmethod
    def benchmark_offer(self, offer: dict, salary_data: dict) -> dict:
        """Benchmark an offer against market data and generate negotiation points.
        Returns: {"assessment": str, "percentile": float, "negotiation_points": [], "counter_suggestion": dict}
        """

    @abstractmethod
    def summarize_market(self, signals: list) -> dict:
        """Generate a market intelligence narrative from signals.
        Returns: {"summary": str, "trends": [], "opportunities": [], "threats": [], "action_items": []}
        """

    def generate(self, prompt: str, response_format: str = "json") -> "str | dict":
        """Generic prompt — send any prompt and get a response back.
        Args:
            prompt: The full prompt text.
            response_format: "json" to parse response as JSON, "text" for raw string.
        Returns: parsed JSON dict or raw string.
        """
        return self._run_cli(prompt, expect_json=(response_format == "json"))

    @abstractmethod
    def health_check(self) -> dict:
        """Returns: {"available": bool, "version": str, "model": str}"""

    def _run_cli(self, prompt: str, expect_json: bool = True) -> "str | dict":
        """Run CLI with prompt. Subclasses can override for different CLI interfaces."""
        try:
            result = subprocess.run(
                [self.cli_command, "prompt", "--format", "json" if expect_json else "text"],
                input=prompt, capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(f"{self.name} CLI error: {result.stderr}")
            if expect_json:
                return json.loads(result.stdout)
            return result.stdout
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{self.name} CLI timed out after 120s")
        except json.JSONDecodeError:
            raise RuntimeError(f"{self.name} returned invalid JSON: {result.stdout[:200]}")
