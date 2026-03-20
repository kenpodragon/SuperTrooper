# Phase E: Documentation — Design Spec

**Goal:** Enable non-technical job seekers to set up and use SuperTroopers from scratch, while also providing technical references for developers and AI agent builders.

**Audience:** Primary — non-technical job seekers on Windows PCs. Secondary — developers extending the platform. Mac not yet tested.

---

## Deliverables

### 1. README.md (`code/README.md`)

Short pitch page (~50 lines):
- What SuperTroopers is (reverse recruiting command center)
- Who it's for (job seekers who want AI-powered resume management)
- Key capabilities (upload/parse resumes, recipe-based generation, gap analysis, application tracking, 42 MCP tools)
- Architecture diagram (text-based)
- Quick links to Setup Guide, API Reference, MCP Reference, Troubleshooting
- "Built for Claude Code" badge/note with tips for other agents
- License placeholder

### 2. Setup Guide (`code/docs/SETUP.md`)

Full walkthrough (~300 lines), assumes zero dev experience. Every command copy-pasteable.

**Flow:**

1. **Prerequisites**
   - Windows PC (Mac not yet tested — callout box with known differences)
   - Admin access (for Docker and Node.js installs)
   - Git installed (or download repo as ZIP from GitHub — provide both options)
   - Node.js LTS installed (required for Claude Code) — download link, verify: `node --version`
   - A .docx or .pdf resume to upload

2. **Install Docker Desktop**
   - Download link for Windows
   - Install steps (accept defaults)
   - Verify: `docker --version`
   - Common issue: WSL2 requirement on Windows, link to Microsoft docs
   - "Mac users: Docker Desktop for Mac should work but is untested"

3. **Install Claude Code**
   - Link to Anthropic's install page
   - `npm install -g @anthropic-ai/claude-code` (Node.js already installed in step 1)
   - Verify: `claude --version`
   - "Using a different AI agent?" callout — Gemini CLI, Cursor, etc. can connect via MCP SSE endpoint at `http://localhost:8056/sse`, consult their docs for MCP configuration

4. **Clone and Start the Platform**
   - Option A: `git clone <repo-url>` (if Git installed)
   - Option B: Download ZIP from GitHub and extract (for non-technical users)
   - `cd supertroopers/code`
   - Copy `.env.example` to `.env` (DB password pre-filled for local dev — contains DB_PASSWORD)
   - `docker compose up -d`
   - Wait for healthy: `docker ps` should show 3 containers (db, backend, frontend) all "Up"

5. **Configure MCP Connection**
   - Copy `.mcp.json.example` to `.mcp.json` in project root
   - File contents: SSE transport pointing to `http://localhost:8056/sse`
   - Start Claude Code in the project directory: `claude`
   - Verify: Claude should see SuperTroopers tools (ask it "what MCP tools do you have?")
   - Troubleshooting: if tools don't appear, restart Claude Code session, check Docker logs

6. **Verify Everything Works** (checkpoint before uploading data)
   - API health: open `http://localhost:8055/api/health` in browser — should show `{"status":"healthy","db":"connected"}`
   - Frontend: open `http://localhost:5175` — Settings page should show System Status all green
   - MCP: Claude Code should list SuperTroopers tools
   - If any of these fail, see Troubleshooting guide before proceeding

7. **Upload Your First Resume**
   - In Claude Code: "Upload my resume at [path-to-file]" or use the API directly
   - MCP tool: `onboard_resume(file_path="path/to/resume.docx")`
   - Or API: `POST http://localhost:8055/api/onboard/upload` with file
   - Watch the pipeline: parse → extract career data → create template → create recipe → verify
   - Check the dashboard — career history, bullets, skills should now be populated

8. **Generate a Test Resume**
   - In Claude Code: "Generate a resume using my uploaded data"
   - MCP tool: `generate_resume(recipe_id=<id>)` — use the recipe ID from the upload report
   - Output: .docx file you can open in Word
   - Compare to your original — the match score tells you how close the reconstruction is

9. **Next Steps**
   - Customize your voice rules (Settings page or via MCP)
   - Connect Gmail for email scanning (link to integration guide — deferred)
   - Search for jobs with Indeed MCP (link to workflow guide — deferred)
   - Tailor resumes for specific roles (gap analysis → recipe customization)
   - Track applications in the dashboard

10. **Tips for Other AI Agents**
    - Any MCP-compatible agent can connect via SSE at `http://localhost:8056/sse`
    - Gemini CLI: configure in `.gemini/settings.json` MCP section
    - Cursor/Windsurf: add MCP server in settings
    - The platform is agent-agnostic — the 42 tools work the same regardless of which AI calls them

### 3. API Reference (`code/docs/API_REFERENCE.md`)

Generated from actual route files. For each endpoint:
- Method + Path
- Description
- Request params/body (with types)
- Response shape (with example JSON)
- Notes (auth, pagination, etc.)

Organized by section:
- Health & Settings
- Career Data (career_history, bullets, skills, summary_variants)
- Resume Management (templates, recipes, header, education, certifications, generation)
- Job Search (saved_jobs, gap_analyses)
- Applications & Pipeline (applications, status_history, materials, follow_ups, stale)
- Interviews (interviews, prep, debriefs)
- Networking (contacts, outreach, referrals, companies)
- Content & Analytics (content_sections, voice_rules, salary, emails, activity, analytics)
- Onboarding (upload endpoint)

### 4. MCP Tool Reference (`code/docs/MCP_REFERENCE.md`)

All 42 tools documented. For each:
- Tool name
- Description
- Parameters (name, type, required/optional, description)
- Return type
- Example usage

Organized by category:
- Career & Knowledge Base (search_bullets, get_career_history, get_skills, get_summary_variant, get_candidate_profile)
- Resume Generation (get_resume_data, generate_resume, list_recipes, get_recipe, create_recipe, update_recipe)
- Job Search & Analysis (match_jd, get_gap_analysis, save_gap_analysis, save_job, list_saved_jobs, update_saved_job)
- Applications & Pipeline (search_applications, add_application, update_application, log_follow_up, get_stale_applications)
- Interviews (save_interview_prep, save_interview_debrief)
- Networking (search_contacts, network_check, search_companies, get_company_dossier)
- Content & Voice (get_voice_rules, check_voice, get_salary_data, get_rejection_analysis, search_emails, get_analytics)
- Document Utils (mcp_read_docx, mcp_read_pdf, mcp_edit_docx, mcp_docx_to_pdf, mcp_templatize_resume, mcp_compare_docs)
- Onboarding (onboard_resume)
- Profile (update_header)

### 5. Troubleshooting Guide (`code/docs/TROUBLESHOOTING.md`)

Common issues organized by symptom:
- **Docker won't start** — WSL2, Hyper-V, disk space
- **Containers not healthy** — port conflicts (5555, 8055, 8056, 5175), DB connection
- **MCP tools not showing** — session restart needed, SSE endpoint check, .mcp.json validation
- **Upload fails** — file format, file size, parser errors
- **Resume generation looks wrong** — template mismatch, recipe validation
- **Frontend won't load** — port 5175 in use, CORS, proxy config
- **Windows-specific** — path separators, line endings, WSL2 memory
- **Mac caveat** — untested, known potential issues (Docker networking, libreoffice for PDF conversion)

### 6. CLAUDE.md Template (`code/CLAUDE.md`)

This is NOT just documentation — it's **operational instructions** that make Claude Code (or any AI agent) immediately functional as a job search assistant when opened in the project directory. Same concept as Stephen's CLAUDE.md, but generic for any user.

**Sections:**

- **What This Is** — one-liner: "You are a reverse recruiting assistant. Here's your toolkit."
- **Docker Startup Check** — same pattern as Stephen's: check containers, start if needed
- **MCP Tool Routing** — "User says X → use tool Y" table covering all workflows:
  - Resume upload/parse → onboard_resume
  - Generate resume → get_recipe + generate_resume pipeline
  - Search for jobs → match_jd, save_job
  - Gap analysis → match_jd, save_gap_analysis
  - Track applications → search_applications, add_application, update_application
  - Company research → search_companies, get_company_dossier
  - Interview prep → save_interview_prep, save_interview_debrief
  - Networking → search_contacts, network_check
  - Voice/style check → get_voice_rules, check_voice
  - Email scanning → search_emails
  - Analytics → get_analytics
- **Voice Rules** — always enforce: pull from DB via get_voice_rules, run check_voice before delivering text
- **Resume Integrity Rules** — metrics required, STAR format, pull from DB never invent
- **Document Operations** — use MCP tools for .docx/.pdf, save to Output/
  - Read documents → mcp_read_docx, mcp_read_pdf
  - Edit documents → mcp_edit_docx
  - Convert to PDF → mcp_docx_to_pdf
  - Compare documents → mcp_compare_docs
  - Create template → mcp_templatize_resume
- **Direct DB Access** — psql connection string for advanced users
- **Skill Triggers** — if user says "find jobs" → job search workflow, etc.
- **Customization Notes** — "Edit this file to match your preferences, add your own voice rules, etc."

Does NOT include: Stephen's personal data, campaign sections (S1-S10), session memory, personal preferences, ContextStream config, RTK config.

---

## Files to Create

| File | Source |
|------|--------|
| `code/README.md` | Written from scratch |
| `code/docs/SETUP.md` | Written from scratch |
| `code/docs/API_REFERENCE.md` | Generated from route files + manual examples |
| `code/docs/MCP_REFERENCE.md` | Generated from mcp_server.py tool decorators |
| `code/docs/TROUBLESHOOTING.md` | Written from experience |
| `code/CLAUDE.md` | Operational AI agent instructions (ships ready-to-use, not as .template) |
| `code/.mcp.json.example` | New — example MCP config for Claude Code |
| `code/.env.example` | New — example environment variables |

## Files to Modify

| File | Change |
|------|--------|
| `recs/TODO.md` | Add living walkthrough TODO + deferred frontend guide |
| `CLAUDE.md` (project root) | Add note about creating walkthroughs as features are built |
| `code/docs/reqs/0_APPLICATION_REQUIREMENTS.md` | Check off 13.7 and 13.8 items |

---

## Out of Scope (Deferred)

- Frontend user guide/FAQ (built into the app) — separate Phase
- Gmail OAuth setup guide — write when email workflow is polished
- Indeed MCP setup guide — write when job search workflow is polished
- Video walkthroughs
- Multi-language docs
