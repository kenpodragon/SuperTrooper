"""
Indeed integration via Claude CLI tunnel.

Since there's no open-source Indeed MCP server, we use Claude CLI
as a tunnel to access Indeed MCP tools through Anthropic's infrastructure.

Requires Claude CLI to be installed and authenticated (.claude mount).
"""

import subprocess
import json
import logging
import shutil

log = logging.getLogger(__name__)

CLI_TIMEOUT = 60  # Claude CLI calls can be slow


def _find_cli() -> str | None:
    """Find the Claude CLI binary."""
    return shutil.which("claude")


def is_available() -> bool:
    """Check if Claude CLI is installed."""
    return _find_cli() is not None


def _call_claude(prompt: str, timeout: int = CLI_TIMEOUT) -> dict | None:
    """
    Call Claude CLI with a prompt and parse JSON response.

    Returns parsed dict or None on failure.
    """
    cli = _find_cli()
    if not cli:
        return None

    try:
        result = subprocess.run(
            [cli, "-p", prompt, "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            log.warning("Claude CLI failed: %s", result.stderr[:300])
            return None

        # Try to parse JSON from response
        output = result.stdout.strip()
        if not output:
            return None

        # Claude CLI may return wrapped JSON or plain text
        # Try to extract JSON block
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            # Look for JSON block in the output
            start = output.find("{")
            end = output.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(output[start:end])
                except json.JSONDecodeError:
                    pass

            # Return as text result
            return {"text": output, "raw": True}

    except subprocess.TimeoutExpired:
        log.warning("Claude CLI timed out after %ds", timeout)
        return None
    except Exception as e:
        log.error("Claude CLI error: %s", e)
        return None


def health_check() -> dict:
    """Test Indeed availability via Claude CLI."""
    if not is_available():
        return {
            "status": "not_installed",
            "message": "Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code",
        }

    # Quick version check
    cli = _find_cli()
    try:
        result = subprocess.run(
            [cli, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        version = result.stdout.strip() or result.stderr.strip()
        return {
            "status": "available",
            "message": f"Indeed available via Claude CLI ({version})",
            "cli_version": version,
            "method": "claude_cli",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def search_jobs(query: str, location: str = "", limit: int = 10) -> dict | None:
    """Search Indeed for jobs via Claude CLI tunnel."""
    prompt = f"""Use the Indeed MCP tools to search for jobs.
Query: {query}
{"Location: " + location if location else ""}
Limit: {limit}

Return the results as JSON with this structure:
{{"jobs": [{{"title": "...", "company": "...", "location": "...", "url": "...", "salary": "...", "snippet": "..."}}]}}

Only return the JSON, no other text."""

    return _call_claude(prompt)


def get_job_details(job_url: str) -> dict | None:
    """Get details for a specific Indeed job listing."""
    prompt = f"""Use the Indeed MCP tools to get details for this job:
{job_url}

Return the results as JSON with this structure:
{{"title": "...", "company": "...", "location": "...", "description": "...", "salary": "...", "requirements": ["..."], "url": "..."}}

Only return the JSON, no other text."""

    return _call_claude(prompt)


def get_company_data(company_name: str) -> dict | None:
    """Get company information from Indeed."""
    prompt = f"""Use the Indeed MCP tools to get company data for: {company_name}

Return the results as JSON with this structure:
{{"name": "...", "industry": "...", "size": "...", "rating": null, "reviews_count": null, "description": "..."}}

Only return the JSON, no other text."""

    return _call_claude(prompt)
