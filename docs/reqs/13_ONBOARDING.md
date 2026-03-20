# 13 — Onboarding System

**Parent:** `0_APPLICATION_REQUIREMENTS.md` Section 13 (13.1, 13.2, 13.5)
**Status:** Design
**Date:** 2026-03-19

---

## 1. Overview

The onboarding system lets a new user go from "I have resume files" to "the platform can reconstruct and tailor my resumes" in one flow. Upload .docx/.pdf files (single or bulk), auto-parse into career data, templatize the original formatting, create recipes, and verify reconstruction matches the original.

AI-enhanced parsing (Claude, Gemini, OpenAI, or any CLI) is optional. When available it produces better results. When not, a rule-based parser handles the job.

### Design Principles

- **Single-user, local-only** — no auth, no multi-tenant, no API keys to manage
- **Graceful degradation** — AI-enhanced when configured, rule-based fallback always works
- **Modular AI providers** — adapter pattern, easy to add new providers
- **Automated verification** — every upload produces a reconstruction match score
- **Append, don't replace** — new bullets get added alongside existing ones

---

## 2. Pipeline

```
Upload (.docx/.pdf)
  │
  ├─ PDF? ──→ pdf2docx ──→ .docx
  │
  ▼
Extract text (read_docx.py)
  │
  ▼
Parse into structured data
  ├─ AI provider enabled? ──→ Claude/Gemini/OpenAI CLI parse
  └─ Fallback ──→ Rule-based regex/heuristic parse
  │
  ▼
Insert into DB
  ├─ career_history (employer, title, dates, location)
  ├─ bullets (append; flag exact/near duplicates)
  └─ skills (deduplicate)
  │
  ▼
Templatize (templatize_resume.py)
  ├─ Placeholder .docx template
  └─ template_map JSON
  │
  ▼
Auto-create recipe
  └─ Map each slot → DB row that was just inserted
  │
  ▼
Reconstruct (generate_resume.py)
  └─ Generate .docx from recipe + template
  │
  ▼
Compare (compare_docs.py)
  └─ Original vs reconstructed → match %, line diff
  │
  ▼
Report
  ├─ Rows inserted (career_history, bullets, skills counts)
  ├─ Duplicates flagged (exact + near-match)
  ├─ Template ID, Recipe ID created
  ├─ Match score + diff details
  └─ Errors (if any step failed for a file)
```

---

## 3. File Handling

### 3.1 Upload Endpoint

`POST /api/onboard/upload` — multipart/form-data, accepts one or more files.

**Accepted formats:** .docx, .pdf

**Bulk upload:** multiple files in one request, processed sequentially. Per-file results returned as an array.

### 3.2 PDF Conversion

PDF files are converted to .docx before entering the pipeline using `pdf2docx` (Python library). Both the original PDF and converted .docx are retained.

**Quality gate:** After conversion, compare paragraph count and check for VML shape loss. If conversion quality is low (e.g., < 50% of expected paragraphs, missing shapes), the report flags it with `conversion_quality: "degraded"` and a warning. **.docx is the recommended upload format** — PDF conversion is best-effort and may lose complex formatting (multi-column layouts, VML shapes, custom fonts).

### 3.3 File Storage

Original files stored in `resume_templates` table with `template_type = 'uploaded_original'`. Converted .docx (from PDF) stored separately with `template_type = 'uploaded_converted'`. These are distinct from existing values (`full`, `placeholder`) which describe templatized outputs.

**Note:** Migration 008 should widen `resume_templates.template_type` from `varchar(20)` to `varchar(50)` to accommodate new values and leave room for future ones.

---

## 4. Resume Parsing

### 4.1 AI-Enhanced Parsing (when configured)

The backend calls the configured AI CLI directly (installed in the Docker container).

**Prompt pattern:**
```
Parse this resume text into JSON matching this schema:
{
  "career_history": [{ "employer", "title", "start_date", "end_date", "location", "industry" }],
  "bullets": [{ "employer", "text", "type", "metrics_json" }],
  "skills": [{ "name", "category", "proficiency" }]
}

Resume text:
<extracted text>
```

The AI returns structured JSON. Backend validates the schema before inserting.

### 4.2 Rule-Based Fallback

When AI is not available or disabled:

1. **Section detection** — identify headers: Experience, Education, Skills, Summary, etc. via regex patterns (caps, bold, underline, known header words)
2. **Employer block extraction** — company name + title + date range + location. Common patterns: "Company Name | Title | Date - Date" or similar
3. **Bullet extraction** — lines starting with bullet chars (•, -, *, ▪) under each employer block
4. **Skills extraction** — comma/pipe-separated lists under Skills headers, plus keyword extraction from bullets
5. **Education extraction** — degree, institution, date patterns

Less accurate on unusual formats. Designed to handle 80% of standard resumes. Returns a top-level `confidence` score (0.0-1.0) representing overall parse quality, so the report can flag low-confidence parses for manual review.

### 4.3 Orchestration

The upload endpoint (`routes/onboard.py`) orchestrates the parsing decision:

1. Read `ai_enabled` and `ai_provider` from settings table
2. Call `get_provider(name)` from the AI provider factory
3. If provider is not None and `is_available()` returns True → use `ai_enhanced.py` (which calls `provider.parse_resume()`)
4. Otherwise → use `rule_based.py` fallback
5. Both parsers return the same schema: `{ career_history: [], bullets: [], skills: [], confidence: float }`

### 4.4 Duplicate Handling on Insert

| Scenario | Action |
|----------|--------|
| Exact bullet match (identical text) | Skip, log as duplicate |
| Near-match (≥ threshold, default 85% similarity) | Flag for review; if AI available, resolve via AI |
| No match | Append normally |

Similarity calculated via `difflib.SequenceMatcher`. Threshold configurable in settings.

**AI duplicate resolution prompt:**
```
Given two resume bullets that are similar but not identical:
A: "{bullet_a}"
B: "{bullet_b}"

Which is stronger? Reply with JSON:
{ "action": "keep_a" | "keep_b" | "merge", "result": "the chosen or merged text", "reason": "brief explanation" }
```

If AI returns `merge`, the merged text is inserted as a new bullet and neither original is deleted (append-only). If AI is unavailable, near-matches are inserted with a `duplicate_flag = true` column for later manual review.

---

## 5. Templatize → Recipe → Verify

After parsing and DB insert, for each .docx file:

### 5.1 Templatize

Call `templatize_resume.py` on the original .docx (or converted .docx for PDFs). Produces:
- Placeholder .docx template (text replaced with `{{SLOT}}` markers)
- `template_map` JSON (slot names, types, formatting rules, original text)

Both stored in `resume_templates` table.

### 5.2 Auto-Create Recipe

Map each placeholder slot to the corresponding DB row:
- `JOB_1_HEADER` → career_history row for that employer
- `JOB_1_BULLET_1` → bullets row with matching text
- `HIGHLIGHT_1` → bullets row (type=highlight)
- `SKILL_KEYWORDS` → skills query
- etc.

Matching uses the original text from template_map against the just-inserted DB rows. Stored as a `resume_recipes` row.

### 5.3 Reconstruct

Call `generate_resume.py` with the new recipe + template. Produces a .docx file.

### 5.4 Compare

Call `compare_docs.py` on original vs reconstructed. Returns:
- Match percentage (target: ≥95%)
- Line-by-line diff of mismatches
- Categorized differences (formatting only, content mismatch, missing section)

### 5.5 Report

Per-file JSON result:
```json
{
  "filename": "resume_v32.docx",
  "status": "success",
  "parsing": {
    "method": "claude",
    "career_history_inserted": 4,
    "bullets_inserted": 25,
    "skills_inserted": 12,
    "duplicates_exact": 0,
    "duplicates_near": 2,
    "near_duplicates": [
      { "existing": "Led team of 8...", "new": "Led a team of 8...", "similarity": 0.92 }
    ]
  },
  "template_id": 5,
  "recipe_id": 6,
  "verification": {
    "match_score": 97.7,
    "diff_lines": 3,
    "diff_details": ["Line 42: curly→straight quote normalization"]
  }
}
```

---

## 6. AI Provider Integration

### 6.1 Architecture

AI CLI is installed directly in the `supertroopers-app` Docker container. Host credentials are volume-mounted so no separate API key management is needed.

```
Docker Container (supertroopers-app)
  ├─ Flask API (port 8055)
  ├─ MCP Server (port 8056)
  └─ AI CLI (claude/gemini/openai)
      └─ Credentials mounted from host (~/.claude/, ~/.config/, etc.)
```

### 6.2 Modular Provider Adapter

```
code/backend/ai_providers/
  __init__.py          # Provider registry + factory
  base.py              # Abstract base class
  claude_provider.py   # Claude CLI adapter
  gemini_provider.py   # Gemini CLI adapter
  openai_provider.py   # OpenAI CLI adapter
```

**Base class:**
```python
class AIProvider:
    name: str
    cli_command: str  # e.g., "claude", "gemini", "openai"

    def is_available(self) -> bool:
        """Check if CLI is installed and credentials are present."""

    def parse_resume(self, text: str) -> dict:
        """Send resume text, get structured JSON back."""

    def resolve_duplicate(self, bullet_a: str, bullet_b: str) -> str:
        """Ask AI which bullet is better, or merge them."""

    def health_check(self) -> dict:
        """Return provider status, version, model info."""
```

**Factory:**
```python
def get_provider(name: str = None) -> AIProvider:
    """Return configured provider, or None if AI disabled."""
    # Reads from settings table
    # Falls back to None if provider unavailable
```

### 6.3 Adding a New Provider

To add a new AI provider:

1. Create `code/backend/ai_providers/{name}_provider.py`
2. Implement the `AIProvider` base class (4 methods)
3. Register in `__init__.py` provider registry
4. Add the CLI install step to `Dockerfile` (or document manual install)
5. Add the credential mount path to `docker-compose.yml`
6. Add the provider name to the settings dropdown (frontend)

**Example adapter (minimal):**
```python
class MyProvider(AIProvider):
    name = "my_provider"
    cli_command = "my-ai"

    def is_available(self) -> bool:
        return shutil.which(self.cli_command) is not None

    def parse_resume(self, text: str) -> dict:
        result = subprocess.run(
            [self.cli_command, "prompt", "--format", "json"],
            input=f"Parse this resume:\n{text}",
            capture_output=True, text=True
        )
        return json.loads(result.stdout)
```

### 6.4 Docker Setup — Claude (Primary)

**Dockerfile additions:**
```dockerfile
# Install Node.js (for Claude CLI)
RUN apt-get update && apt-get install -y nodejs npm
# Install Claude CLI
RUN npm install -g @anthropic-ai/claude-code
```

**docker-compose.yml additions (Windows host):**
```yaml
supertroopers-app:
  volumes:
    - ${USERPROFILE}/.claude:/root/.claude    # Claude credentials (rw for token refresh)
  environment:
    - AI_PROVIDER=claude
```

**Note:** Credentials are mounted read-write (not `:ro`) because the CLI may need to refresh OAuth tokens. On Linux/Mac, replace `${USERPROFILE}` with `${HOME}`.

**Startup:** `docker compose up -d` — same single command. Claude CLI is available inside the container with host credentials.

### 6.5 Docker Setup — Other Providers

**Gemini:**
```dockerfile
RUN npm install -g @google/generative-ai-cli
```
```yaml
volumes:
  - ${USERPROFILE}/.config/gcloud:/root/.config/gcloud
```

**OpenAI:**
```dockerfile
RUN pip install openai-cli
```
```yaml
volumes:
  - ${USERPROFILE}/.openai:/root/.openai
```

**Other providers:** Follow the "Adding a New Provider" guide in Section 6.3. Key steps:
1. Identify the CLI command and install method (npm/pip/binary)
2. Identify where the CLI stores credentials on the host
3. Add the install to Dockerfile, mount the credential dir in docker-compose.yml
4. Implement the adapter (4 methods — see Section 6.3 example)

---

## 7. Settings

### 7.1 Database Table

**Migration 008: settings + onboard_uploads**
```sql
CREATE TABLE settings (
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

INSERT INTO settings (id) VALUES (1);

-- Track upload history for audit, re-processing, rollback
CREATE TABLE onboard_uploads (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(500) NOT NULL,
    file_type VARCHAR(10) NOT NULL,         -- 'docx' or 'pdf'
    file_size INTEGER,
    status VARCHAR(50) DEFAULT 'processing', -- processing, success, partial, failed
    parsing_method VARCHAR(50),              -- 'claude', 'gemini', 'openai', 'rule_based'
    parsing_confidence FLOAT,
    career_history_ids INTEGER[],            -- rows created
    bullet_ids INTEGER[],
    skill_ids INTEGER[],
    template_id INTEGER REFERENCES resume_templates(id),
    recipe_id INTEGER REFERENCES resume_recipes(id),
    match_score FLOAT,
    report JSONB,                            -- full pipeline report
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

The `preferences` JSONB column on settings is reserved for future extensibility (search prefs, notification settings, etc.) without requiring additional migrations.

### 7.2 API Endpoints

- `GET /api/settings` — returns current settings
- `PATCH /api/settings` — update any field(s)
- `POST /api/settings/test-ai` — tests AI provider connection (runs health_check)

### 7.3 Frontend Settings Page

The existing `/settings` route gets populated with:
- **AI Provider** — dropdown (Claude / Gemini / OpenAI / None)
- **AI Enabled** — toggle switch
- **AI Model** — text input (optional override)
- **Test Connection** — button, shows success/fail + provider version
- **Default Template** — dropdown of existing templates
- **Duplicate Sensitivity** — slider (0.5 to 1.0, default 0.85)

---

## 8. Code Cleanup

### 8.1 Remove Duplicates from local_code/

Delete these 7 files from `local_code/` (already migrated to `code/utils/`):
- `read_docx.py`
- `read_pdf.py`
- `edit_docx.py`
- `docx_to_pdf.py`
- `compare_docs.py`
- `templatize_resume.py`
- `generate_resume.py`

**Before deletion:** verify feature parity between `local_code/` and `code/utils/` versions. In particular, confirm `code/utils/generate_resume.py` has `resolve_recipe()`, `--recipe-id`, `--validate`, and `--dry-run` modes (added in Session 6). If any features are missing, sync first, then delete.

Update `local_code/CODE.md` to note migration.

### 8.2 Expose Utils as MCP Tools

New MCP tools wrapping `code/utils/` scripts:
- `read_docx(file_path)` — extract text from .docx
- `read_pdf(file_path)` — extract text from .pdf
- `edit_docx(file_path, edits)` — programmatic .docx editing
- `templatize_resume(file_path, layout)` — create placeholder template
- `generate_resume(recipe_id, output_path)` — already exists, verify works
- `compare_docs(file_a, file_b)` — compare two documents
- `docx_to_pdf(file_path)` — convert .docx to .pdf

---

## 9. New Routes & MCP Tools Summary

### Flask Routes
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/onboard/upload` | Upload file(s), run full pipeline |
| GET | `/api/settings` | Get current settings |
| PATCH | `/api/settings` | Update settings |
| POST | `/api/settings/test-ai` | Test AI provider connection |

### MCP Tools (new)
| Tool | Purpose |
|------|---------|
| `onboard_resume(file_path, ai_override=None)` | Run full pipeline on a single file: parse → insert → templatize → recipe → verify. Returns full report JSON. `ai_override` forces a specific provider or 'none' for rule-based. |
| `read_docx` | Extract text from .docx |
| `read_pdf` | Extract text from .pdf |
| `templatize_resume` | Create placeholder template from .docx |
| `compare_docs` | Compare two documents |
| `docx_to_pdf` | Convert .docx to .pdf |

### Migration
- **008_settings_onboard.sql** — settings table + onboard_uploads table

---

## 10. Dependencies

### Python (add to requirements.txt)
- `pdf2docx` — PDF to .docx conversion

### Node (in Dockerfile)
- `@anthropic-ai/claude-code` — Claude CLI (optional, for AI-enhanced parsing)

### Existing (no changes)
- `python-docx` — already in requirements.txt
- `PyPDF2` or `pdfplumber` — check if already present, may be used by read_pdf.py

---

## 11. Verification

### Integration Tests
- Upload single .docx → verify career_history, bullets, skills inserted
- Upload single .pdf → verify pdf2docx conversion + full pipeline
- Upload bulk (3 files) → verify per-file results
- Upload with duplicate bullets → verify dedup logic
- Upload with AI enabled → verify Claude-enhanced parse (mock CLI in tests)
- Upload with AI disabled → verify rule-based fallback
- Settings CRUD → verify persist and retrieve
- AI test connection → verify health check
- Full round-trip: upload → templatize → recipe → reconstruct → compare ≥ 95% match

### Manual Verification
- Upload Stephen's V32 resume → verify reconstruction matches original
- Upload a PDF resume → verify conversion + reconstruction
- Toggle AI on/off → verify both paths produce valid output

---

## 12. Files Created / Modified

### New Files
- `code/backend/ai_providers/__init__.py`
- `code/backend/ai_providers/base.py`
- `code/backend/ai_providers/claude_provider.py`
- `code/backend/ai_providers/gemini_provider.py`
- `code/backend/ai_providers/openai_provider.py`
- `code/backend/routes/onboard.py`
- `code/backend/routes/settings.py`
- `code/backend/parsers/__init__.py`
- `code/backend/parsers/rule_based.py`
- `code/backend/parsers/ai_enhanced.py`
- `code/db/migrations/008_settings_onboard.sql`
- `tests/test_onboard.py`
- `tests/test_settings.py`

### Modified Files
- `code/backend/routes/__init__.py` — register onboard_bp, settings_bp
- `code/backend/mcp_server.py` — add util MCP tools
- `code/backend/requirements.txt` — add pdf2docx
- `code/Dockerfile` — add Claude CLI install + credential mount docs
- `code/docker-compose.yml` — add volume mount for credentials
- `local_code/CODE.md` — note migration of 7 scripts

### Deleted Files
- `local_code/read_docx.py`
- `local_code/read_pdf.py`
- `local_code/edit_docx.py`
- `local_code/docx_to_pdf.py`
- `local_code/compare_docs.py`
- `local_code/templatize_resume.py`
- `local_code/generate_resume.py`

---

## 13. Scope & Deferred Items

**This spec covers:** 13.1 (settings/profile — settings only, no multi-user), 13.2 (KB population via upload + parse), 13.5 (template setup via templatize pipeline).

**Deferred to future phases:**
- 13.3 — External integrations setup (Gmail, Calendar, LinkedIn, Indeed MCP guides)
- 13.4 — Voice & style configuration (voice sample upload, banned words editor, industry presets)
- 13.6 — Getting started wizard (welcome splash screen with click-through onboarding: "load your resume here," step-by-step instructions, skippable). Defer to Phase E alongside documentation/open-sourcing
- 13.7 — Documentation (README, API ref, setup guides) → Phase E
- 13.8 — Claude Code integration (CLAUDE.md template, SKILLS/) → Phase E
- Manual review/edit UI for parsed content → deferred to template/resume editing phase
