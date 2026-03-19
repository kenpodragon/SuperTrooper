# Reverse Recruiting Platform — Application Requirements

The application platform that powers job search, resume management, gap analysis, application tracking, interview prep, and networking. Generic (any user). Built on Flask + PostgreSQL + pgvector + Docker + MCP.

**Built FOR AI, not WITH AI.** The platform is a data + services layer. AI (Claude via MCP, or any other LLM) does the intelligent work — generation, analysis, tailoring. The frontend is for humans to see, manage, and interact with their data. The backend stores, serves, and organizes. No AI/ML components baked in.

Component docs in this folder break out detailed requirements as needed: `{section}_{COMPONENT}.md`, `{section}_{COMPONENT}_DESIGN.md`, `{section}_{COMPONENT}_SCHEMA.md`.

---

## 1. Infrastructure & Database
**Schema:** [1_DB_SCHEMA.md](1_DB_SCHEMA.md)

### 1.1 PostgreSQL + pgvector
- [x] PostgreSQL 17 + pgvector 0.8.2 in Docker (port 5555, bind mount for persistence)
- [x] 6 SQL migrations (001_initial through 006_resume_recipes) — 20 tables
- [x] 3 analytics views (application_funnel, source_effectiveness, monthly_activity)
- [x] DB dump/restore utility with timestamped backups
- [ ] Activity log / audit trail table (track who changed what, when)
- [ ] Settings / preferences table (per-user: default templates, search prefs, notification settings)

### 1.2 ETL Framework
- [x] Load-order dependency chain (5 phases, 11 scripts)
- [x] Core identity: career_history (19), bullets (232), skills (255), summary_variants (8)
- [x] Pipeline: companies (173), applications (62), contacts (26), interviews (38)
- [x] Content: content_sections (131), voice_rules (173), salary_benchmarks (12), cola_markets (7)
- [x] Emails: 7,215 loaded, documents: 134 indexed, resume_versions: 127
- [ ] Incremental email loader (periodic Gmail scan for new emails)
- [ ] Document re-indexer (update paths for archived files)

### 1.3 Docker & DevOps
- [x] docker-compose: 2 containers (postgres + backend), health checks, depends_on
- [x] Volume mounts for DB persistence
- [x] Environment variables via .env file
- [ ] React frontend container
- [ ] Document storage volume mounts

### 1.4 Code Structure
- [x] db/migrations/, backend/routes/, backend/app.py + mcp_server.py
- [x] Shared db_config.py for connection settings
- [ ] Migrate generic utilities from local_code/ to code/utils/:
  - [ ] read_docx.py — .docx text extraction, search, sections (used by 13.2 resume parsing)
  - [ ] edit_docx.py — find/replace preserving formatting (used by template customization)
  - [ ] read_pdf.py — PDF text extraction, page ranges, search (used by 5.1 JD parsing)
  - [ ] compare_docs.py — paragraph-level document diff (used by 3.6 version control)
  - [ ] docx_to_pdf.py — .docx to .pdf conversion via MS Word COM (used by 3.5, Windows-only)
  - [ ] templatize_resume.py — convert full .docx to placeholder template (used by 13.5 template setup)
  - [ ] generate_resume.py — recipe-based resume generation engine (core of 3.2/3.3)
- [x] Remove superseded scripts from local_code/:
  - [x] create_resume.py (replaced by generate_resume.py recipe system)
  - [x] tracker.py (replaced by DB applications table + CRUD API)
- [ ] local_code/ retains only: Stephen-specific ETL scripts, one-off tailoring scripts, data migration tools

---

## 2. API & MCP Server

### 2.1 Flask REST API (port 8055)
- [x] CRUD endpoints for all core tables
- [x] Search endpoints with filtering
- [x] Analytics endpoints (funnel, monthly, sources)
- [x] Content endpoints (content_sections, voice_rules, salary_benchmarks, cola_markets)
- [x] Gap analysis: POST /api/gap-analysis
- [x] Resume generation: POST /api/resume/generate (legacy spec-based)
- [x] Recipe CRUD: GET/POST/PUT/DELETE /api/resume/recipes + clone + validate
- [x] Recipe generation + resolved preview
- [ ] Saved jobs CRUD endpoints (see 4.1)
- [ ] Gap analysis results CRUD (see 5.2)
- [ ] Application status history endpoint (see 6.1)
- [ ] Generated materials tracking endpoints (see 6.1)
- [ ] Follow-up tracking endpoints (see 6.3)
- [ ] Outreach / message tracking endpoints (see 9.1)
- [ ] Cron job management endpoints (see 2.4)
- [ ] Bulk content import endpoints (KB decomposition, see 3.7)

### 2.2 MCP Server (SSE, port 8056) — 24 tools
- [x] Career & KB (4): search_bullets, get_career_history, get_summary_variant, get_skills
- [x] Content & Voice (5): get_candidate_profile, get_voice_rules, check_voice, get_salary_data, get_rejection_analysis
- [x] Pipeline (4): match_jd, search_applications, add_application, update_application
- [x] Companies & Network (4): search_companies, get_company_dossier, search_contacts, network_check
- [x] Email & Analytics (2): search_emails, get_analytics
- [x] Resume (2): generate_resume (spec + recipe paths), get_resume_data
- [x] Recipes (4): list_recipes, get_recipe, create_recipe, update_recipe
- [ ] Profile management: update resume_header, education, certifications via MCP
- [ ] Template management: list/upload templates via MCP
- [ ] Saved jobs: save_job, list_saved_jobs via MCP
- [ ] Gap results: save_gap_analysis, get_gap_analysis via MCP

### 2.3 Auth & Config
- [x] Local-only, no auth (single user)
- [x] Config file for DB connection, API keys, MCP server settings
- [x] Health check endpoint
- [ ] User / candidate table (multi-user support)
- [ ] API key or session-based auth (for open source / multi-user)

### 2.4 Cron Jobs
- [ ] scan_gmail — periodic Gmail scan, auto-categorize, update tracker
- [ ] scan_indeed — run saved searches, auto-score fit
- [ ] check_calendar — pull upcoming interviews, prep materials
- [ ] follow_up_check — flag stale applications (7/14/21 days)
- [ ] refresh_companies — check target companies for new postings
- [ ] Scheduling infrastructure (APScheduler or similar)

---

## 3. Resume Management

### 3.1 Template System
- [x] Placeholder templates (.docx with {{SLOT}} markers)
- [x] template_map JSONB (slot types, formatting rules, original text)
- [x] Bold-label formatting preserved (colon-split, pipe-split)
- [x] Shape preservation, hyperlinks
- [ ] Template management via API/MCP (create, list, activate/deactivate)

### 3.2 Resume Generation
- [x] generate_resume.py: fill placeholders from content_map
- [x] Spec-based generation (legacy inline text specs)
- [x] Header, education, certifications from DB tables
- [x] Recipe-based generation — resolve_recipe() + --recipe-id CLI
- [ ] Bullet reordering to match JD priorities (AI-driven via MCP)
- [ ] Summary rewriting per role (AI-driven via MCP)
- [ ] Keyword adjustment to mirror JD language (AI-driven via MCP)

### 3.3 Resume Generation System (Recipe Engine) — COMPLETE
**Requirements:** [3.3_RESUME_GENERATION.md](3.3_RESUME_GENERATION.md)

#### 3.3.1 Recipe Schema & Resolution
- [x] resume_recipes table (Migration 006)
- [x] career_history.career_links JSONB column
- [x] resolve_recipe() with single value, array, assembly, literal resolution
- [x] Table whitelist security

#### 3.3.2 Recipe CRUD (API + MCP)
- [x] Full Flask CRUD (list, get, create, update, delete, clone, validate, preview)
- [x] Full MCP CRUD (list_recipes, get_recipe, create_recipe, update_recipe)

#### 3.3.3 Recipe-Based Generation
- [x] CLI, MCP, and Flask generation paths
- [x] Output organization by company/role/date

#### 3.3.4 Validation & Testing
- [x] V32 100% match, V31 96.4% match (quote normalization)
- [x] 27 pytest tests, all green
- [x] --validate and --dry-run CLI modes

### 3.4 Resume Variants
- [ ] Variant templates by role type (CTO, VP Eng, Director, AI/ML, PM, Architect)
- [ ] Generate any variant from knowledge base on demand

### 3.5 PDF Generation
- [ ] .docx to .pdf conversion via docx_to_pdf.py (MS Word COM, pixel-perfect, Windows/Mac only)
- [ ] Both formats saved to output folder
- [ ] API endpoint: POST /api/resume/recipes/<id>/generate?format=pdf (generate + convert)
- [ ] Fallback for Linux/Docker: LibreOffice headless conversion (lower fidelity)

### 3.6 Version Control & Diffing
- [ ] Compare any two resume versions via compare_docs.py (paragraph-level diff)
- [ ] Changelog per tailored resume (what slots changed from base recipe and why)

### 3.7 Resume Data Management (Backend)
- [ ] Full CRUD for bullets (add/edit/delete with validation)
- [ ] Full CRUD for skills, summary_variants
- [ ] Full CRUD for career_history (employer, title, dates, intro_text, career_links)
- [ ] Full CRUD for education, certifications, resume_header
- [ ] Resume upload + parse endpoint: POST .docx/.pdf -> auto-extract career_history + bullets (see 13.2)
- [ ] Bulk text import: POST raw text -> parse into structured bullets
- [ ] Content audit: orphaned bullets not in any recipe, broken recipe references
- [ ] KB export: GET /api/kb/export (JSON/CSV of all bullets + career_history)

---

## 4. Job Search & Discovery

### 4.1 Saved Jobs / Evaluation Queue
- [ ] `saved_jobs` table (url, title, company, source, jd_text, jd_url, fit_score, status: saved/evaluating/applying/passed, notes)
- [ ] CRUD API + MCP tools for saved jobs
- [ ] Browser plugin integration: save job from any job board page (see 14)
- [ ] Transition from saved_job to application when user decides to apply

### 4.2 Multi-Platform Search
- [ ] Indeed search via MCP (already available, needs workflow wrapping)
- [ ] LinkedIn, Dice, ZipRecruiter, Google, HN Who's Hiring, AngelList/Wellfound
- [ ] Browser plugin: capture JD from any job page (see 14)

### 4.3 Search Intelligence
- [ ] Title variation matrix
- [ ] Location variations (radius, remote, international)
- [ ] Industry-specific keyword sets
- [ ] Freshness and salary filtering
- [ ] Cross-platform deduplication
- [ ] Quick fit scoring against candidate profile

### 4.4 Search Scheduling
- [ ] Automated search runs (daily or on-demand)
- [ ] New results only
- [ ] Priority flagging for high-fit matches
- [ ] Weekly summary report
- [ ] Target company alerting

---

## 5. Gap Analysis & Fit Assessment

### 5.1 JD Parsing
- [ ] Accept JD from: pasted text, URL, PDF, Indeed posting, saved_job
- [ ] Structured JD parsing: extract requirements into categories (must-have technical, leadership, experience, education, preferred, industry-specific, cultural)
- [ ] Store parsed JD structure (not just raw text) for querying

### 5.2 Gap Analysis Output & Storage
- [x] match_jd MCP tool (keyword ILIKE matching)
- [ ] `gap_analyses` table (application_id/saved_job_id, jd_parsed, strong_matches, partial_matches, gaps, bonus_value, fit_scores, recommendation, created_at)
- [ ] Persist gap analysis results linked to application or saved job
- [ ] Strong Matches with specific evidence and metrics
- [ ] Partial Matches with bridge/reframe strategy
- [ ] Gaps with mitigation plan
- [ ] Bonus Value (what candidate brings beyond JD)
- [ ] Fit Scorecard (Technical/Leadership/Industry/Culture, X/10)
- [ ] Recommendation: Strong Apply / Apply with Tailoring / Stretch / Pass

### 5.3 Gap-to-Action Pipeline
- [ ] Gap analysis feeds resume tailoring recommendations
- [ ] Identifies which KB bullets to swap in
- [ ] Suggests summary rewording, keywords, cover letter talking points
- [ ] Auto-create tailored recipe from gap analysis (clone base recipe + swap bullets)

---

## 6. Application Tracking & Pipeline

### 6.1 Application Management
- [x] applications table with full lifecycle columns
- [x] CRUD API + MCP tools
- [ ] `application_status_history` table (application_id, old_status, new_status, changed_at, notes) — auto-logged on status change
- [ ] `generated_materials` table (application_id, type: resume/cover_letter/outreach, recipe_id, file_path, generated_at) — track which materials were sent where
- [ ] Link applications to saved_jobs (came from evaluation queue)
- [ ] Link applications to gap_analyses

### 6.2 Email-Based Status Tracking
- [ ] Gmail scan for confirmations, responses, rejections, offers
- [ ] Auto-categorize and populate tracker
- [ ] Flag new/unprocessed emails

### 6.3 Follow-Up Management
- [ ] `follow_ups` table (application_id, attempt_number, date_sent, method: email/linkedin/phone, response_received, notes)
- [ ] Flag stale applications (7/14/21 days with no response)
- [ ] Generate follow-up email drafts (AI-driven via MCP)
- [ ] Auto-mark as ghosted after 3 attempts with no response

### 6.4 Pipeline Reporting
- [x] Analytics views + API endpoints (funnel, sources, monthly)
- [ ] Weekly pipeline summary
- [ ] Conversion funnel visualization
- [ ] Time-in-stage metrics (requires status history)
- [ ] Source effectiveness analysis

---

## 7. Application Materials

### 7.1 Cover Letters
- [ ] Generate from gap analysis (AI-driven via MCP using voice_rules + bullets)
- [ ] Voice-validated (8-point Final Check via check_voice)
- [ ] One page max, .docx + .pdf output
- [ ] Stored in generated_materials linked to application

### 7.2 Outreach Messages
- [ ] Cold and warm outreach templates
- [ ] Follow-up templates
- [ ] Under 150 words, direct, specific
- [ ] Gmail draft creation (never auto-send)
- [ ] Tracked in outreach_messages table (see 9.1)

### 7.3 Thank-You Notes
- [ ] Pull context from Calendar + Gmail threads
- [ ] Reference something specific from interview
- [ ] Under 200 words, create as Gmail draft
- [ ] Tracked in outreach_messages linked to interview

### 7.4 LinkedIn Content
- [ ] Thought leadership post generation (AI-driven)
- [ ] Topic pillars and multiple formats
- [ ] Profile optimization pass

---

## 8. Interview Preparation

### 8.1 STAR Story Bank
- [ ] Map STAR stories to common question categories (bullets already have STAR fields)
- [ ] Multiple stories per category, tagged by role/industry
- [ ] Query interface: "give me stories about leadership" -> matching bullets with STAR data

### 8.2 Company-Specific Prep
- [ ] `interview_prep` table (interview_id, company_dossier, prepared_questions, talking_points, star_stories_selected, notes)
- [ ] Company dossier generation (get_company_dossier MCP tool already exists)
- [ ] Likely questions based on JD + culture
- [ ] 3-5 prepared questions for candidate to ask
- [ ] Recent news talking points
- [ ] Interviewer research when names available

### 8.3 Interview Debrief
- [ ] `interview_debriefs` table (interview_id, went_well, went_poorly, questions_asked, answers_given, next_steps, overall_feeling, lessons_learned)
- [ ] Structured capture after each interview
- [ ] Pattern analysis across debriefs (what topics keep coming up, what answers work)

### 8.4 Negotiation Prep
- [ ] Salary research by role/company/location (salary_benchmarks + cola_markets already in DB)
- [ ] Total comp analysis, counter-offer frameworks
- [ ] "Why I'm worth X" talking points backed by KB metrics

---

## 9. Networking & Contacts

### 9.1 Contact Management
- [x] contacts table + API + MCP tools
- [ ] contacts.company_id FK to companies table (currently VARCHAR, not linked)
- [ ] `outreach_messages` table (contact_id, application_id, channel: email/linkedin/phone, direction: sent/received, subject, body, sent_at, response_received, notes)
- [ ] `referrals` table (contact_id, application_id, referral_date, status, notes) — track "contact A referred me to job B"
- [ ] Follow-up reminders (last_contact + days since)
- [ ] Gmail + LinkedIn correspondence integration
- [ ] Network lookup: "do I know anyone at this company?" (network_check MCP tool exists, needs proper FK)

### 9.2 Targeted Outreach
- [ ] Decision-maker identification at target companies
- [ ] Personalized outreach generation (AI-driven via MCP)
- [ ] LinkedIn connection request messages
- [ ] Browser plugin: view contact info overlay on LinkedIn pages (see 14)

### 9.3 LinkedIn Presence
- [ ] Profile optimization, posting schedule, engagement strategy

### 9.4 Resume/LinkedIn Sync
- [ ] Consistency check on titles, dates, metrics
- [ ] Sync check on any update

---

## 10. Content & Knowledge Base

### 10.1 Knowledge Base System
- [x] career_history, bullets, skills, summary_variants in DB
- [x] content_sections (multi-document store)
- [x] Organized by employer, cross-referenced by competency, tagged
- [ ] KB decomposition: parse content_sections into structured bullets/career_history
- [ ] Resume parser: upload .docx/.pdf -> extract career_history + bullets (API endpoint + frontend)
- [ ] Text parser: paste raw text -> parse into bullets with auto-tagging
- [ ] Alternate phrasings for key achievements
- [ ] Metrics methodology notes (for interview defense)
- [ ] Living updates as new achievements emerge
- [ ] Import/export: export KB as JSON/CSV, import from other sources

### 10.2 Voice System
- [x] voice_rules (173 rules, 8 parts) + check_voice MCP tool
- [x] 8-point Final Check
- [ ] Periodic review for new AI patterns

### 10.3 Candidate Profile System
- [x] content_sections (candidate_profile), salary_benchmarks, cola_markets
- [x] MCP tools: get_candidate_profile, get_salary_data
- [ ] References management (who to use for what role type, last used date)

### 10.4 Company Intelligence
- [x] companies table (173 rows) + MCP tools
- [ ] Research automation (roles, culture, tech stack, news, fit score)
- [ ] Key contact identification per company
- [ ] Engagement status tracking (cold/researched/applied/connected/interviewing)

---

## 11. Frontend

### 11.1 Dashboard
- [ ] Pipeline overview (applications by status, weekly/monthly trends)
- [ ] Source effectiveness chart
- [ ] Upcoming interviews
- [ ] Stale applications needing follow-up
- [ ] Recent activity feed

### 11.2 Application Tracker
- [ ] Table + kanban views, detail view, quick-add
- [ ] Status change with auto-history logging
- [ ] Linked materials (resume, cover letter, gap analysis)

### 11.3 Resume Builder
- [ ] KB bullet browser with search/filter
- [ ] Drag-and-drop bullet selection for recipes
- [ ] JD paste -> gap analysis -> suggested bullets
- [ ] Recipe editor (swap slots, preview, generate)
- [ ] Export to DOCX/PDF

### 11.4 Template Editor
- [ ] Drag-and-drop layout, named slots, formatting rules
- [ ] Save as new template

### 11.5 Job Search & Saved Jobs
- [ ] Saved jobs queue (evaluation pipeline before applying)
- [ ] Multi-platform search interface
- [ ] Job detail view with gap analysis
- [ ] "Apply" flow: gap analysis -> tailor resume -> generate materials -> submit

### 11.6 Networking & Contacts
- [ ] Contact list with relationship strength, last contact
- [ ] Company cross-reference (who do I know there?)
- [ ] Outreach history per contact
- [ ] Referral tracking
- [ ] Follow-up reminders

### 11.7 Interview & Prep
- [ ] Upcoming interviews with prep materials
- [ ] Debrief capture form
- [ ] STAR story browser

### 11.8 Other Views
- [ ] Company research + dossier view
- [ ] Email history viewer
- [ ] Semantic search bar
- [ ] Settings / preferences

---

## 12. Quality & Testing

### 12.1 Output Quality
- [ ] Every generated document passes 8-point Voice Guide Final Check
- [ ] A/B test resume approaches (track which recipe/variant gets callbacks)
- [ ] Capture interview feedback, track rejection patterns

### 12.2 Integration Testing
- [x] pytest with real DB (no mocks) — 27 tests, all green
- [x] Snapshot-based output verification (V32 100%, V31 100%)
- [x] Recipe resolution tests (single, array, assembly, literal, whitelist, security)
- [ ] Tests run as part of Docker rebuild
- [ ] API endpoint tests (recipe CRUD, generation, validation)
- [ ] MCP tool tests

### 12.3 Metrics & Analytics
- [ ] Response rate, interview conversion, offer rate
- [ ] Time to first response, time-in-stage
- [ ] Source and variant effectiveness
- [ ] Which recipes/bullets lead to interviews (A/B tracking)

---

## 13. Onboarding, Open Source & Reusability

### 13.1 User Setup & Candidate Profile
- [ ] User / candidate table (multi-user, not hardcoded to one person)
- [ ] Settings / preferences per user (default templates, search prefs, notification settings)
- [ ] Candidate profile wizard (frontend): name, credentials, location, contact info, elevator pitch
- [ ] Resume header auto-populated from profile
- [ ] Target role preferences (titles, industries, locations, salary range, remote/hybrid/onsite)
- [ ] Deal-breakers and non-negotiables capture

### 13.2 Knowledge Base Population
- [ ] Resume upload + parse: .docx/.pdf -> extract career_history + bullets (auto-detect employers, dates, bullet points)
- [ ] LinkedIn profile import: parse exported CSV -> career_history (titles, dates, companies), connections -> contacts
- [ ] Manual entry UI: add/edit career_history, bullets, skills, summary_variants directly
- [ ] Bulk import from text: paste a resume or work history -> parse into structured data
- [ ] Skills auto-extraction from bullets (detect technologies, frameworks, methodologies mentioned)
- [ ] Deduplication: detect duplicate bullets or career entries during import
- [ ] Existing ETL scripts available as reference implementation (load_knowledge_base.py, etc.)

### 13.3 External Integrations Setup
- [ ] Gmail MCP setup guide: OAuth credentials, scope configuration, Claude Code .mcp.json config
- [ ] Google Calendar MCP setup guide: OAuth credentials, scope configuration
- [ ] LinkedIn data export instructions (request archive, download, where to place files)
- [ ] Indeed MCP setup guide (if applicable to other users)
- [ ] WebSearch/WebFetch MCP configuration
- [ ] Guide: "How to connect your AI agent to this platform via MCP" (SSE endpoint, tool list, auth)

### 13.4 Voice & Style Configuration
- [ ] Voice guide template (default set of anti-AI rules, customizable)
- [ ] "Bring your own voice": upload writing samples -> AI extracts style rules
- [ ] Banned words/constructions editor (frontend)
- [ ] Industry-specific voice presets (tech, finance, healthcare, etc.)

### 13.5 Template Setup
- [ ] Upload your own .docx resume as a template (templatize_resume.py workflow)
- [ ] Template wizard (frontend): upload .docx -> auto-detect sections -> name slots -> save
- [ ] Starter templates provided (generic formats for different role levels)
- [ ] Template marketplace / sharing (future)

### 13.6 Getting Started Flow (End-to-End)
```
1. Docker compose up (platform + DB running)
2. Create candidate profile (name, contact, preferences)
3. Upload resume .docx -> auto-parse into career_history + bullets + skills
4. Review and edit parsed data (fix any parsing errors)
5. Upload resume as template -> templatize -> save to DB
6. Create first recipe from template + parsed data
7. Generate test resume -> compare to original -> iterate
8. (Optional) Connect Gmail MCP for email scanning
9. (Optional) Connect LinkedIn for contact import
10. Start using: search jobs, gap analysis, tailor recipes, generate resumes
```

### 13.7 Documentation
- [ ] Docker one-command setup (`docker compose up`)
- [ ] README with architecture overview, setup instructions, quickstart
- [ ] API reference (all endpoints with request/response examples)
- [ ] MCP tool reference (all tools with parameters and examples)
- [ ] Schema migration guide (how to add tables, run migrations)
- [ ] Contributing guide
- [ ] Troubleshooting guide (common issues: Docker, MCP connection, OAuth)

### 13.8 Claude Code Integration
- [ ] CLAUDE.md template + SKILLS/ for other users
- [ ] Installation guide for Claude Code + MCP setup
- [ ] Example SKILLS files (job-hunter workflow, resume tailoring workflow)
- [ ] Guide: "How to customize CLAUDE.md for your job search"

---

## 14. Browser Plugin

Chrome/Firefox extension that bridges the platform with job boards, LinkedIn, and application forms.

### 14.1 Job Capture
- [ ] "Save Job" button on any job board page (Indeed, LinkedIn, Dice, etc.)
- [ ] Auto-extract: title, company, location, salary, JD text, URL
- [ ] Save to saved_jobs table via API
- [ ] Quick fit score overlay (call gap analysis API)

### 14.2 Networking Overlay
- [ ] On LinkedIn profile pages: show if contact exists in DB, relationship strength, last contact
- [ ] On company pages: show how many contacts you have there, application history
- [ ] "Add to contacts" quick-save from LinkedIn profiles
- [ ] Referral suggestion: "Do you have connections who could refer you?"

### 14.3 Auto-Apply
- [ ] On application forms: auto-fill from candidate profile (name, email, phone, LinkedIn, education, work history)
- [ ] Generate tailored resume for this specific JD (call recipe clone + generate)
- [ ] Generate cover letter (AI-driven via MCP)
- [ ] Fill custom questions from KB/STAR stories
- [ ] One-click application submission tracking (log to applications table)

### 14.4 Context Panel
- [ ] Side panel showing: saved job status, gap analysis summary, generated materials, related contacts
- [ ] Quick actions: run gap analysis, generate resume, draft outreach message
- [ ] Notification badges: stale follow-ups, new email responses, upcoming interviews
