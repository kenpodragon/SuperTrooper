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
