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
