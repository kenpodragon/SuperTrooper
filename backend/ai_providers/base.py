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
