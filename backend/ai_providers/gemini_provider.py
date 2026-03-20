"""Gemini CLI adapter stub."""
import subprocess
from .base import AIProvider


class GeminiProvider(AIProvider):
    """Stub adapter for the Gemini CLI. parse_resume and resolve_duplicate not yet implemented."""
    name = "gemini"
    cli_command = "gemini"

    def parse_resume(self, text: str) -> dict:
        raise NotImplementedError("GeminiProvider.parse_resume is not yet implemented.")

    def resolve_duplicate(self, bullet_a: str, bullet_b: str) -> dict:
        raise NotImplementedError("GeminiProvider.resolve_duplicate is not yet implemented.")

    def health_check(self) -> dict:
        """Check if Gemini CLI is available and return version info."""
        if not self.is_available():
            return {"available": False, "version": None, "model": None}
        try:
            result = subprocess.run(
                [self.cli_command, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            version = result.stdout.strip() or result.stderr.strip()
            return {"available": True, "version": version, "model": "gemini-pro"}
        except Exception as e:
            return {"available": False, "version": None, "model": None, "error": str(e)}
