# Phase E: Documentation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create documentation that enables non-technical job seekers to set up and use SuperTroopers, with technical references for developers.

**Architecture:** 8 independent files — README, Setup Guide, API Reference, MCP Reference, Troubleshooting, CLAUDE.md, .mcp.json.example, .env.example. Each can be written in parallel. Content is generated from the existing codebase (105 endpoints, 42 MCP tools, 33 tables).

**Tech Stack:** Markdown docs, no code changes.

**Spec:** `code/docs/specs/2026-03-20-phase-e-documentation.md`

---

## CRITICAL: Content Sources

All documentation content comes from the live codebase. Do NOT invent endpoints or tool signatures.

### Route Files (14 files, 105 endpoints)
Located in `code/backend/routes/`. Each file has `@bp.route()` decorators with method and path.

### MCP Tools (41 tools)
Located in `code/backend/mcp_server.py`. Each tool has `@mcp.tool()` decorator, docstring with description, Args, Returns.

### Database
33 tables across 8 migrations in `code/db/migrations/`. Live reference: `code/db/migrations/DB_DICTIONARY.md`.

### Docker
`code/docker-compose.yml` — 3 services (postgres, backend, frontend). Ports: 5555 (DB), 8055 (API), 8056 (MCP SSE), 5175 (frontend).

---

## File Structure

```
code/
  README.md                    # Pitch page (~50 lines)
  CLAUDE.md                    # Operational AI agent instructions
  .env.example                 # Environment variable template
  .mcp.json.example            # MCP config template for Claude Code
  docs/
    SETUP.md                   # Full walkthrough (~300 lines)
    API_REFERENCE.md           # All 105 endpoints documented
    MCP_REFERENCE.md           # All 41 tools documented
    TROUBLESHOOTING.md         # Common issues + fixes
```

---

## Task 1: .env.example and .mcp.json.example

**Files:**
- Create: `code/.env.example`
- Create: `code/.mcp.json.example`

- [ ] **Step 1: Create .env.example**

```
# SuperTroopers Environment Variables
# Copy this file to .env before running docker compose up

# Database password (required)
DB_PASSWORD=change-me-to-something-secure

# AI provider (optional): none, claude, gemini, openai
AI_PROVIDER=none
```

Save to `code/.env.example`.

- [ ] **Step 2: Create .mcp.json.example**

Read the existing `.mcp.json` at the project root for the correct format. Create a clean version at `code/.mcp.json.example` with:
- SSE transport pointing to `http://localhost:8056/sse`
- The `supertroopers` server name
- Strip any user-specific config (ContextStream, Chrome DevTools, etc.)

The file should look like:
```json
{
  "mcpServers": {
    "supertroopers": {
      "type": "sse",
      "url": "http://localhost:8056/sse"
    }
  }
}
```

- [ ] **Step 3: Verify .env and .mcp.json are gitignored**

Check `code/.gitignore` contains `.env` and `.mcp.json`. If not, add them. The `.example` variants should NOT be gitignored (they're templates for users to copy).

---

## Task 2: README.md

**Files:**
- Create: `code/README.md`

- [ ] **Step 1: Write the README**

Structure:
```markdown
# SuperTroopers

Your AI-powered reverse recruiting command center. Upload your resume, and SuperTroopers parses it into structured career data, generates tailored resumes via recipes, tracks applications, analyzes job fit, and manages your entire job search... all from your terminal.

## What It Does

- **Resume Intelligence** — Upload .docx/.pdf, auto-parse into career history, bullets, skills
- **Recipe-Based Generation** — Template system that produces tailored .docx resumes for any role
- **Gap Analysis** — Match your experience against job descriptions, see what fits and what's missing
- **Application Tracking** — Full pipeline: saved jobs -> applications -> interviews -> offers
- **Voice Guard** — Configurable rules to keep AI-generated text sounding like you, not a robot
- **42 MCP Tools** — Every feature accessible to AI agents via Model Context Protocol

## Architecture

[text diagram: Docker with 3 containers, Flask API, MCP SSE, React frontend, PostgreSQL]

## Quick Start

1. Install [Docker Desktop](https://docker.com/products/docker-desktop/) and [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
2. Clone this repo and `cd code`
3. `cp .env.example .env && docker compose up -d`
4. Copy `.mcp.json.example` to your project root as `.mcp.json`
5. Run `claude` and ask: "Upload my resume at path/to/resume.docx"

Full setup guide: [docs/SETUP.md](docs/SETUP.md)

## Documentation

- [Setup Guide](docs/SETUP.md) — Step-by-step from zero to working
- [API Reference](docs/API_REFERENCE.md) — All 105 REST endpoints
- [MCP Tool Reference](docs/MCP_REFERENCE.md) — All 42 MCP tools
- [Troubleshooting](docs/TROUBLESHOOTING.md) — Common issues and fixes

## Built For

- **Claude Code** (primary) — Full MCP integration, CLAUDE.md with routing and workflows
- **Other AI agents** — Any MCP-compatible tool can connect via SSE at localhost:8056
- **Direct API** — REST API at localhost:8055 for custom integrations

## Tech Stack

Python/Flask, PostgreSQL + pgvector, React/TypeScript/Vite, Docker, MCP (SSE transport)

## Status

Active development. Core platform complete. PC (Windows 11) tested. Mac not yet tested.

## License

[placeholder]
```

Save to `code/README.md`.

---

## Task 3: Setup Guide

**Files:**
- Create: `code/docs/SETUP.md`

- [ ] **Step 1: Write the complete setup guide**

This is the longest document (~300 lines). Follow the spec flow exactly:

1. **Prerequisites** — Windows PC caveat, admin access, Git OR ZIP download, Node.js LTS (with install link + verify command), a resume file
2. **Install Docker Desktop** — download link, install steps, verify `docker --version`, WSL2 gotcha, Mac callout
3. **Install Claude Code** — link, `npm install -g @anthropic-ai/claude-code`, verify `claude --version`, "other agents" callout
4. **Clone and Start** — git clone OR ZIP download, cd, cp .env.example .env, docker compose up -d, wait for healthy
5. **Configure MCP** — cp .mcp.json.example .mcp.json, start claude, verify tools appear
6. **Verify Everything Works** — checklist: API health (8055), frontend (5175), MCP tools visible
7. **Upload Your First Resume** — via Claude Code natural language OR mcp tool OR curl command, explain what happens in the pipeline
8. **Generate a Test Resume** — use recipe from upload, get .docx output, compare to original
9. **Next Steps** — customize voice rules, connect Gmail, search jobs, tailor resumes
10. **Tips for Other AI Agents** — SSE endpoint, Gemini CLI config hint, Cursor/Windsurf hint

Every command must be copy-pasteable. Use callout boxes for warnings and tips. Include expected output for verification steps.

Save to `code/docs/SETUP.md`.

---

## Task 4: API Reference

**Files:**
- Create: `code/docs/API_REFERENCE.md`

- [ ] **Step 1: Write the API reference**

Read ALL route files in `code/backend/routes/` to extract exact endpoints, parameters, and response shapes. Do NOT guess — read the actual code.

**Route files to read:**
- `code/backend/routes/activity.py`
- `code/backend/routes/analytics.py`
- `code/backend/routes/career.py`
- `code/backend/routes/contacts.py`
- `code/backend/routes/content.py`
- `code/backend/routes/gap_analysis.py`
- `code/backend/routes/interview_extras.py`
- `code/backend/routes/knowledge.py`
- `code/backend/routes/onboard.py`
- `code/backend/routes/pipeline.py`
- `code/backend/routes/resume.py`
- `code/backend/routes/saved_jobs.py`
- `code/backend/routes/search.py`
- `code/backend/routes/settings.py`

Also read `code/backend/app.py` for the health endpoint and any middleware.

**Format for each endpoint:**

```markdown
### METHOD /api/path

Description from the route docstring.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|

**Request Body** (if POST/PATCH/PUT):
```json
{ example }
```

**Response:**
```json
{ example }
```
```

**Organize by section:**
1. Health & Settings (health, settings, test-ai)
2. Career Data (career-history, bullets, skills, summary-variants, kb/export)
3. Resume Management (recipes, templates, header, education, certifications, versions, generate)
4. Job Search (saved-jobs, gap-analyses, search/gap-analysis)
5. Applications & Pipeline (applications, status-history, materials, follow-ups, stale)
6. Interviews (interviews, prep, debriefs)
7. Networking (contacts, outreach, referrals, companies)
8. Content & Knowledge (content, voice-rules, salary-benchmarks, cola-markets, emails, documents)
9. Search (search/bullets, search/emails, search/companies, search/contacts)
10. Analytics (funnel, monthly, sources, summary)
11. Activity Log
12. Onboarding (upload)

Save to `code/docs/API_REFERENCE.md`.

---

## Task 5: MCP Tool Reference

**Files:**
- Create: `code/docs/MCP_REFERENCE.md`

- [ ] **Step 1: Write the MCP tool reference**

Read `code/backend/mcp_server.py` to extract ALL `@mcp.tool()` decorated functions. For each tool, document:
- Tool name (the function name)
- Description (from docstring)
- Parameters (name, type, required/optional, description — from docstring Args section)
- Returns (from docstring Returns section)
- Example usage (natural language: "Ask Claude: ...")

**41 tools organized by category:**

1. **Career & Knowledge Base** — search_bullets, get_career_history, get_skills, get_summary_variant, get_candidate_profile
2. **Resume Generation** — get_resume_data, generate_resume, list_recipes, get_recipe, create_recipe, update_recipe
3. **Job Search & Analysis** — match_jd, save_job, list_saved_jobs, update_saved_job, save_gap_analysis, get_gap_analysis
4. **Applications & Pipeline** — search_applications, add_application, update_application, log_follow_up, get_stale_applications
5. **Interviews** — save_interview_prep, save_interview_debrief
6. **Networking** — search_contacts, network_check, search_companies, get_company_dossier
7. **Content & Voice** — get_voice_rules, check_voice, get_salary_data, get_rejection_analysis, search_emails, get_analytics
8. **Document Utilities** — mcp_read_docx, mcp_read_pdf, mcp_edit_docx, mcp_docx_to_pdf, mcp_templatize_resume, mcp_compare_docs
9. **Onboarding** — onboard_resume
10. **Profile** — update_header

**Format:**
```markdown
### tool_name

Description from docstring.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|

**Returns:** description

**Example:** "Ask Claude: search my bullets for leadership experience"
```

Save to `code/docs/MCP_REFERENCE.md`.

---

## Task 6: Troubleshooting Guide

**Files:**
- Create: `code/docs/TROUBLESHOOTING.md`

- [ ] **Step 1: Write the troubleshooting guide**

Organized by symptom. For each issue: symptom, cause, fix.

**Sections:**

1. **Docker Issues**
   - Docker Desktop won't start (WSL2 not enabled, Hyper-V conflict)
   - `docker compose up` fails (port already in use — 5555, 8055, 8056, 5175)
   - Container exits immediately (check logs: `docker logs supertroopers-app`)
   - DB container unhealthy (disk space, permissions on db_data folder)

2. **API Issues**
   - Health endpoint returns error (DB connection — check DB_PASSWORD in .env matches docker-compose)
   - 404 on endpoints (container not rebuilt after code changes — `docker compose up -d --build`)
   - CORS errors from frontend (proxy config, ensure frontend container is running)

3. **MCP Issues**
   - Claude Code doesn't see tools (restart session, check .mcp.json path, verify SSE endpoint responds)
   - MCP tool returns error (check Docker logs, verify DB connection)
   - SSE connection drops (container restart, network issues)

4. **Upload / Parsing Issues**
   - Upload fails with 400 (wrong field name — use "files", check file extension .docx/.pdf)
   - Parser returns low confidence (complex resume format, try AI-enhanced parsing)
   - Template creation fails (resume too short, unusual formatting)

5. **Resume Generation Issues**
   - Generated resume looks wrong (recipe validation — check recipe slots match template)
   - Missing content in output (recipe references deleted data — run recipe validate)
   - Formatting issues (template corruption — re-upload original .docx)

6. **Frontend Issues**
   - Page won't load at localhost:5175 (container not running, port conflict)
   - Data not showing (API not reachable, check backend container)
   - Settings not saving (API error — check browser console)

7. **Windows-Specific**
   - Path issues (use forward slashes in commands, or quote paths with backslashes)
   - Line ending issues (configure git: `git config core.autocrlf true`)
   - WSL2 memory (Docker Desktop settings -> Resources -> Memory)

8. **Mac Users**
   - Platform is developed and tested on Windows 11. Mac is untested.
   - Docker Desktop for Mac should work but networking may differ
   - `docx_to_pdf` requires LibreOffice on Mac (not Word COM automation)
   - Report issues on GitHub

Save to `code/docs/TROUBLESHOOTING.md`.

---

## Task 7: CLAUDE.md (Operational Agent Instructions)

**Files:**
- Create: `code/CLAUDE.md`

- [ ] **Step 1: Write the operational CLAUDE.md**

Read the project root CLAUDE.md at `c:\Users\ssala\OneDrive\Desktop\Resumes\CLAUDE.md` as the source template. Create a generic version at `code/CLAUDE.md` that:

**Includes:**
- Platform description: "You are a reverse recruiting assistant powered by SuperTroopers"
- Docker startup check (same pattern: check containers, start if needed)
- MCP Tool Routing table — "User says X → use tool Y":
  - Upload/parse resume → onboard_resume
  - Generate resume → list_recipes, get_recipe, generate_resume
  - Search for jobs → match_jd
  - Gap analysis → match_jd, save_gap_analysis, get_gap_analysis
  - Track applications → search_applications, add_application, update_application
  - Company research → search_companies, get_company_dossier
  - Interview prep → save_interview_prep, save_interview_debrief
  - Networking → search_contacts, network_check
  - Voice/style check → get_voice_rules, check_voice
  - Email scanning → search_emails
  - Analytics → get_analytics
  - Read/edit documents → mcp_read_docx, mcp_read_pdf, mcp_edit_docx, mcp_docx_to_pdf
  - Compare documents → mcp_compare_docs
  - Create template → mcp_templatize_resume
  - Update profile → update_header
- Voice Rules enforcement: always run check_voice before delivering generated text
- Resume Integrity: metrics required, STAR format, pull from DB never invent
- Document Operations: use MCP tools, save to Output/
- Direct psql access: connection string (localhost:5555)
- Customization notes: "Edit this file to match your preferences"

**Excludes:**
- Stephen's personal data (campaign sections S1-S10, session memory references)
- ContextStream config
- RTK config
- Personal preferences (ask one question at a time, etc.)
- File archival references (Archived/, Notes/)
- local_code/ references
- Specific company/contact data

Save to `code/CLAUDE.md`.

---

## Task 8: Update Tracking Docs

**Files:**
- Modify: `recs/TODO.md`
- Modify: `CLAUDE.md` (project root)
- Modify: `code/docs/reqs/0_APPLICATION_REQUIREMENTS.md`

- [ ] **Step 1: Add living walkthrough TODO to recs/TODO.md**

Add a new section after Phase E:

```markdown
## Living Documentation (ongoing)
As features are built out and used, add user walkthrough guides:
- [ ] Email scanning walkthrough (Gmail setup + scan workflow)
- [ ] Job search walkthrough (Indeed MCP + save + gap analysis)
- [ ] Resume tailoring walkthrough (gap analysis -> recipe customization -> generate)
- [ ] Application tracking walkthrough (full pipeline: save job -> apply -> interview -> outcome)
- [ ] Company research walkthrough (dossier + contacts + networking)

## Deferred: Frontend User Guide
- [ ] In-app help/FAQ system (built into frontend)
- [ ] Getting started wizard
- [ ] Contextual help tooltips
```

- [ ] **Step 2: Add walkthrough note to project root CLAUDE.md**

In the "Session Handoff Protocol" section or "Always Enforced" section, add:

```markdown
### Documentation Updates
When building new features or workflows, also add a user walkthrough guide to `code/docs/guides/`. Each guide should explain the workflow from the user's perspective (what to say to Claude, what to expect, how to verify results). See `recs/TODO.md` "Living Documentation" section for the list.
```

- [ ] **Step 3: Check off 13.7 and 13.8 items in 0_APPLICATION_REQUIREMENTS.md**

In section 13.7 Documentation:
- [x] Docker one-command setup
- [x] README with architecture overview, setup instructions, quickstart
- [x] API reference (all endpoints with request/response examples)
- [x] MCP tool reference (all tools with parameters and examples)
- [ ] Schema migration guide — leave unchecked (not in scope)
- [ ] Contributing guide — leave unchecked (not in scope)
- [x] Troubleshooting guide

In section 13.8 Claude Code Integration:
- [x] CLAUDE.md template + SKILLS/ for other users
- [x] Installation guide for Claude Code + MCP setup
- [ ] Example SKILLS files — leave unchecked (deferred)
- [ ] Guide: "How to customize CLAUDE.md" — leave unchecked (deferred)

---

## Task Dependency Order

```
Task 1 (.env.example, .mcp.json.example) — no dependencies
Task 2 (README) — references Task 1 files
Task 3 (Setup Guide) — references Task 1 files
Task 4 (API Reference) — no dependencies
Task 5 (MCP Reference) — no dependencies
Task 6 (Troubleshooting) — no dependencies
Task 7 (CLAUDE.md) — no dependencies
Task 8 (Tracking docs) — after all others complete
```

**Parallelizable:** Tasks 1-7 can all run in parallel (independent files). Task 8 is the final step.

**Recommended execution:** Dispatch Tasks 1, 4, 5, 6 as subagents (mechanical, well-defined). Tasks 2, 3, 7 need more judgment (write inline or with capable model). Task 8 is a quick edit.
