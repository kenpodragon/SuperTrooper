"""OpenAI CLI adapter stub."""
import subprocess
from .base import AIProvider


class OpenAIProvider(AIProvider):
    """Stub adapter for the OpenAI CLI. parse_resume and resolve_duplicate not yet implemented."""
    name = "openai"
    cli_command = "openai"

    def parse_resume(self, text: str) -> dict:
        raise NotImplementedError("OpenAIProvider.parse_resume is not yet implemented.")

    def resolve_duplicate(self, bullet_a: str, bullet_b: str) -> dict:
        raise NotImplementedError("OpenAIProvider.resolve_duplicate is not yet implemented.")

    def ats_analysis(self, resume_text: str, jd_text: str) -> dict:
        raise NotImplementedError("OpenAIProvider.ats_analysis is not yet implemented.")

    def score_answer(self, question: str, answer: str, suggested_answer: str) -> dict:
        raise NotImplementedError("OpenAIProvider.score_answer is not yet implemented.")

    def build_suggested_answer(self, question: str, context: dict) -> dict:
        raise NotImplementedError("OpenAIProvider.build_suggested_answer is not yet implemented.")

    def analyze_strategy(self, rollup_data: dict) -> dict:
        raise NotImplementedError("OpenAIProvider.analyze_strategy is not yet implemented.")

    def semantic_match(self, resume_text: str, jd_text: str) -> dict:
        raise NotImplementedError("OpenAIProvider.semantic_match is not yet implemented.")

    def check_voice_ai(self, text: str, rules: list) -> dict:
        raise NotImplementedError("OpenAIProvider.check_voice_ai is not yet implemented.")

    def score_fit(self, skills: list, jd_text: str) -> dict:
        raise NotImplementedError("OpenAIProvider.score_fit is not yet implemented.")

    def analyze_email(self, email_text: str) -> dict:
        raise NotImplementedError("OpenAIProvider.analyze_email is not yet implemented.")

    def generate_content(self, task_type: str, context: dict) -> dict:
        raise NotImplementedError("OpenAIProvider.generate_content is not yet implemented.")

    def audit_profile(self, profile_data: dict, target_jds: list) -> dict:
        raise NotImplementedError("OpenAIProvider.audit_profile is not yet implemented.")

    def parse_jd(self, jd_text: str) -> dict:
        raise NotImplementedError("OpenAIProvider.parse_jd is not yet implemented.")

    def analyze_skills(self, skills: list, jd_texts: list) -> dict:
        raise NotImplementedError("OpenAIProvider.analyze_skills is not yet implemented.")

    def compare_offers(self, offers: list) -> dict:
        raise NotImplementedError("OpenAIProvider.compare_offers is not yet implemented.")

    def benchmark_offer(self, offer: dict, salary_data: dict) -> dict:
        raise NotImplementedError("OpenAIProvider.benchmark_offer is not yet implemented.")

    def summarize_market(self, signals: list) -> dict:
        raise NotImplementedError("OpenAIProvider.summarize_market is not yet implemented.")

    def health_check(self) -> dict:
        """Check if OpenAI CLI is available and return version info."""
        if not self.is_available():
            return {"available": False, "version": None, "model": None}
        try:
            result = subprocess.run(
                [self.cli_command, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            version = result.stdout.strip() or result.stderr.strip()
            return {"available": True, "version": version, "model": "gpt-4o"}
        except Exception as e:
            return {"available": False, "version": None, "model": None, "error": str(e)}
