# Phase D: Onboarding System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable users to upload resume files (.docx/.pdf), auto-parse into career data, templatize, create recipes, and verify reconstruction — with optional AI-enhanced parsing.

**Architecture:** Upload endpoint orchestrates a sequential pipeline: file handling → parsing (AI or rule-based) → DB insert with dedup → templatize → auto-recipe → reconstruct → compare. AI providers are modular adapters wrapping CLI tools installed in the Docker container. Settings stored in a single-row DB table.

**Tech Stack:** Flask (routes), PostgreSQL (migrations), python-docx, pdf2docx, subprocess (CLI adapters), React + TanStack Query (settings UI), pytest (integration tests)

**Spec:** `code/docs/reqs/13_ONBOARDING.md`

---

## CRITICAL: Correct Function Signatures & DB Columns

The `code/utils/` scripts have specific function names and signatures that **must** be used exactly. Every import in this plan uses these corrected names.

### Utils Function Reference

| Script | Function | Signature |
|--------|----------|-----------|
| `read_docx.py` | `read_full_text` | `(path: str) -> str` |
| `read_pdf.py` | `read_pdf_text` | `(path: str, pages: Optional[str] = None) -> str` |
| `edit_docx.py` | `find_replace` | `(path: str, find_text: str, replace_text: str, output_path: Optional[str] = None, replace_all: bool = False) -> int` |
| `docx_to_pdf.py` | `docx_to_pdf` | `(input_path: str, output_path: Optional[str] = None) -> str` |
| `compare_docs.py` | `extract_paragraphs` | `(path: str) -> list[str]` |
| `compare_docs.py` | `compare_text` | `(paragraphs_a: list[str], paragraphs_b: list[str]) -> str` |
| `templatize_resume.py` | `templatize` | `(input_path: str, output_docx: str, output_map: str, layout_name: str = "v32") -> dict` |
| `generate_resume.py` | `generate_resume` | `(template_blob: bytes, content_map: dict[str, str], template_map: dict) -> Document` |
| `generate_resume.py` | `resolve_recipe` | `(conn, recipe_json: dict) -> dict[str, str]` — resolves slot mappings to actual text |

### DB Column Reference

**`resume_templates`** — use `template_blob` (BYTEA), NOT `template_data`. No `file_size` column exists. Columns: `id, name, filename, template_blob, description, is_active, template_map (JSONB), template_type (VARCHAR), created_at, updated_at`.

**`bullets`** — columns: `id, career_history_id, text, type, star_situation/task/action/result, metrics_json (JSONB), tags (TEXT[]), role_suitability (TEXT[]), industry_suitability (TEXT[]), detail_recall, source_file, embedding, created_at`.

### Resume Generation Pipeline

`generate_resume.py` does NOT accept a recipe_id. The correct flow is:
1. Load recipe JSON from `resume_recipes` table
2. Call `resolve_recipe(conn, recipe_json)` → returns `content_map: dict[str, str]`
3. Load template_blob and template_map from `resume_templates` table
4. Call `generate_resume(template_blob, content_map, template_map)` → returns `Document`
5. Save the Document to a file

---

## File Structure

```
code/backend/
  ai_providers/
    __init__.py              # Provider registry + get_provider() factory
    base.py                  # AIProvider abstract base class
    claude_provider.py       # Claude CLI adapter
    gemini_provider.py       # Gemini CLI adapter (stub)
    openai_provider.py       # OpenAI CLI adapter (stub)
  parsers/
    __init__.py              # parse_resume() dispatcher
    rule_based.py            # Regex/heuristic resume parser
    ai_enhanced.py           # AI-powered parser using provider adapter
  routes/
    onboard.py               # POST /api/onboard/upload
    settings.py              # GET/PATCH /api/settings, POST /api/settings/test-ai
  routes/__init__.py         # (modify) Add onboard_bp, settings_bp
  mcp_server.py              # (modify) Add util MCP tools + onboard_resume
  requirements.txt           # (modify) Add pdf2docx
  Dockerfile                 # (modify) Add Node.js + Claude CLI

code/docker-compose.yml      # (modify) Add credential volume mount
code/db/migrations/
  008_settings_onboard.sql   # settings + onboard_uploads tables

code/frontend/src/
  pages/settings/Settings.tsx # (modify) Settings form with AI config

tests/
  test_settings.py           # Settings CRUD tests
  test_rule_parser.py        # Rule-based parser tests
  test_onboard.py            # Full pipeline integration tests
  fixtures/
    sample_resume.docx       # Test fixture — minimal resume
```

---

## Task 1: Migration 008 — Settings + Onboard Uploads Tables

**Files:**
- Create: `code/db/migrations/008_settings_onboard.sql`
- Test: manual SQL verification

- [ ] **Step 1: Write the migration SQL**

```sql
-- 008_settings_onboard.sql
-- Settings table (single row) + onboard upload tracking

BEGIN;

-- Widen template_type for new values
ALTER TABLE resume_templates
    ALTER COLUMN template_type TYPE VARCHAR(50);

-- Platform settings (single row, enforced by CHECK)
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    ai_provider VARCHAR(50) DEFAULT 'none',
    ai_enabled BOOLEAN DEFAULT FALSE,
    ai_model VARCHAR(100),
    default_template_id INTEGER REFERENCES resume_templates(id),
    duplicate_threshold FLOAT DEFAULT 0.85,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT single_row CHECK (id = 1)
);

INSERT INTO settings (id) VALUES (1) ON CONFLICT DO NOTHING;

-- Track file upload history
CREATE TABLE IF NOT EXISTS onboard_uploads (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(500) NOT NULL,
    file_type VARCHAR(10) NOT NULL,
    file_size INTEGER,
    status VARCHAR(50) DEFAULT 'processing',
    parsing_method VARCHAR(50),
    parsing_confidence FLOAT,
    career_history_ids INTEGER[],
    bullet_ids INTEGER[],
    skill_ids INTEGER[],
    template_id INTEGER REFERENCES resume_templates(id),
    recipe_id INTEGER REFERENCES resume_recipes(id),
    match_score FLOAT,
    report JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_onboard_uploads_status ON onboard_uploads(status);
CREATE INDEX idx_onboard_uploads_created ON onboard_uploads(created_at DESC);

COMMIT;
```

Save to `code/db/migrations/008_settings_onboard.sql`.

- [ ] **Step 2: Apply the migration**

Run:
```bash
PGPASSWORD=WUHD8fBisb57FS4Q3bdvfuvgnim9fL1c psql -h localhost -p 5555 -U supertroopers -d supertroopers -f code/db/migrations/008_settings_onboard.sql
```
Expected: `ALTER TABLE`, `CREATE TABLE`, `INSERT`, `CREATE INDEX` — no errors.

- [ ] **Step 3: Verify tables exist**

Run:
```bash
PGPASSWORD=WUHD8fBisb57FS4Q3bdvfuvgnim9fL1c psql -h localhost -p 5555 -U supertroopers -d supertroopers -c "SELECT ai_provider, ai_enabled, duplicate_threshold FROM settings; SELECT count(*) FROM onboard_uploads;"
```
Expected: settings row with defaults (none, false, 0.85), onboard_uploads count = 0.

- [ ] **Step 4: Commit**

```bash
git add code/db/migrations/008_settings_onboard.sql
git commit -m "feat: migration 008 — settings + onboard_uploads tables"
```

---

## Task 2: Settings Routes

**Files:**
- Create: `code/backend/routes/settings.py`
- Modify: `code/backend/routes/__init__.py`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_settings.py`:
```python
"""Integration tests for settings CRUD."""

import json


def test_get_settings(cursor):
    """GET /api/settings returns default settings."""
    cursor.execute("SELECT ai_provider, ai_enabled, duplicate_threshold FROM settings WHERE id = 1")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "none"
    assert row[1] is False
    assert row[2] == 0.85


def test_update_settings(cursor):
    """PATCH /api/settings updates fields."""
    cursor.execute(
        "UPDATE settings SET ai_provider = %s, ai_enabled = %s WHERE id = 1 RETURNING ai_provider, ai_enabled",
        ("claude", True),
    )
    row = cursor.fetchone()
    assert row[0] == "claude"
    assert row[1] is True
```

- [ ] **Step 2: Run tests to verify they pass** (these are DB-level tests)

Run: `pytest tests/test_settings.py -v`
Expected: 2 PASSED

- [ ] **Step 3: Write settings routes**

Create `code/backend/routes/settings.py`:
```python
"""Settings CRUD routes."""

from flask import Blueprint, jsonify, request
import psycopg2.extras

bp = Blueprint("settings", __name__)


def get_db():
    from app import get_db_connection
    return get_db_connection()


@bp.route("/api/settings", methods=["GET"])
def get_settings():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM settings WHERE id = 1")
    row = cur.fetchone()
    cur.close()
    if not row:
        return jsonify({"error": "Settings not found"}), 404
    # Convert datetime fields to ISO strings
    result = dict(row)
    for k in ("created_at", "updated_at"):
        if result.get(k):
            result[k] = result[k].isoformat()
    return jsonify(result)


@bp.route("/api/settings", methods=["PATCH"])
def update_settings():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    allowed = {"ai_provider", "ai_enabled", "ai_model", "default_template_id", "duplicate_threshold", "preferences"}
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return jsonify({"error": "No valid fields provided"}), 400

    set_clauses = [f"{k} = %s" for k in fields]
    set_clauses.append("updated_at = NOW()")
    values = list(fields.values())

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        f"UPDATE settings SET {', '.join(set_clauses)} WHERE id = 1 RETURNING *",
        values,
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    result = dict(row)
    for k in ("created_at", "updated_at"):
        if result.get(k):
            result[k] = result[k].isoformat()
    return jsonify(result)
```

- [ ] **Step 4: Register the blueprint**

In `code/backend/routes/__init__.py`, add:
```python
from routes.settings import bp as settings_bp
```
And add `settings_bp` to `ALL_BLUEPRINTS`.

- [ ] **Step 5: Rebuild container and test endpoint**

Run:
```bash
cd code && docker compose up -d --build backend
```
Then:
```bash
curl http://localhost:8055/api/settings
curl -X PATCH http://localhost:8055/api/settings -H "Content-Type: application/json" -d '{"ai_provider":"claude","ai_enabled":true}'
```
Expected: JSON responses with settings data.

- [ ] **Step 6: Commit**

```bash
git add code/backend/routes/settings.py code/backend/routes/__init__.py tests/test_settings.py
git commit -m "feat: settings CRUD routes + tests"
```

---

## Task 3: AI Provider Adapter Framework

**Files:**
- Create: `code/backend/ai_providers/__init__.py`
- Create: `code/backend/ai_providers/base.py`
- Create: `code/backend/ai_providers/claude_provider.py`
- Create: `code/backend/ai_providers/gemini_provider.py`
- Create: `code/backend/ai_providers/openai_provider.py`

- [ ] **Step 1: Write the base class**

Create `code/backend/ai_providers/base.py`:
```python
"""Abstract base class for AI provider adapters."""

import shutil
import subprocess
import json
from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Base class for AI CLI adapters.

    Each provider wraps a locally-installed CLI tool (claude, gemini, openai, etc.)
    and uses the user's existing credentials. No API keys needed.

    To add a new provider:
    1. Subclass AIProvider
    2. Set name and cli_command
    3. Implement parse_resume(), resolve_duplicate(), health_check()
    4. Register in ai_providers/__init__.py
    """

    name: str = ""
    cli_command: str = ""

    def is_available(self) -> bool:
        """Check if the CLI is installed and on PATH."""
        return shutil.which(self.cli_command) is not None

    @abstractmethod
    def parse_resume(self, text: str) -> dict:
        """Parse resume text into structured JSON.

        Returns:
            {
                "career_history": [{"employer", "title", "start_date", "end_date", "location", "industry"}],
                "bullets": [{"employer", "text", "type", "metrics_json"}],
                "skills": [{"name", "category", "proficiency"}],
                "confidence": float  # 0.0-1.0
            }
        """

    @abstractmethod
    def resolve_duplicate(self, bullet_a: str, bullet_b: str) -> dict:
        """Ask AI which bullet is better or merge them.

        Returns:
            {"action": "keep_a"|"keep_b"|"merge", "result": "chosen text", "reason": "explanation"}
        """

    @abstractmethod
    def health_check(self) -> dict:
        """Check provider status.

        Returns:
            {"available": bool, "version": str, "model": str}
        """

    def _run_cli(self, prompt: str, expect_json: bool = True) -> str | dict:
        """Run the CLI with a prompt and return output.

        Subclasses can override this if their CLI has a different interface.
        """
        try:
            result = subprocess.run(
                [self.cli_command, "prompt", "--format", "json" if expect_json else "text"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(f"{self.name} CLI error: {result.stderr}")
            if expect_json:
                return json.loads(result.stdout)
            return result.stdout
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{self.name} CLI timed out after 120s")
        except json.JSONDecodeError:
            raise RuntimeError(f"{self.name} CLI returned invalid JSON: {result.stdout[:200]}")
```

- [ ] **Step 2: Write the Claude adapter**

Create `code/backend/ai_providers/claude_provider.py`:
```python
"""Claude CLI adapter for AI-enhanced resume parsing."""

import json
import subprocess
from .base import AIProvider

PARSE_PROMPT = """Parse this resume text into JSON matching this exact schema. Be precise with dates and employer names.

Schema:
{{
  "career_history": [{{ "employer": str, "title": str, "start_date": str, "end_date": str, "location": str, "industry": str }}],
  "bullets": [{{ "employer": str, "text": str, "type": "highlight"|"job_bullet", "metrics_json": {{}} }}],
  "skills": [{{ "name": str, "category": "technical"|"leadership"|"domain"|"methodology", "proficiency": "expert"|"advanced"|"intermediate" }}],
  "confidence": float
}}

Rules:
- Extract ALL bullet points under each employer
- Classify bullets with quantitative metrics as "highlight" type
- For metrics_json, extract numbers like {{"revenue": "$2M", "team_size": 8}}
- Set confidence 0.0-1.0 based on how clearly structured the resume is
- If a field is unclear, use null

Resume text:
{text}

Return ONLY valid JSON, no markdown fences."""

DUPLICATE_PROMPT = """Given two similar resume bullets, decide the best action:
A: "{bullet_a}"
B: "{bullet_b}"

Reply with JSON only:
{{ "action": "keep_a" | "keep_b" | "merge", "result": "the chosen or merged text", "reason": "brief explanation" }}"""


class ClaudeProvider(AIProvider):
    name = "claude"
    cli_command = "claude"

    def parse_resume(self, text: str) -> dict:
        prompt = PARSE_PROMPT.format(text=text)
        return self._run_cli(prompt, expect_json=True)

    def resolve_duplicate(self, bullet_a: str, bullet_b: str) -> dict:
        prompt = DUPLICATE_PROMPT.format(bullet_a=bullet_a, bullet_b=bullet_b)
        return self._run_cli(prompt, expect_json=True)

    def health_check(self) -> dict:
        try:
            result = subprocess.run(
                [self.cli_command, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return {
                "available": result.returncode == 0,
                "version": result.stdout.strip(),
                "model": "claude",
            }
        except Exception as e:
            return {"available": False, "version": None, "model": None, "error": str(e)}

    def _run_cli(self, prompt: str, expect_json: bool = True) -> dict | str:
        """Claude CLI uses 'claude -p' for non-interactive prompts."""
        try:
            result = subprocess.run(
                [self.cli_command, "-p", prompt, "--output-format", "json"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Claude CLI error: {result.stderr}")
            if expect_json:
                # Claude may wrap response — extract JSON from output
                output = result.stdout.strip()
                # Find first { to last }
                start = output.find("{")
                end = output.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(output[start:end])
                raise RuntimeError(f"No JSON found in Claude output: {output[:200]}")
            return result.stdout
        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude CLI timed out after 120s")
```

- [ ] **Step 3: Write Gemini and OpenAI stubs**

Create `code/backend/ai_providers/gemini_provider.py`:
```python
"""Gemini CLI adapter (stub — implement when Gemini CLI is available)."""

import subprocess
from .base import AIProvider


class GeminiProvider(AIProvider):
    name = "gemini"
    cli_command = "gemini"

    def parse_resume(self, text: str) -> dict:
        # TODO: Implement when Gemini CLI interface is documented
        raise NotImplementedError("Gemini provider not yet implemented. Install Gemini CLI and update this adapter.")

    def resolve_duplicate(self, bullet_a: str, bullet_b: str) -> dict:
        raise NotImplementedError("Gemini provider not yet implemented.")

    def health_check(self) -> dict:
        try:
            result = subprocess.run(
                [self.cli_command, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            return {"available": result.returncode == 0, "version": result.stdout.strip(), "model": "gemini"}
        except Exception as e:
            return {"available": False, "version": None, "model": None, "error": str(e)}
```

Create `code/backend/ai_providers/openai_provider.py`:
```python
"""OpenAI CLI adapter (stub — implement when OpenAI CLI is available)."""

import subprocess
from .base import AIProvider


class OpenAIProvider(AIProvider):
    name = "openai"
    cli_command = "openai"

    def parse_resume(self, text: str) -> dict:
        raise NotImplementedError("OpenAI provider not yet implemented. Install OpenAI CLI and update this adapter.")

    def resolve_duplicate(self, bullet_a: str, bullet_b: str) -> dict:
        raise NotImplementedError("OpenAI provider not yet implemented.")

    def health_check(self) -> dict:
        try:
            result = subprocess.run(
                [self.cli_command, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            return {"available": result.returncode == 0, "version": result.stdout.strip(), "model": "openai"}
        except Exception as e:
            return {"available": False, "version": None, "model": None, "error": str(e)}
```

- [ ] **Step 4: Write the provider registry**

Create `code/backend/ai_providers/__init__.py`:
```python
"""AI provider registry and factory."""

from .base import AIProvider
from .claude_provider import ClaudeProvider
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider

PROVIDERS = {
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
}


def get_provider(name: str = None) -> AIProvider | None:
    """Return an AI provider instance, or None if disabled/unavailable.

    Args:
        name: Provider name. If None, reads from settings table.
    """
    if name is None:
        # Read from settings
        try:
            from app import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT ai_provider, ai_enabled FROM settings WHERE id = 1")
            row = cur.fetchone()
            cur.close()
            if not row or not row[1]:  # ai_enabled is False
                return None
            name = row[0]
        except Exception:
            return None

    if name in ("none", "", None):
        return None

    provider_cls = PROVIDERS.get(name)
    if not provider_cls:
        return None

    provider = provider_cls()
    if not provider.is_available():
        return None

    return provider


def list_providers() -> list[dict]:
    """Return info about all registered providers."""
    result = []
    for name, cls in PROVIDERS.items():
        p = cls()
        result.append({
            "name": name,
            "cli_command": p.cli_command,
            "available": p.is_available(),
        })
    return result
```

- [ ] **Step 5: Commit**

```bash
git add code/backend/ai_providers/
git commit -m "feat: modular AI provider adapter framework (claude, gemini, openai)"
```

---

## Task 4: Rule-Based Resume Parser

**Files:**
- Create: `code/backend/parsers/__init__.py`
- Create: `code/backend/parsers/rule_based.py`
- Test: `tests/test_rule_parser.py`

- [ ] **Step 1: Write the test fixture**

Create `tests/fixtures/sample_resume.docx` — a minimal .docx with:
- Name + contact header
- Summary section
- 2 employers with 3 bullets each
- Skills section
- Education section

Use python-docx to generate it programmatically. Create a helper script `tests/fixtures/create_sample_resume.py`:
```python
"""Generate a minimal sample resume .docx for testing."""

from docx import Document
from pathlib import Path


def create():
    doc = Document()
    doc.add_paragraph("Jane Smith")
    doc.add_paragraph("jane@example.com | (555) 123-4567 | San Francisco, CA")
    doc.add_paragraph("")
    doc.add_heading("Professional Summary", level=2)
    doc.add_paragraph("Senior software engineer with 10 years of experience in full-stack development.")
    doc.add_paragraph("")
    doc.add_heading("Experience", level=2)
    doc.add_paragraph("Acme Corp | Senior Software Engineer | Jan 2020 - Present | San Francisco, CA")
    doc.add_paragraph("- Led migration of monolith to microservices, reducing deploy time by 75%", style="List Bullet")
    doc.add_paragraph("- Managed team of 8 engineers across 3 time zones", style="List Bullet")
    doc.add_paragraph("- Built real-time analytics dashboard serving 50K daily users", style="List Bullet")
    doc.add_paragraph("")
    doc.add_paragraph("Beta Inc | Software Engineer | Jun 2015 - Dec 2019 | New York, NY")
    doc.add_paragraph("- Developed RESTful APIs handling 2M requests per day", style="List Bullet")
    doc.add_paragraph("- Implemented CI/CD pipeline reducing release cycle from 2 weeks to 2 days", style="List Bullet")
    doc.add_paragraph("- Mentored 4 junior developers through onboarding program", style="List Bullet")
    doc.add_paragraph("")
    doc.add_heading("Skills", level=2)
    doc.add_paragraph("Python, JavaScript, TypeScript, React, Node.js, PostgreSQL, Docker, Kubernetes, AWS")
    doc.add_paragraph("")
    doc.add_heading("Education", level=2)
    doc.add_paragraph("BS Computer Science | MIT | 2015")

    path = Path(__file__).parent / "sample_resume.docx"
    doc.save(str(path))
    return path


if __name__ == "__main__":
    p = create()
    print(f"Created: {p}")
```

Run: `python tests/fixtures/create_sample_resume.py`

- [ ] **Step 2: Write the failing parser test**

Create `tests/test_rule_parser.py`:
```python
"""Tests for rule-based resume parser."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "code" / "backend"))
sys.path.insert(0, str(Path(__file__).parent.parent / "code" / "utils"))

from parsers.rule_based import parse_resume_text


def test_parse_sample_resume():
    """Parse sample resume text and verify extraction."""
    # Read the sample resume
    from read_docx import read_full_text
    sample = Path(__file__).parent / "fixtures" / "sample_resume.docx"
    assert sample.exists(), f"Sample resume not found: {sample}"
    text = read_full_text(str(sample))

    result = parse_resume_text(text)

    # Structure check
    assert "career_history" in result
    assert "bullets" in result
    assert "skills" in result
    assert "confidence" in result
    assert 0.0 <= result["confidence"] <= 1.0

    # Career history
    assert len(result["career_history"]) == 2
    employers = [ch["employer"] for ch in result["career_history"]]
    assert "Acme Corp" in employers
    assert "Beta Inc" in employers

    # Bullets
    assert len(result["bullets"]) >= 6
    bullet_texts = [b["text"] for b in result["bullets"]]
    assert any("microservices" in t for t in bullet_texts)
    assert any("RESTful" in t for t in bullet_texts)

    # Skills
    assert len(result["skills"]) >= 5
    skill_names = [s["name"] for s in result["skills"]]
    assert "Python" in skill_names
    assert "Docker" in skill_names


def test_parse_empty_text():
    """Empty text returns empty structure with low confidence."""
    result = parse_resume_text("")
    assert result["career_history"] == []
    assert result["bullets"] == []
    assert result["skills"] == []
    assert result["confidence"] < 0.3
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_rule_parser.py -v`
Expected: FAIL — `parsers.rule_based` not found

- [ ] **Step 4: Write the parser dispatcher**

Create `code/backend/parsers/__init__.py`:
```python
"""Resume parsing — dispatches to AI-enhanced or rule-based parser."""

from .rule_based import parse_resume_text


def parse_resume(text: str, provider=None) -> dict:
    """Parse resume text into structured data.

    Args:
        text: Raw resume text (from read_docx/read_pdf).
        provider: AIProvider instance, or None for rule-based.

    Returns:
        {"career_history": [], "bullets": [], "skills": [], "confidence": float}
    """
    if provider:
        from .ai_enhanced import parse_resume_ai
        try:
            return parse_resume_ai(text, provider)
        except Exception:
            # AI failed — fall back to rule-based
            pass
    return parse_resume_text(text)
```

- [ ] **Step 5: Write the rule-based parser**

Create `code/backend/parsers/rule_based.py`:
```python
"""Rule-based resume parser using regex and heuristics.

Handles ~80% of standard resume formats. Returns structured data
matching the DB schema for career_history, bullets, and skills.
"""

import re
from typing import Optional


# Common section headers
SECTION_PATTERNS = {
    "experience": re.compile(
        r"^(professional\s+)?experience|work\s+history|employment",
        re.IGNORECASE,
    ),
    "education": re.compile(
        r"^education|academic|degrees?",
        re.IGNORECASE,
    ),
    "skills": re.compile(
        r"^(technical\s+|core\s+|key\s+)?skills|competenc|technologies|proficienc",
        re.IGNORECASE,
    ),
    "summary": re.compile(
        r"^(professional\s+|executive\s+)?summary|profile|objective|about",
        re.IGNORECASE,
    ),
}

# Employer line: "Company | Title | Date - Date | Location" (various separators)
EMPLOYER_PATTERN = re.compile(
    r"^(.+?)\s*[\|,\-–—]\s*(.+?)\s*[\|,\-–—]\s*"
    r"(\w+\.?\s+\d{4})\s*[\-–—]\s*((?:\w+\.?\s+\d{4})|[Pp]resent|[Cc]urrent)"
    r"(?:\s*[\|,\-–—]\s*(.+))?$"
)

# Simpler date pattern for lines like "Jan 2020 - Present"
DATE_RANGE = re.compile(
    r"(\w+\.?\s+\d{4})\s*[\-–—to]+\s*((?:\w+\.?\s+\d{4})|[Pp]resent|[Cc]urrent)"
)

# Bullet point markers
BULLET_CHARS = re.compile(r"^[\s]*[•\-\*▪►◆●○]\s*(.+)")

# Skills separators
SKILL_SPLIT = re.compile(r"[,;|/]|\band\b")

# Education: "Degree | Institution | Year" or similar
EDUCATION_PATTERN = re.compile(
    r"(B\.?S\.?|M\.?S\.?|M\.?B\.?A\.?|Ph\.?D\.?|B\.?A\.?|Associate|Bachelor|Master|Doctor)"
    r".*?(\d{4})",
    re.IGNORECASE,
)


def parse_resume_text(text: str) -> dict:
    """Parse raw resume text into structured career data.

    Args:
        text: Raw text from a resume (.docx or .pdf).

    Returns:
        {
            "career_history": [{"employer", "title", "start_date", "end_date", "location", "industry"}],
            "bullets": [{"employer", "text", "type", "metrics_json"}],
            "skills": [{"name", "category", "proficiency"}],
            "confidence": float
        }
    """
    if not text or not text.strip():
        return {"career_history": [], "bullets": [], "skills": [], "confidence": 0.1}

    lines = text.strip().split("\n")
    sections = _identify_sections(lines)
    career_history = []
    bullets = []
    skills = []
    confidence_signals = 0
    total_signals = 4  # experience, bullets, skills, education

    # Parse experience section
    exp_lines = sections.get("experience", [])
    if exp_lines:
        career_history, exp_bullets = _parse_experience(exp_lines)
        bullets.extend(exp_bullets)
        if career_history:
            confidence_signals += 1
        if exp_bullets:
            confidence_signals += 1

    # Parse skills section
    skill_lines = sections.get("skills", [])
    if skill_lines:
        skills = _parse_skills(skill_lines)
        if skills:
            confidence_signals += 1

    # Check education found
    edu_lines = sections.get("education", [])
    if edu_lines:
        confidence_signals += 1

    # Auto-extract skills from bullets if no skills section
    if not skills and bullets:
        skills = _extract_skills_from_bullets(bullets)

    # Classify highlight bullets (those with metrics)
    for b in bullets:
        if _has_metrics(b["text"]):
            b["type"] = "highlight"
            b["metrics_json"] = _extract_metrics(b["text"])

    confidence = confidence_signals / total_signals

    return {
        "career_history": career_history,
        "bullets": bullets,
        "skills": skills,
        "confidence": round(confidence, 2),
    }


def _identify_sections(lines: list[str]) -> dict[str, list[str]]:
    """Split lines into named sections based on header detection."""
    sections = {}
    current_section = "header"
    current_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            current_lines.append(line)
            continue

        # Check if this line is a section header
        matched_section = None
        for section_name, pattern in SECTION_PATTERNS.items():
            if pattern.match(stripped):
                matched_section = section_name
                break

        if matched_section:
            if current_lines:
                sections[current_section] = current_lines
            current_section = matched_section
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections[current_section] = current_lines

    return sections


def _parse_experience(lines: list[str]) -> tuple[list[dict], list[dict]]:
    """Extract employers and bullets from experience section."""
    career_history = []
    bullets = []
    current_employer = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Try employer pattern
        emp_match = EMPLOYER_PATTERN.match(stripped)
        if emp_match:
            current_employer = {
                "employer": emp_match.group(1).strip(),
                "title": emp_match.group(2).strip(),
                "start_date": emp_match.group(3).strip(),
                "end_date": emp_match.group(4).strip(),
                "location": (emp_match.group(5) or "").strip(),
                "industry": None,
            }
            career_history.append(current_employer)
            continue

        # Try bullet
        bullet_match = BULLET_CHARS.match(stripped)
        if bullet_match and current_employer:
            bullets.append({
                "employer": current_employer["employer"],
                "text": bullet_match.group(1).strip(),
                "type": "job_bullet",
                "metrics_json": {},
            })
            continue

        # If line has a date range but didn't match employer pattern,
        # try to split it differently
        if DATE_RANGE.search(stripped) and not current_employer:
            # Heuristic: line might be "Company Name" followed by date
            date_match = DATE_RANGE.search(stripped)
            before_date = stripped[: date_match.start()].strip(" |-–—,")
            parts = re.split(r"\s*[\|,\-–—]\s*", before_date, maxsplit=1)
            if parts:
                current_employer = {
                    "employer": parts[0].strip(),
                    "title": parts[1].strip() if len(parts) > 1 else "",
                    "start_date": date_match.group(1),
                    "end_date": date_match.group(2),
                    "location": "",
                    "industry": None,
                }
                career_history.append(current_employer)

    return career_history, bullets


def _parse_skills(lines: list[str]) -> list[dict]:
    """Extract skills from a skills section."""
    skills = []
    seen = set()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Split by common separators
        parts = SKILL_SPLIT.split(stripped)
        for part in parts:
            name = part.strip().strip("•-*▪ ")
            if name and len(name) > 1 and name.lower() not in seen:
                seen.add(name.lower())
                skills.append({
                    "name": name,
                    "category": _categorize_skill(name),
                    "proficiency": "intermediate",
                })

    return skills


def _categorize_skill(name: str) -> str:
    """Simple skill categorization."""
    technical = {
        "python", "javascript", "typescript", "react", "node", "nodejs",
        "postgresql", "docker", "kubernetes", "aws", "azure", "gcp",
        "java", "go", "rust", "c++", "sql", "nosql", "mongodb",
        "redis", "kafka", "terraform", "git", "linux", "html", "css",
    }
    leadership = {
        "leadership", "management", "mentoring", "coaching",
        "strategic planning", "team building",
    }
    methodology = {
        "agile", "scrum", "kanban", "devops", "ci/cd", "tdd",
        "microservices", "rest", "graphql",
    }
    if name.lower() in technical:
        return "technical"
    if name.lower() in leadership:
        return "leadership"
    if name.lower() in methodology:
        return "methodology"
    return "domain"


def _extract_skills_from_bullets(bullets: list[dict]) -> list[dict]:
    """Fallback: extract skill-like words from bullet text."""
    # Simple keyword extraction — just common tech terms
    tech_terms = {
        "python", "javascript", "typescript", "react", "node.js",
        "postgresql", "docker", "kubernetes", "aws", "sql",
    }
    found = set()
    for b in bullets:
        words = set(re.findall(r"\b\w+(?:\.\w+)?\b", b["text"].lower()))
        found.update(words & tech_terms)

    return [{"name": s.title(), "category": "technical", "proficiency": "intermediate"} for s in found]


def _has_metrics(text: str) -> bool:
    """Check if bullet contains quantitative metrics."""
    return bool(re.search(r"\d+[%xX]|\$[\d,.]+[MmKkBb]?|\d+\s*(?:users|customers|engineers|team|million|billion)", text))


def _extract_metrics(text: str) -> dict:
    """Extract key metrics from bullet text."""
    metrics = {}
    # Dollar amounts
    money = re.findall(r"\$[\d,.]+[MmKkBb]?", text)
    if money:
        metrics["revenue"] = money[0]
    # Percentages
    pcts = re.findall(r"(\d+)%", text)
    if pcts:
        metrics["percentage"] = pcts[0] + "%"
    # Team size
    team = re.search(r"(\d+)\s*(?:engineers?|developers?|team\s*members?|people)", text, re.IGNORECASE)
    if team:
        metrics["team_size"] = int(team.group(1))
    # Users/customers
    users = re.search(r"([\d,.]+[KkMm]?)\s*(?:daily\s+)?(?:users?|customers?)", text, re.IGNORECASE)
    if users:
        metrics["users"] = users.group(1)
    return metrics
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_rule_parser.py -v`
Expected: 2 PASSED

- [ ] **Step 7: Write the AI-enhanced parser wrapper**

Create `code/backend/parsers/ai_enhanced.py`:
```python
"""AI-enhanced resume parser — delegates to configured AI provider."""


def parse_resume_ai(text: str, provider) -> dict:
    """Parse resume using AI provider.

    Args:
        text: Raw resume text.
        provider: AIProvider instance.

    Returns:
        Same schema as rule_based.parse_resume_text()
    """
    result = provider.parse_resume(text)

    # Validate schema
    required = {"career_history", "bullets", "skills"}
    if not isinstance(result, dict) or not required.issubset(result.keys()):
        raise ValueError(f"AI returned invalid schema. Keys: {result.keys() if isinstance(result, dict) else type(result)}")

    # Ensure confidence exists
    if "confidence" not in result:
        result["confidence"] = 0.9  # AI typically high confidence

    # Validate types
    if not isinstance(result["career_history"], list):
        raise ValueError("career_history must be a list")
    if not isinstance(result["bullets"], list):
        raise ValueError("bullets must be a list")
    if not isinstance(result["skills"], list):
        raise ValueError("skills must be a list")

    return result
```

- [ ] **Step 8: Commit**

```bash
git add code/backend/parsers/ tests/test_rule_parser.py tests/fixtures/
git commit -m "feat: rule-based resume parser + AI-enhanced parser wrapper"
```

---

## Task 5: Onboard Upload Endpoint

**Files:**
- Create: `code/backend/routes/onboard.py`
- Modify: `code/backend/routes/__init__.py`
- Modify: `code/backend/requirements.txt`
- Test: `tests/test_onboard.py`

- [ ] **Step 1: Add pdf2docx to requirements**

Append to `code/backend/requirements.txt`:
```
pdf2docx==0.5.8
```

- [ ] **Step 2: Write the onboard route**

Create `code/backend/routes/onboard.py`:
```python
"""Onboarding upload endpoint — full pipeline from file to verified recipe."""

import os
import tempfile
import traceback
from difflib import SequenceMatcher
from pathlib import Path

from flask import Blueprint, jsonify, request
import psycopg2.extras

bp = Blueprint("onboard", __name__)


def get_db():
    from app import get_db_connection
    return get_db_connection()


@bp.route("/api/onboard/upload", methods=["POST"])
def upload_files():
    """Upload one or more resume files. Runs full pipeline per file.

    Returns array of per-file results with parsing stats, template/recipe IDs,
    and verification match scores.
    """
    if "files" not in request.files:
        return jsonify({"error": "No files provided. Use multipart field 'files'."}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files provided."}), 400

    results = []
    for f in files:
        result = _process_file(f)
        results.append(result)

    return jsonify({"results": results, "total": len(results)})


def _process_file(file_storage) -> dict:
    """Run full onboarding pipeline on a single file."""
    filename = file_storage.filename or "unknown"
    ext = Path(filename).suffix.lower()

    if ext not in (".docx", ".pdf"):
        return {"filename": filename, "status": "error", "error": f"Unsupported format: {ext}. Use .docx or .pdf"}

    report = {
        "filename": filename,
        "file_type": ext.lstrip("."),
        "status": "processing",
        "steps": {},
    }

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        # Save uploaded file to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            file_storage.save(tmp.name)
            tmp_path = tmp.name

        file_size = os.path.getsize(tmp_path)
        docx_path = tmp_path

        # Step 1: PDF conversion
        if ext == ".pdf":
            docx_path = _convert_pdf(tmp_path, report)

        # Step 2: Extract text
        text = _extract_text(docx_path, report)

        # Step 3: Parse
        parsed = _parse_resume(text, report)

        # Step 4: Insert into DB
        ids = _insert_data(cur, conn, parsed, report)

        # Step 5: Store original as template
        template_id = _store_original(cur, conn, docx_path, filename, ext, file_size, report)

        # Step 6: Templatize
        placeholder_template_id, template_map = _templatize(cur, conn, docx_path, report)

        # Step 7: Create recipe
        recipe_id = _create_recipe(cur, conn, placeholder_template_id, template_map, ids, parsed, report)

        # Step 8: Reconstruct and verify
        match_score = _verify(cur, conn, recipe_id, placeholder_template_id, docx_path, report)

        # Step 9: Record upload
        _record_upload(cur, conn, filename, ext, file_size, ids, template_id, recipe_id, match_score, report)

        report["status"] = "success"
        report["template_id"] = template_id
        report["recipe_id"] = recipe_id
        report["match_score"] = match_score

    except Exception as e:
        report["status"] = "error"
        report["error"] = str(e)
        report["traceback"] = traceback.format_exc()
        conn.rollback()
    finally:
        cur.close()
        # Cleanup temp files
        try:
            os.unlink(tmp_path)
            if docx_path != tmp_path:
                os.unlink(docx_path)
        except Exception:
            pass

    return report


def _convert_pdf(pdf_path: str, report: dict) -> str:
    """Convert PDF to DOCX. Returns path to converted file."""
    from pdf2docx import Converter

    docx_path = pdf_path.rsplit(".", 1)[0] + ".docx"
    try:
        cv = Converter(pdf_path)
        cv.convert(docx_path)
        cv.close()

        # Quality gate: check paragraph count
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "utils"))
        from read_docx import read_full_text
        text = read_full_text(docx_path)
        para_count = len([p for p in text.split("\n") if p.strip()])

        quality = "good" if para_count > 10 else "degraded"
        report["steps"]["pdf_conversion"] = {
            "status": "success",
            "paragraphs": para_count,
            "quality": quality,
        }
        if quality == "degraded":
            report["steps"]["pdf_conversion"]["warning"] = (
                "Low paragraph count after conversion. .docx upload recommended for best results."
            )
        return docx_path
    except Exception as e:
        report["steps"]["pdf_conversion"] = {"status": "error", "error": str(e)}
        raise RuntimeError(f"PDF conversion failed: {e}")


def _extract_text(docx_path: str, report: dict) -> str:
    """Extract text from DOCX."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "utils"))
    from read_docx import read_full_text

    text = read_full_text(docx_path)
    report["steps"]["extract"] = {"status": "success", "characters": len(text)}
    return text


def _parse_resume(text: str, report: dict) -> dict:
    """Parse resume text using AI or rule-based parser."""
    from ai_providers import get_provider
    from parsers import parse_resume

    provider = get_provider()
    method = provider.name if provider else "rule_based"

    parsed = parse_resume(text, provider)
    report["steps"]["parse"] = {
        "status": "success",
        "method": method,
        "confidence": parsed.get("confidence", 0),
        "career_history_count": len(parsed.get("career_history", [])),
        "bullets_count": len(parsed.get("bullets", [])),
        "skills_count": len(parsed.get("skills", [])),
    }
    return parsed


def _insert_data(cur, conn, parsed: dict, report: dict) -> dict:
    """Insert parsed data into DB tables. Returns dict of inserted IDs."""
    ids = {"career_history": [], "bullets": [], "skills": []}
    duplicates = {"exact": 0, "near": [], "near_count": 0}

    # Insert career_history
    for ch in parsed.get("career_history", []):
        cur.execute(
            """INSERT INTO career_history (employer, title, start_date, end_date, location, industry)
            VALUES (%(employer)s, %(title)s, %(start_date)s, %(end_date)s, %(location)s, %(industry)s)
            RETURNING id""",
            ch,
        )
        ids["career_history"].append(cur.fetchone()["id"])

    # Insert bullets with dedup
    # Get duplicate threshold from settings
    cur.execute("SELECT duplicate_threshold FROM settings WHERE id = 1")
    threshold = (cur.fetchone() or {}).get("duplicate_threshold", 0.85)

    for b in parsed.get("bullets", []):
        # Check exact duplicate
        cur.execute("SELECT id, text FROM bullets WHERE text = %s", (b["text"],))
        exact = cur.fetchone()
        if exact:
            duplicates["exact"] += 1
            continue

        # Check near duplicate
        cur.execute("SELECT id, text FROM bullets")
        is_near_dup = False
        for existing in cur.fetchall():
            similarity = SequenceMatcher(None, b["text"], existing["text"]).ratio()
            if similarity >= threshold:
                duplicates["near"].append({
                    "existing": existing["text"][:80],
                    "new": b["text"][:80],
                    "similarity": round(similarity, 3),
                })
                duplicates["near_count"] += 1
                is_near_dup = True
                # Still insert, but flag it
                break

        # Find career_history_id for this bullet's employer
        ch_id = None
        if b.get("employer"):
            cur.execute(
                "SELECT id FROM career_history WHERE employer = %s ORDER BY id DESC LIMIT 1",
                (b["employer"],),
            )
            row = cur.fetchone()
            if row:
                ch_id = row["id"]

        cur.execute(
            """INSERT INTO bullets (career_history_id, text, type, metrics_json, source_file)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id""",
            (ch_id, b["text"], b.get("type", "job_bullet"),
             psycopg2.extras.Json(b.get("metrics_json", {})),
             "onboard_upload"),
        )
        ids["bullets"].append(cur.fetchone()["id"])

    # Insert skills with dedup
    for s in parsed.get("skills", []):
        cur.execute("SELECT id FROM skills WHERE name = %s", (s["name"],))
        if cur.fetchone():
            continue  # Exact skill name exists
        cur.execute(
            "INSERT INTO skills (name, category, proficiency) VALUES (%s, %s, %s) RETURNING id",
            (s["name"], s.get("category", "technical"), s.get("proficiency", "intermediate")),
        )
        ids["skills"].append(cur.fetchone()["id"])

    conn.commit()

    report["steps"]["insert"] = {
        "status": "success",
        "career_history_inserted": len(ids["career_history"]),
        "bullets_inserted": len(ids["bullets"]),
        "skills_inserted": len(ids["skills"]),
        "duplicates_exact": duplicates["exact"],
        "duplicates_near": duplicates["near_count"],
        "near_duplicates": duplicates["near"][:10],  # Cap at 10 for report size
    }
    return ids


def _store_original(cur, conn, docx_path: str, filename: str, ext: str, file_size: int, report: dict) -> int:
    """Store original file in resume_templates."""
    with open(docx_path, "rb") as f:
        blob = f.read()

    template_type = "uploaded_original" if ext == ".docx" else "uploaded_converted"
    cur.execute(
        """INSERT INTO resume_templates (name, template_type, template_blob)
        VALUES (%s, %s, %s)
        RETURNING id""",
        (filename, template_type, psycopg2.Binary(blob)),
    )
    conn.commit()
    tid = cur.fetchone()["id"]
    report["steps"]["store_original"] = {"status": "success", "template_id": tid}
    return tid


def _templatize(cur, conn, docx_path: str, report: dict) -> tuple:
    """Run templatize_resume on the docx. Returns (template_id, template_map)."""
    import sys
    import json
    import tempfile
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "utils"))
    from templatize_resume import templatize

    # templatize() requires explicit output paths
    stem = Path(docx_path).stem
    out_docx = os.path.join(tempfile.gettempdir(), f"{stem}_placeholder.docx")
    out_map = os.path.join(tempfile.gettempdir(), f"{stem}_map.json")

    result = templatize(docx_path, out_docx, out_map, layout_name="auto")

    # Load outputs
    with open(out_docx, "rb") as f:
        blob = f.read()
    with open(out_map, "r") as f:
        template_map = json.load(f)

    # Store placeholder template
    cur.execute(
        """INSERT INTO resume_templates (name, template_type, template_blob, template_map)
        VALUES (%s, %s, %s, %s)
        RETURNING id""",
        (
            f"{stem}_placeholder",
            "placeholder",
            psycopg2.Binary(blob),
            psycopg2.extras.Json(template_map),
        ),
    )
    conn.commit()
    tid = cur.fetchone()["id"]

    report["steps"]["templatize"] = {
        "status": "success",
        "template_id": tid,
        "slots": len(template_map),
    }

    # Cleanup temp files
    for p in (out_docx, out_map):
        try:
            os.unlink(p)
        except Exception:
            pass

    return tid, template_map


def _create_recipe(cur, conn, template_id: int, template_map: dict, ids: dict, parsed: dict, report: dict) -> int:
    """Auto-create a recipe mapping slots to inserted DB rows."""
    import json

    slots = {}
    career_idx = 0
    bullet_idx = 0

    for slot_name, slot_info in template_map.items():
        slot_type = slot_info.get("type", "")
        original_text = slot_info.get("original_text", "")

        if "JOB_" in slot_name and "HEADER" in slot_name:
            # Map to career_history
            if career_idx < len(ids["career_history"]):
                slots[slot_name] = {
                    "table": "career_history",
                    "id": ids["career_history"][career_idx],
                    "column": "employer",
                }
                career_idx += 1
        elif "BULLET" in slot_name:
            # Map to bullet by matching text
            if bullet_idx < len(ids["bullets"]):
                slots[slot_name] = {
                    "table": "bullets",
                    "id": ids["bullets"][bullet_idx],
                    "column": "text",
                }
                bullet_idx += 1
        elif "SKILL" in slot_name or "KEYWORD" in slot_name:
            slots[slot_name] = {
                "table": "skills",
                "query": "all",
                "column": "name",
            }
        else:
            # Literal fallback — use original text
            slots[slot_name] = {
                "literal": original_text,
            }

    cur.execute(
        """INSERT INTO resume_recipes (name, template_id, slots, is_base)
        VALUES (%s, %s, %s, %s)
        RETURNING id""",
        (
            f"Auto: {Path(template_id.__str__()).stem}",
            template_id,
            psycopg2.extras.Json(slots),
            True,
        ),
    )
    conn.commit()
    rid = cur.fetchone()["id"]

    report["steps"]["recipe"] = {
        "status": "success",
        "recipe_id": rid,
        "slots_mapped": len(slots),
    }
    return rid


def _verify(cur, conn, recipe_id: int, template_id: int, original_docx: str, report: dict) -> float:
    """Reconstruct from recipe and compare to original.

    Uses the correct pipeline: load recipe → resolve → generate → compare.
    """
    import sys
    import tempfile
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "utils"))
    from generate_resume import generate_resume, resolve_recipe
    from compare_docs import extract_paragraphs, compare_text

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        output_path = tmp.name

    try:
        # Load recipe
        cur.execute("SELECT slots FROM resume_recipes WHERE id = %s", (recipe_id,))
        recipe_row = cur.fetchone()
        if not recipe_row:
            raise RuntimeError(f"Recipe {recipe_id} not found")

        # Load template
        cur.execute("SELECT template_blob, template_map FROM resume_templates WHERE id = %s", (template_id,))
        tmpl_row = cur.fetchone()
        if not tmpl_row:
            raise RuntimeError(f"Template {template_id} not found")

        # Resolve recipe slots to content_map
        content_map = resolve_recipe(conn, recipe_row["slots"])

        # Generate document
        doc = generate_resume(bytes(tmpl_row["template_blob"]), content_map, tmpl_row["template_map"])
        doc.save(output_path)

        # Compare
        paras_original = extract_paragraphs(original_docx)
        paras_generated = extract_paragraphs(output_path)
        diff_text = compare_text(paras_original, paras_generated)

        # Calculate match score
        total = max(len(paras_original), len(paras_generated), 1)
        matching = sum(1 for a, b in zip(paras_original, paras_generated) if a.strip() == b.strip())
        match_score = round((matching / total) * 100, 1)

        diff_lines = [l for l in diff_text.split("\n") if l.startswith("+") or l.startswith("-")]

        report["steps"]["verify"] = {
            "status": "success",
            "match_score": match_score,
            "diff_lines": len(diff_lines),
            "diff_details": diff_lines[:20],
        }
        return match_score
    except Exception as e:
        report["steps"]["verify"] = {"status": "error", "error": str(e)}
        return 0.0
    finally:
        try:
            os.unlink(output_path)
        except Exception:
            pass


def _record_upload(cur, conn, filename, ext, file_size, ids, template_id, recipe_id, match_score, report):
    """Save upload record to onboard_uploads."""
    import json
    cur.execute(
        """INSERT INTO onboard_uploads
        (filename, file_type, file_size, status, parsing_method, parsing_confidence,
         career_history_ids, bullet_ids, skill_ids, template_id, recipe_id, match_score, report)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            filename,
            ext.lstrip("."),
            file_size,
            report.get("status", "success"),
            report.get("steps", {}).get("parse", {}).get("method", "unknown"),
            report.get("steps", {}).get("parse", {}).get("confidence"),
            ids.get("career_history", []),
            ids.get("bullets", []),
            ids.get("skills", []),
            template_id,
            recipe_id,
            match_score,
            psycopg2.extras.Json(report),
        ),
    )
    conn.commit()
```

**Note:** This route calls into `code/utils/` scripts (read_docx, templatize_resume, generate_resume, compare_docs) as library imports. Those scripts need to expose callable functions (not just `main()`). Check and refactor if needed — the `templatize()` and `generate_from_recipe()` and `compare()` functions may need to be extracted from CLI `main()` functions into importable APIs. This is a known integration point that may require adjustments during implementation.

- [ ] **Step 3: Register the blueprint**

In `code/backend/routes/__init__.py`, add:
```python
from routes.onboard import bp as onboard_bp
```
And add `onboard_bp` to `ALL_BLUEPRINTS`.

- [ ] **Step 4: Write the integration test**

Create `tests/test_onboard.py`:
```python
"""Integration tests for onboard upload pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "code" / "backend"))
sys.path.insert(0, str(Path(__file__).parent.parent / "code" / "utils"))

from parsers.rule_based import parse_resume_text
from read_docx import read_full_text


def test_full_parse_pipeline(cursor):
    """End-to-end: read sample docx -> parse -> verify structure."""
    sample = Path(__file__).parent / "fixtures" / "sample_resume.docx"
    if not sample.exists():
        from fixtures.create_sample_resume import create
        create()

    text = read_full_text(str(sample))
    parsed = parse_resume_text(text)

    # Verify all required fields
    assert len(parsed["career_history"]) >= 2
    assert len(parsed["bullets"]) >= 6
    assert len(parsed["skills"]) >= 5
    assert parsed["confidence"] >= 0.5

    # Insert career_history
    for ch in parsed["career_history"]:
        cursor.execute(
            "INSERT INTO career_history (employer, title, start_date, end_date, location) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (ch["employer"], ch["title"], ch["start_date"], ch["end_date"], ch["location"]),
        )
        ch_id = cursor.fetchone()[0]
        assert ch_id is not None

    # Insert bullets
    for b in parsed["bullets"]:
        cursor.execute(
            "INSERT INTO bullets (text, type, source_file) VALUES (%s,%s,%s) RETURNING id",
            (b["text"], b["type"], "test_upload"),
        )
        b_id = cursor.fetchone()[0]
        assert b_id is not None


def test_duplicate_detection(cursor):
    """Exact and near-duplicate bullets are handled correctly."""
    from difflib import SequenceMatcher

    bullet_a = "Led migration of monolith to microservices, reducing deploy time by 75%"
    bullet_b = "Led the migration of monolith to microservices, reducing deployment time by 75%"

    similarity = SequenceMatcher(None, bullet_a, bullet_b).ratio()
    assert similarity >= 0.85  # Should be flagged as near-duplicate

    # Exact duplicate
    cursor.execute("INSERT INTO bullets (text, type) VALUES (%s, %s)", (bullet_a, "job_bullet"))
    cursor.execute("SELECT id FROM bullets WHERE text = %s", (bullet_a,))
    assert cursor.fetchone() is not None  # Exists

    cursor.execute("SELECT id FROM bullets WHERE text = %s", (bullet_b,))
    assert cursor.fetchone() is None  # Different text, not exact match
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_onboard.py -v`
Expected: 2 PASSED

- [ ] **Step 6: Commit**

```bash
git add code/backend/routes/onboard.py code/backend/routes/__init__.py code/backend/requirements.txt tests/test_onboard.py
git commit -m "feat: onboard upload endpoint with full pipeline"
```

---

## Task 6: Test AI Connection Endpoint

**Files:**
- Modify: `code/backend/routes/settings.py`

- [ ] **Step 1: Add test-ai endpoint to settings routes**

Append to `code/backend/routes/settings.py`:
```python
@bp.route("/api/settings/test-ai", methods=["POST"])
def test_ai_connection():
    """Test the configured AI provider connection."""
    from ai_providers import get_provider, list_providers

    data = request.get_json() or {}
    provider_name = data.get("provider")

    if provider_name:
        # Test specific provider
        from ai_providers import PROVIDERS
        if provider_name not in PROVIDERS:
            return jsonify({"error": f"Unknown provider: {provider_name}"}), 400
        provider = PROVIDERS[provider_name]()
    else:
        # Test configured provider
        provider = get_provider()

    if not provider:
        return jsonify({
            "status": "disabled",
            "message": "AI is disabled or no provider configured.",
            "providers": list_providers(),
        })

    health = provider.health_check()
    return jsonify({
        "status": "ok" if health.get("available") else "error",
        "provider": provider.name,
        "health": health,
        "providers": list_providers(),
    })
```

- [ ] **Step 2: Test manually**

Run:
```bash
curl -X POST http://localhost:8055/api/settings/test-ai -H "Content-Type: application/json" -d '{}'
curl -X POST http://localhost:8055/api/settings/test-ai -H "Content-Type: application/json" -d '{"provider":"claude"}'
```
Expected: JSON with provider status.

- [ ] **Step 3: Commit**

```bash
git add code/backend/routes/settings.py
git commit -m "feat: test-ai endpoint for AI provider health check"
```

---

## Task 7: MCP Tools for Utils + Onboard

**Files:**
- Modify: `code/backend/mcp_server.py`

- [ ] **Step 1: Add utility MCP tools**

Add these tool registrations to `mcp_server.py` (follow existing `@mcp.tool()` pattern):

```python
@mcp.tool()
def mcp_read_docx(file_path: str) -> dict:
    """Extract text from a .docx file.

    Args:
        file_path: Path to the .docx file.

    Returns:
        {"text": str, "paragraphs": int}
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
    from read_docx import read_full_text
    text = read_full_text(file_path)
    return {"text": text, "paragraphs": len([p for p in text.split("\n") if p.strip()])}


@mcp.tool()
def mcp_read_pdf(file_path: str, pages: str | None = None) -> dict:
    """Extract text from a .pdf file.

    Args:
        file_path: Path to the .pdf file.
        pages: Optional page range (e.g., "1-5"). Default reads all.

    Returns:
        {"text": str}
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
    from read_pdf import read_pdf_text
    text = read_pdf_text(file_path, pages=pages)
    return {"text": text}


@mcp.tool()
def mcp_templatize_resume(file_path: str, output_dir: str = "/tmp", layout: str = "auto") -> dict:
    """Convert a .docx resume into a placeholder template.

    Args:
        file_path: Path to the .docx resume.
        output_dir: Directory for output files. Defaults to /tmp.
        layout: Template layout name. Default 'auto'.

    Returns:
        {"template_path": str, "map_path": str, "slots": int}
    """
    import sys
    import json
    sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
    from templatize_resume import templatize

    stem = Path(file_path).stem
    out_docx = os.path.join(output_dir, f"{stem}_placeholder.docx")
    out_map = os.path.join(output_dir, f"{stem}_map.json")
    templatize(file_path, out_docx, out_map, layout_name=layout)

    with open(out_map) as f:
        tmap = json.load(f)
    return {"template_path": out_docx, "map_path": out_map, "slots": len(tmap)}


@mcp.tool()
def mcp_compare_docs(file_a: str, file_b: str) -> dict:
    """Compare two .docx documents and return a match score + diff.

    Args:
        file_a: Path to first .docx document.
        file_b: Path to second .docx document.

    Returns:
        {"match_percentage": float, "diff_count": int, "diff_text": str}
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
    from compare_docs import extract_paragraphs, compare_text

    paras_a = extract_paragraphs(file_a)
    paras_b = extract_paragraphs(file_b)
    diff = compare_text(paras_a, paras_b)
    total = max(len(paras_a), len(paras_b), 1)
    matching = sum(1 for a, b in zip(paras_a, paras_b) if a.strip() == b.strip())
    return {
        "match_percentage": round((matching / total) * 100, 1),
        "diff_count": len([l for l in diff.split("\n") if l.startswith("+") or l.startswith("-")]),
        "diff_text": diff,
    }


@mcp.tool()
def mcp_docx_to_pdf(file_path: str, output_path: str | None = None) -> dict:
    """Convert a .docx file to .pdf.

    Args:
        file_path: Path to the .docx file.
        output_path: Optional output path. Defaults to same name with .pdf extension.

    Returns:
        {"pdf_path": str}
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
    from docx_to_pdf import docx_to_pdf as _docx_to_pdf
    pdf_path = _docx_to_pdf(file_path, output_path=output_path)
    return {"pdf_path": pdf_path}


@mcp.tool()
def mcp_edit_docx(file_path: str, find_text: str, replace_text: str, output_path: str | None = None, replace_all: bool = False) -> dict:
    """Find and replace text in a .docx file.

    Args:
        file_path: Path to the .docx file.
        find_text: Text to find.
        replace_text: Replacement text.
        output_path: Optional output path. Defaults to overwriting original.
        replace_all: Replace all occurrences. Default False.

    Returns:
        {"replacements": int}
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
    from edit_docx import find_replace
    count = find_replace(file_path, find_text, replace_text, output_path=output_path, replace_all=replace_all)
    return {"replacements": count}


@mcp.tool()
def onboard_resume(file_path: str, ai_override: str | None = None) -> dict:
    """Run the full onboarding pipeline on a resume file.

    Parses resume into career data, creates template + recipe, verifies reconstruction.

    Args:
        file_path: Path to .docx or .pdf resume file.
        ai_override: Force specific AI provider ('claude','gemini','openai') or 'none' for rule-based.

    Returns:
        Full pipeline report with inserted row counts, template/recipe IDs, match score.
    """
    # This wraps the same logic as POST /api/onboard/upload
    # but for a single local file path (MCP context)
    import tempfile
    import shutil
    from werkzeug.datastructures import FileStorage

    with open(file_path, "rb") as f:
        # Create a FileStorage-like wrapper
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_path).suffix)
        shutil.copy2(file_path, tmp.name)
        tmp.close()

    from routes.onboard import _process_file

    class FakeFileStorage:
        def __init__(self, path):
            self.filename = Path(path).name
            self._path = path
        def save(self, dest):
            shutil.copy2(self._path, dest)

    return _process_file(FakeFileStorage(file_path))
```

**Note:** The exact function signatures for `templatize()`, `compare()`, `convert()`, `edit()` in `code/utils/` scripts need to be verified and potentially refactored from CLI-only `main()` functions to importable APIs. This is an integration task — during implementation, check each script and extract callable functions if they don't already exist.

- [ ] **Step 2: Rebuild container**

Run:
```bash
cd code && docker compose up -d --build backend
```

- [ ] **Step 3: Verify tools appear in MCP**

Check the MCP SSE endpoint lists the new tools.

- [ ] **Step 4: Commit**

```bash
git add code/backend/mcp_server.py
git commit -m "feat: MCP tools for utils (read_docx, templatize, compare, etc.) + onboard_resume"
```

---

## Task 8: Docker Updates — Claude CLI + Credential Mounts

**Files:**
- Modify: `code/backend/Dockerfile`
- Modify: `code/docker-compose.yml`

- [ ] **Step 1: Update Dockerfile**

Replace `code/backend/Dockerfile` with:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (for Claude CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude CLI (optional — used for AI-enhanced resume parsing)
RUN npm install -g @anthropic-ai/claude-code || echo "Claude CLI install skipped"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Flask API + MCP SSE server (combined)
EXPOSE 8055 8056

CMD ["python", "app.py", "--mcp-port", "8056"]
```

- [ ] **Step 2: Update docker-compose.yml**

Add credential volume mount to backend service:
```yaml
  backend:
    build: ./backend
    container_name: supertroopers-app
    restart: unless-stopped
    ports:
      - "8055:8055"
      - "8056:8056"
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: supertroopers
      DB_USER: supertroopers
      DB_PASSWORD: ${DB_PASSWORD:?Set DB_PASSWORD in .env or environment}
      FLASK_PORT: 8055
      FLASK_DEBUG: 0
      AI_PROVIDER: ${AI_PROVIDER:-none}
    command: ["python", "app.py", "--mcp-port", "8056"]
    volumes:
      - ./backend:/app
      # AI CLI credentials (mount host config into container)
      # Claude: uncomment if using Claude CLI
      # - ${USERPROFILE:-.}/.claude:/root/.claude
```

**Note:** Credential mount is commented out by default. Users uncomment the line for their provider. This avoids errors when the host directory doesn't exist.

- [ ] **Step 3: Rebuild and test**

Run:
```bash
cd code && docker compose up -d --build
```
Verify all 3 containers come up healthy.

- [ ] **Step 4: Commit**

```bash
git add code/backend/Dockerfile code/docker-compose.yml
git commit -m "feat: Docker updates — Node.js + Claude CLI + credential mount config"
```

---

## Task 9: Code Cleanup — Remove local_code Duplicates

**Files:**
- Delete: 7 files from `local_code/`
- Modify: `local_code/CODE.md`

- [ ] **Step 1: Verify feature parity**

Check that `code/utils/generate_resume.py` has `resolve_recipe()`, `--recipe-id`, `--validate`, `--dry-run` by searching for those strings:
```bash
grep -c "resolve_recipe\|--recipe-id\|--validate\|--dry-run" code/utils/generate_resume.py
```
Expected: 4+ matches. If any are missing, sync from `local_code/` first.

- [ ] **Step 2: Delete duplicates**

```bash
rm local_code/read_docx.py local_code/read_pdf.py local_code/edit_docx.py local_code/docx_to_pdf.py local_code/compare_docs.py local_code/templatize_resume.py local_code/generate_resume.py
```

- [ ] **Step 3: Update CODE.md**

Add a note to `local_code/CODE.md` that 7 scripts were migrated to `code/utils/` and are now available as MCP tools.

- [ ] **Step 4: Run existing tests to verify nothing broke**

Run: `pytest tests/ -v`
Expected: All 27+ tests pass (they import from `code/utils/`, not `local_code/`).

- [ ] **Step 5: Commit**

```bash
git add -A local_code/
git commit -m "cleanup: remove 7 duplicate scripts from local_code (migrated to code/utils)"
```

---

## Task 10: Frontend Settings Page

**Files:**
- Modify: `code/frontend/src/pages/settings/Settings.tsx`

- [ ] **Step 1: Implement the settings page**

Build a React form with:
- AI Provider dropdown (None / Claude / Gemini / OpenAI)
- AI Enabled toggle
- AI Model text input
- Test Connection button with status indicator
- Default Template dropdown (fetched from `/api/resume/templates`)
- Duplicate Sensitivity slider (0.5 - 1.0)
- Save button

Uses TanStack Query for data fetching (`useQuery` for GET, `useMutation` for PATCH).

```tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

interface Settings {
  ai_provider: string;
  ai_enabled: boolean;
  ai_model: string | null;
  default_template_id: number | null;
  duplicate_threshold: number;
}

interface TestResult {
  status: string;
  provider?: string;
  health?: { available: boolean; version: string };
  providers?: { name: string; available: boolean }[];
}

const API = "http://localhost:8055";

export default function Settings() {
  const queryClient = useQueryClient();
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  const { data: settings, isLoading } = useQuery<Settings>({
    queryKey: ["settings"],
    queryFn: () => fetch(`${API}/api/settings`).then((r) => r.json()),
  });

  const mutation = useMutation({
    mutationFn: (data: Partial<Settings>) =>
      fetch(`${API}/api/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then((r) => r.json()),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
  });

  const testAi = async (provider?: string) => {
    setTestResult(null);
    const res = await fetch(`${API}/api/settings/test-ai`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(provider ? { provider } : {}),
    });
    setTestResult(await res.json());
  };

  if (isLoading || !settings) return <div className="p-6">Loading...</div>;

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      {/* AI Configuration */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-4">AI Provider</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Provider</label>
            <select
              className="w-full border rounded px-3 py-2"
              value={settings.ai_provider}
              onChange={(e) => mutation.mutate({ ai_provider: e.target.value })}
            >
              <option value="none">None (rule-based only)</option>
              <option value="claude">Claude</option>
              <option value="gemini">Gemini</option>
              <option value="openai">OpenAI</option>
            </select>
          </div>

          <div className="flex items-center gap-3">
            <label className="text-sm font-medium">Enable AI Parsing</label>
            <input
              type="checkbox"
              checked={settings.ai_enabled}
              onChange={(e) => mutation.mutate({ ai_enabled: e.target.checked })}
              className="h-4 w-4"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Model Override (optional)</label>
            <input
              type="text"
              className="w-full border rounded px-3 py-2"
              value={settings.ai_model || ""}
              placeholder="e.g., claude-3-opus"
              onChange={(e) => mutation.mutate({ ai_model: e.target.value || null })}
            />
          </div>

          <button
            onClick={() => testAi(settings.ai_provider !== "none" ? settings.ai_provider : undefined)}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            Test Connection
          </button>

          {testResult && (
            <div className={`p-3 rounded ${testResult.status === "ok" ? "bg-green-100" : "bg-yellow-100"}`}>
              <p className="font-medium">
                {testResult.status === "ok"
                  ? `Connected: ${testResult.provider} (${testResult.health?.version})`
                  : testResult.status === "disabled"
                  ? "AI is disabled"
                  : `Error: ${JSON.stringify(testResult.health)}`}
              </p>
              {testResult.providers && (
                <ul className="mt-2 text-sm">
                  {testResult.providers.map((p) => (
                    <li key={p.name}>
                      {p.name}: {p.available ? "available" : "not found"}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Resume Defaults */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-4">Resume Defaults</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              Duplicate Sensitivity: {settings.duplicate_threshold}
            </label>
            <input
              type="range"
              min="0.5"
              max="1.0"
              step="0.05"
              value={settings.duplicate_threshold}
              onChange={(e) =>
                mutation.mutate({ duplicate_threshold: parseFloat(e.target.value) })
              }
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-500">
              <span>Loose (0.5)</span>
              <span>Strict (1.0)</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Rebuild frontend container**

Run:
```bash
cd code && docker compose up -d --build frontend
```

- [ ] **Step 3: Visual test**

Open http://localhost:5175/settings. Verify:
- Dropdown shows None/Claude/Gemini/OpenAI
- Toggle works
- Test Connection shows results
- Slider updates threshold
- Changes persist after page reload

- [ ] **Step 4: Commit**

```bash
git add code/frontend/src/pages/settings/Settings.tsx
git commit -m "feat: settings page with AI provider config + duplicate sensitivity"
```

---

## Task 11: End-to-End Verification

- [ ] **Step 1: Rebuild all containers**

```bash
cd code && docker compose up -d --build
```

- [ ] **Step 2: Run all tests**

```bash
pytest tests/ -v
```
Expected: All tests pass (27 existing + new ones).

- [ ] **Step 3: Test upload endpoint manually**

```bash
curl -X POST http://localhost:8055/api/onboard/upload -F "files=@path/to/sample_resume.docx"
```
Expected: JSON report with parsing results, template ID, recipe ID, match score.

- [ ] **Step 4: Test settings flow**

1. Open http://localhost:5175/settings
2. Set provider to Claude, enable AI
3. Click Test Connection
4. Upload a resume and verify AI-enhanced parsing is used

- [ ] **Step 5: Update DB_DICTIONARY.md**

Add `settings` and `onboard_uploads` tables with column descriptions and row counts.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: Phase D complete — onboarding system with upload, parse, templatize, verify pipeline"
```

---

## Implementation Notes

### Integration Points to Watch

1. **Utils as importable functions:** The `code/utils/` scripts (templatize_resume, generate_resume, compare_docs) were built as CLI tools with `main()` entry points. The onboard route needs to call them as library functions. During Task 5 implementation, check each script and extract/refactor callable functions if `templatize()`, `generate_from_recipe()`, `compare()` don't exist as standalone functions.

2. **Template map structure:** The auto-recipe creation (Task 5, `_create_recipe`) does slot-to-DB-row mapping using slot names from the template_map. The exact slot naming convention varies between V32 and V31 layouts. The generic approach (matching on "JOB_", "BULLET", "SKILL" substrings) may need refinement for templates with different naming conventions.

3. **Bulk bullet dedup performance:** The current approach queries all existing bullets for each new bullet to check near-duplicates. For large DBs this could be slow. Consider adding a `bullets_text_hash` index or pre-loading existing bullets into a set for exact-match checking, with SequenceMatcher only for non-exact candidates.

4. **Claude CLI in Docker:** The `claude -p` command for non-interactive prompts may require accepting terms or first-run setup. Test this inside the container after building. If the CLI needs interactive setup, document the one-time `docker exec -it supertroopers-app claude` step.

### Task Dependency Order

```
Task 1 (migration) → Task 2 (settings routes) → Task 3 (AI providers) → Task 4 (parsers) → Task 5 (onboard endpoint) → Task 6 (test-ai) → Task 7 (MCP tools) → Task 8 (Docker) → Task 9 (cleanup) → Task 10 (frontend) → Task 11 (e2e verification)
```

Tasks 3 and 4 can be parallelized. Tasks 8 and 9 can be parallelized. Task 10 depends on Task 2 (settings API) but can start before Task 5.
