# Reverse Recruiting Platform — Application Requirements

The application platform that powers job search, resume management, gap analysis, application tracking, interview prep, and networking. Generic (any user). Built on Flask + PostgreSQL + pgvector + Docker + MCP.

**Built FOR AI, not WITH AI.** The platform is a data + services layer. AI (Claude via MCP, or any other LLM) does the intelligent work — generation, analysis, tailoring. The frontend is for humans to see, manage, and interact with their data. The backend stores, serves, and organizes. No AI/ML components baked in.

Component docs in this folder break out detailed requirements as needed: `{section}_{COMPONENT}.md`, `{section}_{COMPONENT}_DESIGN.md`, `{section}_{COMPONENT}_SCHEMA.md`.

---

## 1. Infrastructure & Database
**Schema:** Migration files in `code/db/migrations/` | Live reference: `code/db/migrations/DB_DICTIONARY.md`

### 1.1 PostgreSQL + pgvector
- [x] PostgreSQL 17 + pgvector 0.8.2 in Docker (port 5555, bind mount for persistence)
- [x] 7 SQL migrations (001_initial through 007_platform_tables) — 31 tables
- [x] 3 analytics views (application_funnel, source_effectiveness, monthly_activity)
- [x] DB dump/restore utility with timestamped backups
- [x] Activity log / audit trail table — Migration 007 (auto-population TBD)
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
- [x] React frontend container — Docker, port 5175, `serve` static
- [ ] Document storage volume mounts

### 1.4 Code Structure
- [x] db/migrations/, backend/routes/, backend/app.py + mcp_server.py
- [x] Shared db_config.py for connection settings
- [x] Migrate generic utilities from local_code/ to code/utils/:
  - [x] read_docx.py — .docx text extraction, search, sections (used by 13.2 resume parsing)
  - [x] edit_docx.py — find/replace preserving formatting (used by template customization)
  - [x] read_pdf.py — PDF text extraction, page ranges, search (used by 5.1 JD parsing)
  - [x] compare_docs.py — paragraph-level document diff (used by 3.6 version control)
  - [x] docx_to_pdf.py — .docx to .pdf conversion via MS Word COM (used by 3.5, Windows-only)
  - [x] templatize_resume.py — convert full .docx to placeholder template (used by 13.5 template setup)
  - [x] generate_resume.py — recipe-based resume generation engine (core of 3.2/3.3)
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
- [x] Saved jobs CRUD endpoints (see 4.1) — routes/saved_jobs.py
- [x] Gap analysis results CRUD (see 5.2) — routes/gap_analysis.py
- [x] Application status history endpoint (see 6.1) — auto-logged in pipeline.py
- [x] Generated materials tracking endpoints (see 6.1) — pipeline.py
- [x] Follow-up tracking endpoints (see 6.3) — pipeline.py + stale detection
- [x] Outreach / message tracking endpoints (see 9.1) — contacts.py
- [ ] Cron job management endpoints (see 2.4)
- [ ] Bulk content import endpoints (KB decomposition, see 3.7)

### 2.2 MCP Server (SSE, port 8056) — 35 tools
- [x] Career & KB (4): search_bullets, get_career_history, get_summary_variant, get_skills
- [x] Content & Voice (5): get_candidate_profile, get_voice_rules, check_voice, get_salary_data, get_rejection_analysis
- [x] Pipeline (4): match_jd, search_applications, add_application, update_application
- [x] Companies & Network (4): search_companies, get_company_dossier, search_contacts, network_check
- [x] Email & Analytics (2): search_emails, get_analytics
- [x] Resume (2): generate_resume (spec + recipe paths), get_resume_data
- [x] Recipes (4): list_recipes, get_recipe, create_recipe, update_recipe
- [x] Profile management: update_header via MCP
- [ ] Template management: list/upload templates via MCP
- [x] Saved jobs: save_job, list_saved_jobs, update_saved_job via MCP
- [x] Gap results: save_gap_analysis, get_gap_analysis via MCP
- [x] Follow-ups: log_follow_up, get_stale_applications via MCP
- [x] Interview: save_interview_prep, save_interview_debrief via MCP

### 2.3 Auth & Config
- [x] Local-only, no auth (single user)
- [x] Config file for DB connection, API keys, MCP server settings
- [x] Health check endpoint
- [ ] User / candidate table (multi-user support)
- [ ] API key or session-based auth (for open source / multi-user)

### 2.5 AI Routing Pattern
All REST API endpoints that involve inference/analysis MUST follow the AI routing pattern:
1. Endpoint checks if AI provider is available (via Phase D settings + AI provider framework)
2. If AI available → route inference pieces through AI (semantic matching, scoring, analysis)
3. If AI unavailable → fall back to Python rule-based processing
4. Only inference/reasoning uses AI — CRUD, extraction, and deterministic ops stay Python-only

- [ ] Build reusable AI routing utility (`code/backend/ai_providers/router.py`) — check availability, route inference, fallback
- [ ] Retrofit `POST /api/gap-analysis` (search.py) — first implementation of the pattern
- [ ] Retrofit `match_jd` MCP tool — use AI router instead of hardcoded keyword matching
- [ ] Audit + retrofit all existing inference endpoints to follow this pattern
- [ ] Document the pattern in API_REFERENCE.md

### 2.4 Cron Jobs
- [ ] scan_gmail — periodic Gmail scan, auto-categorize, update tracker
- [ ] scan_indeed — run saved searches, auto-score fit
- [ ] check_calendar — pull upcoming interviews, prep materials
- [ ] follow_up_check — flag stale applications (7/14/21 days)
- [ ] refresh_companies — check target companies for new postings
- [ ] social_scan — scan LinkedIn/HN for hidden opportunities (see 4.5)
- [ ] weekly_digest — compile weekly campaign report (see 15.2)
- [ ] aging_sweep — expire/archive stale saved jobs and dead applications (see 6.5)
- [ ] check_job_links — re-check posting URLs, flag closed listings, notify (see 6.6)
- [ ] Scheduling infrastructure (APScheduler or similar)

### 2.6 Notifications & Alerts System
Cross-cutting notification infrastructure used by all modules.
- [ ] Notification store table (type, severity, title, body, link, read/unread, created_at, expires_at)
- [ ] Notification REST endpoints (list, mark read, mark all read, dismiss, preferences)
- [ ] MCP tool: get_notifications, dismiss_notification
- [ ] Notification sources:
  - [ ] New jobs discovered (from search, email, social scan, plugin capture)
  - [ ] Application status changes (response received, interview scheduled, offer, rejection)
  - [ ] Follow-up due / overdue reminders
  - [ ] Stale application warnings
  - [ ] Interview coming up (24h, 1h reminders)
  - [ ] Contact follow-up due (CRM cadence)
  - [ ] Weekly digest ready
  - [ ] New email matched to an application
- [ ] Severity levels: info, action-needed, urgent
- [ ] Browser plugin integration: badge count, toast notifications, popup notification panel
- [ ] Frontend notification center (bell icon, dropdown, notification page)
- [ ] Desktop notification support (browser Notification API via plugin)
- [ ] Notification preferences (per-type enable/disable, quiet hours)

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
- [x] Full CRUD for bullets (add/edit/delete with validation) — career.py
- [x] Full CRUD for skills, summary_variants — career.py
- [x] Full CRUD for career_history (employer, title, dates, intro_text, career_links) — career.py
- [x] Full CRUD for education, certifications, resume_header — resume.py
- [x] Resume upload + parse endpoint: POST /api/onboard/upload .docx/.pdf -> auto-extract career_history + bullets (see 13.2)
- [ ] Bulk text import: POST raw text -> parse into structured bullets
- [ ] Content audit: orphaned bullets not in any recipe, broken recipe references
- [x] KB export: GET /api/kb/export (JSON of all bullets + career_history + skills + summaries)

---

## 4. Job Search & Discovery

### 4.1 Saved Jobs / Evaluation Queue
- [x] `saved_jobs` table (url, title, company, source, jd_text, jd_url, fit_score, status: saved/evaluating/applying/passed, notes) — Migration 007
- [x] CRUD API + MCP tools for saved jobs — routes/saved_jobs.py + 3 MCP tools
- [ ] Browser plugin integration: save job from any job board page (see 14)
- [x] Transition from saved_job to application: POST /api/saved-jobs/<id>/apply
- [ ] **Excitement/priority rating** (1-5 stars or hot/warm/cold) — subjective "how much do I want this" score alongside objective fit_score
- [ ] Auto-detect compensation from JD text (salary range extraction via regex + AI)
- [ ] Salary comparison: extracted salary vs. salary_benchmarks for that role

### 4.2 Multi-Platform Search
- [ ] Indeed search via MCP (already available, needs workflow wrapping)
- [ ] Direct boards: LinkedIn, Dice, ZipRecruiter, Glassdoor, Monster, CareerBuilder, SimplyHired, Wellfound, Otta, Levels.fyi, TheLadders, WeWorkRemotely, FlexJobs, Remotive, USAJobs, GovernmentJobs.com, Welcome to the Jungle, The Muse, Built In, Handshake, Idealist, HN Who's Hiring
- [ ] Aggregators: Google for Jobs, Jooble, Adzuna, JobisJob, Working Nomads, Remote.co
- [ ] Browser plugin: capture JD from any job board page (see 14)

#### 4.2.1 API Integrations (free, programmatic search)
- [ ] USAJobs API — REST, free key (email registration), JSON, well-documented (`developer.usajobs.gov`)
- [ ] Adzuna API — REST, free key, aggregator covering 16 countries, 250 req/day free tier (`developer.adzuna.com`)
- [ ] The Muse API — REST, no key needed, filters by location/company/category (`themuse.com/developers/api/v2`)
- [ ] Remotive API — REST, no key needed, remote-focused (`remotive.com/api/remote-jobs`)
- [ ] Jooble API — POST-based, free key, aggregator (`jooble.org/api/about`)

#### 4.2.2 RSS Feed Integrations (lightweight polling)
- [ ] WeWorkRemotely RSS (`weworkremotely.com/remote-jobs.rss`)
- [ ] Working Nomads RSS (`workingnomads.com/jobs.rss`)
- [ ] USAJobs RSS (search results exportable as RSS)

#### 4.2.3 No API Available (browser plugin only)
LinkedIn, Dice, ZipRecruiter, Glassdoor, Monster, CareerBuilder, SimplyHired, Wellfound, Otta, Levels.fyi, TheLadders, FlexJobs, Built In, Handshake, Idealist, Welcome to the Jungle, GovernmentJobs.com, Google for Jobs, Remote.co

### 4.3 Search Intelligence
- [ ] Title variation matrix
- [ ] Location variations (radius, remote, international)
- [ ] Industry-specific keyword sets
- [ ] Freshness and salary filtering
- [ ] Cross-platform deduplication
- [ ] Quick fit scoring against candidate profile
- [ ] Skill demand analysis (which skills appear most across matching JDs)

### 4.4 Search Scheduling
- [ ] Automated search runs (daily or on-demand)
- [ ] New results only
- [ ] Priority flagging for high-fit matches
- [ ] Weekly summary report
- [ ] Target company alerting

### 4.5 Hidden Opportunity Mining
Social and non-traditional job discovery beyond job boards.
- [ ] LinkedIn post scanning — detect "HIRING", "looking for", "we're growing", "join my team" patterns
- [ ] LinkedIn boolean search strategies (configurable search templates)
- [ ] HN Who's Hiring monthly thread parsing (auto-detect new threads, extract posts)
- [ ] Twitter/X hiring post detection
- [ ] Company careers page monitoring (periodic crawl of target company career pages for new postings)
- [ ] Recruiter post detection (identify recruiters posting about open roles)
- [ ] All discovered opportunities → Fresh Jobs Inbox (see 4.6)
- [ ] Source tagging (where was this found: LinkedIn post, HN, careers page, email, etc.)

### 4.6 Fresh Jobs Inbox / Triage Queue
Central inbox for ALL newly discovered jobs before they're evaluated. Distinct from saved_jobs (which are already triaged).
- [ ] `fresh_jobs` table (source, source_url, title, company, location, salary_range, jd_snippet, discovered_at, status: new/reviewed/saved/passed/expired, auto_score, source_type)
- [ ] Sources feeding the inbox:
  - [ ] API search results (Indeed, Adzuna, USAJobs, etc.)
  - [ ] Browser plugin captures
  - [ ] Email-parsed recruiter messages (see 6.2)
  - [ ] Social/hidden opportunity mining (see 4.5)
  - [ ] RSS feed polling (see 4.2.2)
  - [ ] Manual add (paste a URL or JD)
- [ ] Auto-scoring: quick fit score on arrival (keyword match against profile)
- [ ] Deduplication: cross-source dedup (same job from Indeed + LinkedIn = one entry)
- [ ] Triage workflow: review → save (moves to saved_jobs) / pass / snooze / batch-queue
- [ ] Batch operations: select multiple → batch save, batch pass, batch gap analysis
- [ ] Notification on new high-fit jobs (see 2.6)
- [ ] REST API: CRUD + triage actions + batch endpoints
- [ ] MCP tools: get_fresh_jobs, triage_job, batch_triage

---

## 5. Gap Analysis & Fit Assessment

### 5.1 JD Parsing
- [ ] Accept JD from: pasted text, URL, PDF, Indeed posting, saved_job
- [ ] Structured JD parsing: extract requirements into categories (must-have technical, leadership, experience, education, preferred, industry-specific, cultural)
- [ ] Store parsed JD structure (not just raw text) for querying

### 5.2 Gap Analysis Output & Storage
- [x] match_jd MCP tool (keyword ILIKE matching)
- [x] `gap_analyses` table (application_id/saved_job_id, jd_parsed, strong_matches, partial_matches, gaps, bonus_value, fit_scores, recommendation, created_at) — Migration 007
- [x] Persist gap analysis results linked to application or saved job — routes/gap_analysis.py + 2 MCP tools
- [ ] Strong Matches with specific evidence and metrics
- [ ] Partial Matches with bridge/reframe strategy
- [ ] Gaps with mitigation plan
- [ ] Bonus Value (what candidate brings beyond JD)
- [ ] Fit Scorecard (Technical/Leadership/Industry/Culture, X/10)
- [ ] Recommendation: Strong Apply / Apply with Tailoring / Stretch / Pass

### 5.3 ATS Optimization & Reverse-Engineering
Understanding how specific ATS platforms parse, score, and filter resumes.
- [ ] ATS format rules per platform (Workday, Greenhouse, Lever, iCIMS, Taleo, BambooHR)
  - Accepted file formats, parsing quirks, section header expectations
  - Keyword matching algorithms (exact vs. semantic vs. skills taxonomy)
  - Known parsing failures (tables, columns, headers/footers, images)
- [ ] ATS-safe resume validation: check generated resume against ATS parsing rules
- [ ] Keyword density analysis: compare resume keyword frequency to JD requirements
- [ ] Section ordering recommendations per ATS platform
- [ ] "ATS score" alongside gap analysis fit score (structural compatibility, not just content)
- [ ] ATS-specific template variants (some ATS parse single-column better, etc.)

### 5.4 Gap-to-Action Pipeline
- [ ] Gap analysis feeds resume tailoring recommendations
- [ ] Identifies which KB bullets to swap in
- [ ] Suggests summary rewording, keywords, cover letter talking points
- [ ] Auto-create tailored recipe from gap analysis (clone base recipe + swap bullets)

---

## 6. Application Tracking & Pipeline

### 6.1 Application Management
- [x] applications table with full lifecycle columns
- [x] CRUD API + MCP tools
- [x] `application_status_history` table (application_id, old_status, new_status, changed_at, notes) — Migration 007 (auto-logging TBD)
- [x] `generated_materials` table (application_id, type: resume/cover_letter/outreach, recipe_id, file_path, generated_at) — Migration 007 (CRUD TBD)
- [x] Link applications to saved_jobs (came from evaluation queue) — applications.saved_job_id FK
- [x] Link applications to gap_analyses — applications.gap_analysis_id FK

### 6.2 Email-Based Status Tracking & Intelligence
- [ ] Gmail scan for confirmations, responses, rejections, offers
- [ ] Auto-categorize and populate tracker
- [ ] Flag new/unprocessed emails
- [ ] Inbound recruiter emails → auto-create fresh job entry (see 4.6)
- [ ] Auto-detect status signals:
  - [ ] "Thank you for applying" → confirmed
  - [ ] "We'd like to schedule" / calendar invite → interview_scheduled
  - [ ] "We regret to inform" / "moved forward with other candidates" → rejected
  - [ ] "We're pleased to offer" → offer
  - [ ] No response after configurable timeout (default 21 days) → ghosted
- [ ] Confidence scoring on auto-classification (flag low-confidence for manual review)
- [ ] Alert on ANY new email matched to an existing application (see 2.6)
- [ ] Link parsed emails to application records automatically (match by company + role)
- [ ] Recruiter contact extraction → contacts table

### 6.3 Follow-Up Management
- [x] `follow_ups` table (application_id, attempt_number, date_sent, method: email/linkedin/phone, response_received, notes) — Migration 007
- [x] Flag stale applications — GET /api/applications/stale + get_stale_applications MCP
- [ ] Generate follow-up email drafts (AI-driven via MCP)
- [ ] Auto-mark as ghosted after 3 attempts with no response

### 6.4 Pipeline Reporting
- [x] Analytics views + API endpoints (funnel, sources, monthly)
- [ ] Weekly pipeline summary
- [ ] Conversion funnel visualization
- [ ] Time-in-stage metrics (requires status history)
- [ ] Source effectiveness analysis
- [ ] Pipeline velocity (average days per stage)
- [ ] Win/loss analysis (what do successful applications have in common?)
- [ ] Activity recommendations ("you haven't applied in 5 days", "3 follow-ups overdue")
- [ ] Best performing resume variant tracking (which recipe/variant gets callbacks)
- [ ] Optimal application timing patterns (day of week, time of day correlations)

### 6.5 Application Aging & Expiry
Configurable lifecycle management for applications and saved jobs.
- [ ] Freshness thresholds (configurable per status: e.g., "applied" goes stale at 14d, "interviewing" at 7d)
- [ ] Visual decay indicators: fresh (green) → aging (yellow) → stale (red) → expired (grey)
- [ ] Auto-archive: applications with no activity past configurable threshold (default 60d)
- [ ] Auto-mark ghosted: no email response + no status change after N days post-apply
- [ ] Saved jobs expiry: job listings older than 30d auto-flagged (posting likely closed)
- [ ] "Show expired" toggle in all list views
- [ ] Aging settings configurable per user (see 1.1 settings table)

### 6.6 Job Posting Link Monitoring
Periodic re-check of job posting URLs to detect closed/removed listings.
- [ ] Cron job: `check_job_links` — visit saved_job and application URLs, check if posting is still live
- [ ] Detection methods:
  - [ ] HTTP status (404, 410 = removed)
  - [ ] Page content signals ("this job is no longer available", "position has been filled", redirect to search page)
  - [ ] ATS-specific patterns per siteConfig (Greenhouse "no longer accepting", Lever "this position has been closed", etc.)
- [ ] When posting is closed:
  - [ ] Flag `posting_closed = true` + `posting_closed_at` timestamp on the application/saved_job record
  - [ ] **Do NOT auto-close the application** — posting closed ≠ role filled (candidate may still be in process)
  - [ ] Notify candidate: "Job posting for {role} at {company} appears to be closed" (see 2.6)
- [ ] Auto-close rule (configurable): if posting closed AND no activity for N days (default 30d, configurable in settings), THEN mark application as closed/expired
  - [ ] Different thresholds by application status: "interviewing" gets longer grace period than "applied"
- [ ] Dashboard indicator: posting status icon (live / closed / unknown) alongside application status
- [ ] Bulk check: run across all active applications + saved jobs on schedule (daily or weekly, configurable)
- [ ] Rate limiting: respect robots.txt, stagger requests, don't hammer job boards

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
See **9.4 LinkedIn Networking Magnet** for the full content engine (post generation, voice guide, theme pillars, engagement analytics). This section covers the materials-generation interface only.
- [ ] Generate LinkedIn post from: gap analysis topic, interview insight, industry news, career reflection
- [ ] LinkedIn voice guide validation (separate from resume voice rules, see 9.4.6)
- [ ] Draft storage and scheduling (see 9.4.1)

---

## 8. Interview Preparation

### 8.1 STAR Story Bank
- [ ] Map STAR stories to common question categories (bullets already have STAR fields)
- [ ] Multiple stories per category, tagged by role/industry
- [ ] Query interface: "give me stories about leadership" -> matching bullets with STAR data

### 8.2 Company-Specific Prep
- [x] `interview_prep` table (interview_id, company_dossier, prepared_questions, talking_points, star_stories_selected, notes) — Migration 007
- [ ] Company dossier generation (get_company_dossier MCP tool already exists)
- [ ] Likely questions based on JD + culture
- [ ] 3-5 prepared questions for candidate to ask
- [ ] Recent news talking points
- [ ] Interviewer research when names available

### 8.3 Interview Debrief
- [x] `interview_debriefs` table (interview_id, went_well, went_poorly, questions_asked, answers_given, next_steps, overall_feeling, lessons_learned) — Migration 007
- [ ] Structured capture after each interview
- [ ] Pattern analysis across debriefs (what topics keep coming up, what answers work)

### 8.5 AI Mock Interviews
Practice interviews with AI-generated questions and real-time feedback.
- [ ] Generate interview questions from JD + company dossier + common patterns for role level
- [ ] Question categories: behavioral (STAR), technical, situational, culture fit, leadership
- [ ] Practice mode: AI asks question → candidate responds (text or voice) → AI evaluates against STAR stories + KB
- [ ] Feedback per answer: strength of evidence, metric specificity, voice rule compliance, length
- [ ] Suggested improved answer using actual KB bullets and STAR data
- [ ] Mock interview report: areas of strength, areas to improve, suggested prep focus
- [ ] Company-specific question prediction (based on Glassdoor interview data, dossier, role type)
- [ ] Panel simulation: different interviewer personas (HR, technical, hiring manager, executive)

### 8.4 Negotiation Prep
- [ ] Salary research by role/company/location (salary_benchmarks + cola_markets already in DB)
- [ ] Total comp analysis, counter-offer frameworks
- [ ] "Why I'm worth X" talking points backed by KB metrics

---

## 9. Networking & Contacts

### 9.1 Contact Management (CRM)
- [x] contacts table + API + MCP tools
- [x] contacts.company_id FK to companies table — Migration 007
- [x] `outreach_messages` table (contact_id, application_id, channel: email/linkedin/phone, direction: sent/received, subject, body, sent_at, response_received, notes) — Migration 007
- [x] `referrals` table (contact_id, application_id, referral_date, status, notes) — Migration 007
- [ ] Follow-up reminders (last_contact + days since)
- [ ] Gmail + LinkedIn correspondence integration
- [ ] Network lookup: "do I know anyone at this company?" (network_check MCP tool exists, needs proper FK)

#### 9.1.1 Relationship Pipeline Stages
Every contact has a clear "where are we" status, distinct from the application pipeline.
- [ ] Pipeline stages: **Identified** → **Connected** → **Engaged** → **Warm** → **Advocate** → **Dormant**
  - Identified: found them, no contact yet
  - Connected: LinkedIn accepted or email exchanged
  - Engaged: had a real conversation (informational, coffee, call)
  - Warm: mutual value established, they'd take your call
  - Advocate: actively helping (referring, introducing, recommending)
  - Dormant: was warm, gone cold (needs reactivation)
- [ ] Contacts can be in relationship pipeline AND linked to application pipeline simultaneously
- [ ] Stage history tracking (when did they move, what triggered it)
- [ ] Kanban view for relationship pipeline (frontend, see 11.6)

#### 9.1.2 Relationship Health & Scoring
- [ ] **Relationship Health Score** (0-100) computed from:
  - Recency of last touchpoint (decays over time)
  - Frequency of interactions (emails, meetings, LinkedIn engagement)
  - Reciprocity (are they responding? initiating?)
  - Depth (surface networking vs. substantive conversation)
  - Relevance to current targets (at a target company? decision-making role?)
- [ ] Auto-decay: relationships cool over time without touchpoints
- [ ] Staleness alerts when relationships drop below threshold (see 2.6)
- [ ] Relationship type tags: recruiter, hiring manager, peer, mentor, former colleague, referral source
- [ ] Seniority/influence level tracking

#### 9.1.3 Contact Enrichment
- [ ] Auto-enrich on contact creation from LinkedIn profile URL: current title, company, tenure, location
- [ ] Company enrichment link: auto-associate contact's company with companies table
- [ ] Periodic re-enrichment to catch job changes
- [ ] **Job change alerts**: when a contact moves to a target company → flag as warm intro opportunity + notify (see 2.6)
- [ ] Contact notes and context (how you met, shared interests, conversation topics to reference)

#### 9.1.4 Contact Timeline & Activity
- [ ] Unified chronological view of ALL interactions per contact (emails, messages, meetings, referrals, LinkedIn)
- [ ] Auto-log from Gmail integration (sent/received emails tagged to contact)
- [ ] Manual touchpoint logging: coffee meetings, phone calls, LinkedIn messages, events, referral requests
- [ ] Touchpoint types: Email, Call, Meeting, LinkedIn Message, LinkedIn Engagement, Event/Conference, Referral Request, Intro Made, Thank You
- [ ] Thread association: link email threads to contacts AND applications

#### 9.1.5 Touchpoint Cadence & Follow-up Sequences
- [ ] Configurable cadence per relationship stage:
  - New connection: touch within 48 hours
  - Active networking: every 2-3 weeks
  - Warm relationship maintenance: monthly
  - Dormant reactivation: quarterly check-in
- [ ] Follow-up sequences: multi-step drip templates by scenario:
  - Post-application follow-up (Day 3, Day 10, Day 21)
  - Post-informational-interview nurture (Day 1 thank you, Day 14 article share, Day 30 check-in)
  - Recruiter relationship maintenance (monthly value-add touches)
  - Warm intro request sequence (ask, follow-up, thank regardless)
  - Conference/event follow-up (Day 1, Day 7, Day 30)
  - Post-rejection nurture (stay connected, they may have other leads)
- [ ] Auto-pause sequence on reply (don't send follow-up #2 if they responded)
- [ ] AI draft generation using voice rules + contact context (not generic templates)
- [ ] Task creation for non-email steps (call them, engage on LinkedIn, send article)
- [ ] Overdue follow-up alerts (see 2.6 notifications)

#### 9.1.6 Task & Reminder System
- [ ] Auto-generated tasks from:
  - Sequence steps ("call John on Thursday")
  - Staleness alerts ("haven't talked to Sarah in 30 days")
  - Application milestones ("follow up 1 week after applying")
  - Interview prep ("research company 2 days before interview")
- [ ] Manual tasks with due dates, linked to contacts and/or applications
- [ ] **Daily networking digest**: "Today: 3 follow-ups due, 2 thank-you notes, 1 intro to request"
- [ ] Task completion logging (feeds into touchpoint history)
- [ ] Task queue view in frontend (see 11.6)

#### 9.1.7 Warm Intro & Path Finding
- [ ] **Path finder**: given a target person/company, show:
  - Direct connections who work there
  - Second-degree connections (who can intro you)
  - Alumni connections (same school, same previous employer)
  - Shared group/community membership
- [ ] Intro request workflow: identify connector → draft warm intro request → track outcome
- [ ] Company contact map: all contacts at Company X, their roles, relationship stages
- [ ] Company-level relationship score: aggregate of individual contact scores
- [ ] "Warm path" scoring: rank target companies by strength of existing connections
- [ ] Job change alerts feeding into path finding (contact moved to target company → new warm path)

### 9.2 Targeted Outreach
- [ ] Decision-maker identification at target companies
- [ ] Personalized outreach generation (AI-driven via MCP, using voice rules + contact context)
- [ ] LinkedIn connection request messages
- [ ] Browser plugin: view contact info overlay on LinkedIn pages (see 14)
- [ ] Batch outreach: draft messages for multiple contacts at once
- [ ] A/B testing outreach templates (track which message styles get responses)
- [ ] Response tracking: auto-detect replies in Gmail, update outreach record
- [ ] Outreach analytics: response rate by channel, message type, relationship warmth
- [ ] Email open tracking (pixel-based — know when they read your email)
- [ ] Link click tracking (know when they viewed your resume/portfolio link)
- [ ] Reply detection → auto-update touchpoint log and relationship score
- [ ] Best day/time for outreach analysis

### 9.3 LinkedIn Profile Optimization
Full profile management — headline, about, experience, skills, featured — all aligned to target roles and kept current as strategy evolves.

#### 9.3.1 Headline & About Section
- [ ] **Headline generator**: multiple options optimized for recruiter search visibility
  - [ ] Keyword-stuffing avoidance — reads naturally but contains target role keywords
  - [ ] Multiple variants: current-role focused, aspiration-focused, expertise-focused
  - [ ] Refresh recommendations when target roles change
- [ ] **About section optimization**:
  - [ ] Rewrite using LinkedIn voice guide + candidate profile positioning
  - [ ] Keyword density check: does About contain the keywords hiring managers search for
  - [ ] Structure: hook → value proposition → key achievements → what you're looking for → CTA
  - [ ] Auto-update suggestions as target role themes evolve (see 9.4.4 theme pillars)
- [ ] **LinkedIn match score**: how well does full profile match target JDs (à la Jobscan)

#### 9.3.2 Experience Section
- [ ] **Experience bullet optimization**: review each role's bullets against target JDs
  - [ ] Rewrite bullets to emphasize skills/outcomes relevant to target roles
  - [ ] Ensure metrics and outcomes in every bullet (same standards as resume)
  - [ ] Keyword alignment: mirror the language recruiters search for
  - [ ] Order bullets by relevance to target roles (most relevant first)
- [ ] **Title optimization**: LinkedIn titles don't have to match exact HR titles
  - [ ] Suggest title variants that are more searchable (e.g., "Sr. Director, Engineering" → "VP Engineering | Director of Engineering")
  - [ ] Flag titles that don't match common recruiter search terms
- [ ] **LinkedIn-to-resume sync check**: consistency of titles, dates, metrics between LinkedIn and resume
  - [ ] Bi-directional: flag discrepancies in either direction
  - [ ] Sync check on any resume update

#### 9.3.3 Skills Management
LinkedIn allows up to 100 skills. Most profiles are cluttered with outdated or irrelevant skills that dilute signal.
- [ ] **Skills audit**: compare current LinkedIn skills against target role JD requirements
  - [ ] Categorize: high-relevance (keep/add), low-relevance (demote/remove), outdated (remove), missing (add)
  - [ ] Cross-reference with platform skills table (255 skills in DB) for canonical naming
- [ ] **Skills-to-role targeting**: given target roles, recommend top 50 skills to feature
  - [ ] Pull most-requested skills from saved JDs and gap analyses
  - [ ] Rank by: frequency in target JDs × your proficiency level
  - [ ] Flag outdated skills that signal wrong era (e.g., "COBOL" when targeting modern cloud roles — unless strategically relevant)
  - [ ] Flag fluff skills that add noise ("Microsoft Office", "Communication" — unless entry-level)
- [ ] **Skills-to-experience mapping**: ensure skills are endorsed on the right roles
  - [ ] LinkedIn lets you pin skills to specific experience entries
  - [ ] Recommend which skills to associate with which roles for maximum relevance
  - [ ] Flag skills not attached to any experience (floating/unverified)
- [ ] **Skills refresh cadence**: quarterly review aligned with target role evolution
  - [ ] As target roles shift (e.g., from VP Eng to CTO), skills recommendations update
  - [ ] Alert when target JDs consistently ask for a skill you don't have listed
- [ ] **Endorsement strategy**: identify which skills need more endorsements
  - [ ] Flag high-priority skills with low endorsement counts
  - [ ] Suggest contacts to request endorsements from (based on relationship strength + shared work history)

#### 9.3.4 Featured Section & Extras
- [ ] **Featured section strategy**: what to showcase (posts, articles, links, media)
  - [ ] Recommend top-performing LinkedIn posts to pin (see 9.4.3 engagement data)
  - [ ] Portfolio links, project showcases, speaking engagements
  - [ ] Rotate featured items to keep profile fresh
- [ ] **Recommendations strategy**: who to ask, when, for which skills/roles
- [ ] **Certifications & Education**: ensure all relevant certs are listed and current
  - [ ] Flag expired certifications
  - [ ] Suggest certifications from JD analysis (see 16.4 certification ROI)
- [ ] **Custom URL**: ensure vanity URL is claimed and professional

#### 9.3.5 Recruiter Search Optimization
- [ ] **Recruiter email finder**: given a company + role, find likely recruiter/hiring manager contacts
  - [ ] Search LinkedIn for recruiters at target company
  - [ ] Email pattern detection (firstname.lastname@company.com patterns)
  - [ ] Auto-create contact record with enrichment
- [ ] **Search appearance optimization**: how often profile appears in recruiter searches
  - [ ] Keyword gap analysis: what terms are recruiters searching that your profile doesn't contain
  - [ ] Location/industry/open-to-work settings optimization
  - [ ] "Open to Work" visibility strategy (visible to recruiters only vs. public)

### 9.4 LinkedIn Networking Magnet (Content & Brand Engine)
Full content marketing system for building niche audience, establishing thought leadership, and attracting opportunities through LinkedIn presence.

#### 9.4.1 Post Storage & History
- [ ] `linkedin_posts` table (content, post_type: text/article/carousel/poll/video, posted_at, url, status: draft/scheduled/posted, topic_tags, theme_pillar, word_count, has_media, hook_text)
- [ ] Import existing post history (bulk import from LinkedIn data export or manual paste)
- [ ] Learn-as-you-go mode: add posts going forward, system builds understanding over time
- [ ] Draft storage: work-in-progress posts before publishing
- [ ] Post versioning: track edits and A/B variants

#### 9.4.2 Engagement Tracking
- [ ] `linkedin_post_engagement` table (post_id, impressions, reactions, comments, reposts, saves, profile_views_after, follower_delta, snapshot_at)
- [ ] Periodic engagement snapshot (manual entry or browser plugin scrape from LinkedIn analytics)
- [ ] Engagement rate calculation: (reactions + comments + reposts) / impressions
- [ ] Track engagement over time per post (Day 1, Day 3, Day 7 snapshots — LinkedIn posts have a decay curve)
- [ ] Follower growth tracking (total followers over time, correlated with posting activity)

#### 9.4.3 Content Performance Analytics
- [ ] **Pattern detection** — what makes posts perform:
  - Content length sweet spots (which word count ranges get most engagement)
  - Post type effectiveness (text vs. carousel vs. poll vs. article)
  - Hook analysis: which opening lines drive engagement (first 2 lines before "see more")
  - Topic/theme performance: which pillars resonate most
  - Posting time analysis: best day of week, time of day
  - Media impact: posts with images/video vs. text-only
  - Hashtag effectiveness
  - CTA effectiveness (question prompts, "agree?" etc.)
- [ ] **Recommendations engine:**
  - "Your posts about [topic] get 3x more engagement than [other topic]"
  - "Posts under 150 words outperform longer posts by 40%"
  - "Tuesday morning posts get the most impressions"
  - "Try more carousel posts — your one carousel got 5x your average"
- [ ] Benchmark: compare your engagement rates to LinkedIn averages for your follower count

#### 9.4.4 Theme Pillars & Brand Strategy
- [ ] **Theme pillars** — 3-5 core topics that define your professional brand
  - Derived from: target role types, candidate profile positioning, skill strengths, industry expertise
  - Example for a CTO: "Engineering Leadership", "AI/ML Strategy", "Scaling Teams", "Tech Culture"
  - Flexible — evolve over time as target roles shift
- [ ] **Theme-to-role mapping**: suggest theme pillars based on the types of roles being targeted
  - Targeting VP Engineering? → emphasize scaling, people management, delivery
  - Targeting AI Architect? → emphasize technical depth, research, architecture decisions
- [ ] **Content calendar**: suggested posting cadence per pillar (rotate topics to avoid one-note)
- [ ] **Trending topic overlay**: surface trending topics in your industry/niche that align with your pillars
  - Sources: LinkedIn trending, industry news, HN/Reddit trends, Google Trends
  - "AI agents are trending this week and aligns with your 'AI Strategy' pillar — here's a post angle"
- [ ] **Brand coherence score**: are your recent posts on-brand or drifting? Alert if posting off-pillar too often
- [ ] **About section sync**: as pillars evolve, suggest LinkedIn About section updates to reinforce brand

#### 9.4.5 Post Generation
- [ ] Generate posts using **LinkedIn voice guide** (distinct from resume voice rules)
- [ ] Voice guide sourced from: stored post history analysis (tone, structure, vocabulary, cadence)
- [ ] Post inputs: topic/theme, key point to make, optional article/news link to riff on, target length
- [ ] Post types supported: thought leadership, hot take, storytelling, how-to/lessons learned, engagement bait (polls, questions), company/industry commentary, career reflection
- [ ] **Hook-first writing**: AI generates strong opening hooks (the "above the fold" text before "see more")
- [ ] Voice validation: run generated post through LinkedIn voice check (adapted from check_voice)
- [ ] Hashtag suggestions based on topic + trending + historical performance
- [ ] CTA suggestions based on post type and engagement patterns
- [ ] Preview: show approximate LinkedIn rendering (character count, line breaks, "see more" cutoff point)

#### 9.4.6 LinkedIn Voice Guide System (Generic / Multi-User)
The LinkedIn voice guide must be user-specific, not hardcoded. Platform provides tools to help any user build their own.
- [ ] **Voice guide generation from post history**: analyze user's existing LinkedIn posts → extract patterns:
  - Sentence structure preferences (short punchy vs. flowing)
  - Vocabulary fingerprint (words they use often, words they avoid)
  - Tone markers (humor level, formality, contrarian vs. consensus)
  - Structural patterns (list posts, story arc, open with question, etc.)
  - Hook style (bold statement, question, statistic, personal anecdote)
- [ ] **Voice guide editor**: user can review AI-extracted rules and adjust (add rules, remove rules, override)
- [ ] **Generation rules table**: `linkedin_voice_rules` (rule_text, category, weight, active, user_id)
  - Categories: tone, structure, vocabulary, hook, cta, banned_patterns, formatting
- [ ] **Starter templates**: default voice guide presets by persona (executive, technical, creative, academic)
- [ ] Voice guide evolves: as more posts are written and engagement tracked, system suggests rule updates ("posts where you use humor get 2x engagement — should we add a humor-friendly rule?")
- [ ] **Separation from resume voice rules**: LinkedIn voice is different from resume voice. More casual, more personality, more opinion. Separate rule sets, separate check tools.

### 9.5 LinkedIn Engagement Strategy
- [ ] Comment strategy: identify posts from target company employees to engage with
- [ ] Engagement tracking: which comments/interactions lead to connection requests or conversations
- [ ] Content calendar with posting cadence recommendations

### 9.6 Resume/LinkedIn Sync
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
- [ ] **Visual WYSIWYG preview**: see the resume rendered as you edit (not just JSON recipe view)
- [ ] ATS score indicator alongside gap analysis fit score (see 5.3)
- [ ] Export to DOCX/PDF
- [ ] Side-by-side: resume preview + JD with keyword highlighting

### 11.4 Template Editor
- [ ] Drag-and-drop layout, named slots, formatting rules
- [ ] Save as new template

### 11.5 Job Search & Saved Jobs
- [ ] **Fresh Jobs Inbox page** — all newly discovered jobs, sortable by fit score, source, date
  - [ ] Quick-action buttons: save, pass, snooze, batch select
  - [ ] Source filter (API, plugin, email, social, RSS)
  - [ ] Auto-refresh / new job count badge
- [ ] Saved jobs queue (evaluation pipeline before applying)
- [ ] Multi-platform search interface
- [ ] Job detail view with gap analysis
- [ ] "Apply" flow: gap analysis -> tailor resume -> generate materials -> submit
- [ ] Batch apply queue view: select multiple → review → batch process

### 11.6 Networking & Contacts (CRM)
- [ ] Contact list with relationship health score, stage, last contact
- [ ] **Relationship pipeline kanban** (Identified → Connected → Engaged → Warm → Advocate → Dormant)
- [ ] Contact detail view: profile, timeline, tasks, outreach history, linked applications
- [ ] **Company contact map**: for a given company, show all contacts + their stages
- [ ] **Path finder UI**: "Who can intro me to [company/person]?"
- [ ] Outreach history per contact
- [ ] Referral tracking
- [ ] Follow-up reminders + task queue
- [ ] **Daily networking digest view** (today's tasks, stale contacts, opportunities)
- [ ] Network health dashboard: contacts by stage, going stale, coverage at target companies

### 11.7 Interview & Prep
- [ ] Upcoming interviews with prep materials
- [ ] Debrief capture form
- [ ] STAR story browser
- [ ] **AI mock interview UI** — practice mode with question display, answer input, real-time feedback (see 8.5)
- [ ] Mock interview history + improvement tracking

### 11.8 Notifications & Activity
- [ ] Notification center (bell icon → dropdown panel → full notification page)
- [ ] Unread count badge in nav
- [ ] Activity feed: recent actions across all modules (applied, saved, contacted, etc.)
- [ ] Notification preferences page (per-type enable/disable)

### 11.9 Analytics & Reports
- [ ] Campaign dashboard: pipeline velocity, conversion funnels, activity trends
- [ ] **Market intelligence dashboard**: JOLTS trends, TRU vs U-3, WARN filings, layoff/hiring sentiment (see 16.2)
- [ ] Skill demand + micro signals dashboard (see 16.3)
- [ ] Weekly digest view (auto-generated campaign summary)
- [ ] Monthly market briefing view (macro signals + strategy recommendations)
- [ ] Source effectiveness charts
- [ ] Resume variant performance comparison

### 11.10 LinkedIn Hub
- [ ] **Profile scorecard**: headline, about, experience, skills, featured — each scored with improvement suggestions
- [ ] **Skills manager**: current skills list, add/remove recommendations, skills-to-role mapping, endorsement gaps
- [ ] **Content dashboard**: post history, engagement charts, theme pillar balance, content calendar (see 9.4)
- [ ] **Profile preview**: approximate rendering of how profile looks to recruiters

### 11.11 Other Views
- [ ] Company research + dossier view
- [ ] Email history viewer
- [ ] Semantic search bar
- [ ] Settings / preferences
- [ ] Workflow automation builder (see 15.2)
- [ ] Batch operations progress view

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
- [x] Settings / preferences per user (settings table, CRUD routes, frontend settings page)
- [ ] Candidate profile wizard (frontend): name, credentials, location, contact info, elevator pitch
- [ ] Resume header auto-populated from profile
- [ ] Target role preferences (titles, industries, locations, salary range, remote/hybrid/onsite)
- [ ] Deal-breakers and non-negotiables capture

### 13.2 Knowledge Base Population
- [x] Resume upload + parse: .docx/.pdf -> extract career_history + bullets (auto-detect employers, dates, bullet points)
- [ ] LinkedIn profile import: parse exported CSV -> career_history (titles, dates, companies), connections -> contacts
- [ ] Manual entry UI: add/edit career_history, bullets, skills, summary_variants directly
- [ ] Bulk import from text: paste a resume or work history -> parse into structured data
- [x] Skills auto-extraction from bullets (rule-based parser extracts skills)
- [x] Deduplication: detect duplicate bullets or career entries during import (SequenceMatcher, configurable threshold)
- [x] Existing ETL scripts available as reference implementation (load_knowledge_base.py, etc.)

### 13.3 External Integrations Setup
- [ ] Gmail MCP setup guide: OAuth credentials, scope configuration, Claude Code .mcp.json config
- [ ] Google Calendar MCP setup guide: OAuth credentials, scope configuration
- [ ] LinkedIn data export instructions (request archive, download, where to place files)
- [ ] Indeed MCP setup guide (if applicable to other users)
- [ ] WebSearch/WebFetch MCP configuration
- [ ] Guide: "How to connect your AI agent to this platform via MCP" (SSE endpoint, tool list, auth)

### 13.4 Voice & Style Configuration
- [ ] **Resume voice guide** template (default set of anti-AI rules, customizable)
- [ ] "Bring your own voice": upload writing samples → AI extracts style rules
- [ ] Banned words/constructions editor (frontend)
- [ ] Industry-specific voice presets (tech, finance, healthcare, etc.)
- [ ] **LinkedIn voice guide** generation (separate from resume voice — see 9.4.6):
  - [ ] Import LinkedIn post history → AI analyzes tone, structure, vocabulary, hooks → generates voice rules
  - [ ] Starter persona templates (executive, technical, creative, academic)
  - [ ] Voice guide editor: review/adjust AI-extracted rules
  - [ ] LinkedIn voice rules stored separately from resume voice rules (different table, different check tool)
- [ ] Voice guide must be **user-specific, never hardcoded** — all Stephen-specific patterns stripped from code, replaced by generated rules per user

### 13.5 Template Setup
- [x] Upload your own .docx resume as a template (onboard endpoint: upload -> templatize -> recipe -> verify)
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
- [x] Docker one-command setup (`docker compose up`) — in SETUP.md
- [x] README with architecture overview, setup instructions, quickstart — code/README.md
- [x] API reference (all endpoints with request/response examples) — code/docs/API_REFERENCE.md (105 endpoints)
- [x] MCP tool reference (all tools with parameters and examples) — code/docs/MCP_REFERENCE.md (42 tools)
- [ ] Schema migration guide (how to add tables, run migrations)
- [ ] Contributing guide
- [x] Troubleshooting guide (common issues: Docker, MCP connection, OAuth) — code/docs/TROUBLESHOOTING.md

### 13.8 Claude Code Integration
- [x] CLAUDE.md template for other users — code/CLAUDE.md (operational agent instructions)
- [x] Installation guide for Claude Code + MCP setup — in SETUP.md steps 3+5
- [ ] Example SKILLS files (job-hunter workflow, resume tailoring workflow)
- [ ] Guide: "How to customize CLAUDE.md for your job search"

---

## 14. Browser Plugin

> Full requirements: [14_BROWSER_PLUGIN.md](14_BROWSER_PLUGIN.md) (91 requirements, 13 sections)

Chrome extension (Manifest V3) that connects to the local SuperTroopers backend (localhost:8055) to augment job browsing with career intelligence. Dark theme with terminal green (#00FF41) aesthetic. All data stays local.

### Phase 0: Foundation (14.0) ✅
- [x] 14.0.1 Chrome extension scaffold (Manifest V3, TypeScript, Vite, React popup)
- [x] 14.0.2 Background service worker with localhost API connection
- [x] 14.0.3 Popup UI — connection status, pipeline summary, dark/green theme
- [x] 14.0.4 Extension icon with badge (application count)
- [x] 14.0.5 Content script framework with site-specific config system

### Phase 1: Job Capture + Match (14.1-14.2)
- [ ] 14.1 Job detection on major boards (Indeed, LinkedIn, Glassdoor) + 46 ATS platforms
- [ ] 14.1.1 "Save to SuperTroopers" button injection on job listings
- [ ] 14.1.2 Auto-extract: title, company, location, salary, JD text, URL
- [ ] 14.1.3 Duplicate detection (don't save same job twice)
- [ ] 14.2 Match score overlay — run gap analysis, show fit % inline on job pages
- [ ] 14.2.1 Strong matches, partial matches, gaps breakdown
- [ ] 14.2.2 Keyword highlighting in JD text

### Phase 2: AI Materials + Auto-Apply (14.3-14.4)
- [ ] 14.3 One-click tailored resume generation from any job listing page
- [ ] 14.3.1 Cover letter generation with voice rules enforcement
- [ ] 14.3.2 Generation progress indicator, download when complete
- [ ] 14.4 ATS auto-fill — detect form fields, populate from backend profile data
- [ ] 14.4.1 Top ATS platforms: Workday, Greenhouse, Lever, iCIMS, Taleo
- [ ] 14.4.2 Resume file attachment handling
- [ ] 14.4.3 User review + confirm before submission (never auto-submit)
- [ ] 14.4.4 Open-ended question answering from career data + STAR stories

### Phase 3: Application Tracking (14.5)
- [ ] 14.5 Auto-create application record after applying
- [ ] 14.5.1 Status change tracking from within the browser
- [ ] 14.5.2 Popup application list with filters
- [ ] 14.5.3 Badge counts (saved, applied, interviewing)
- [ ] 14.5.4 Stale application alerts

### Phase 4: Networking + Outreach (14.6-14.8)
- [ ] 14.6 Contact overlay — show existing contacts at company on job/company pages
- [ ] 14.6.1 Contact cards with relationship strength, last interaction
- [ ] 14.6.2 LinkedIn connection search for warm intros
- [ ] 14.7 Outreach automation — craft LinkedIn messages, emails with voice rules
- [ ] 14.7.1 Schedule sends and track touchpoints
- [ ] 14.7.2 Outreach templates by relationship type
- [ ] 14.8 Response tracking — unified view of email + messaging responses per contact
- [ ] 14.8.1 Auto-update contact records with latest interaction

### Phase 5: Notifications + Fresh Jobs (14.13-14.14)
- [ ] 14.13 Notification panel in popup — show unread alerts from backend (see 2.6)
- [ ] 14.13.1 Toast notifications for high-priority events (new high-fit job, interview response)
- [ ] 14.13.2 Desktop notifications via browser Notification API
- [ ] 14.13.3 Badge count updates (unread notifications + pipeline counts)
- [ ] 14.14 Fresh jobs page — open localhost frontend filtered to new/unreviewed jobs
- [ ] 14.14.1 Quick-action buttons in popup: "View Fresh Jobs" opens frontend tab
- [ ] 14.14.2 Inline triage from popup: save / pass / snooze without opening frontend

### Phase 6: Intelligent Batch Apply (14.15)
Unlike spray-and-pray auto-apply bots that submit generic resumes at volume, SuperTroopers batch apply is an AI agent with full access to the candidate's career data, voice rules, and gap analysis. Every application is individually tailored — the automation is in the orchestration, not in cutting corners.

**Per-application pipeline (fully automated, human-reviewed):**
1. Run gap analysis against JD → fit score + match/gap breakdown
2. Clone best-fit recipe → swap bullets to address JD requirements
3. Rewrite summary targeting the specific role + company
4. Generate tailored cover letter using gap analysis + company dossier + voice rules
5. Fill ATS form fields from candidate profile (education, certifications, work history)
6. Answer open-ended application questions from STAR stories + KB
7. Attach tailored resume + cover letter
8. **Pause for human review** → candidate confirms or edits before submit
9. Log application in tracker with all generated materials linked

- [ ] 14.15 Batch apply queue — select multiple saved/triaged jobs, plugin processes sequentially
- [ ] 14.15.1 Per-job intelligent tailoring pipeline (steps 1-9 above)
- [ ] 14.15.2 Review gate: pause between applications for candidate review/confirm (configurable: review-all, review-on-low-fit, auto-submit-high-fit)
- [ ] 14.15.3 Progress tracker: X of Y complete, current job, fit score, errors/skips
- [ ] 14.15.4 Post-batch report: what was applied, materials generated, fit scores, what needs manual attention
- [ ] 14.15.5 Rate limiting and human-like delays (avoid bot detection)
- [ ] 14.15.6 Quality floor: skip or flag jobs below configurable fit threshold (don't waste applications on bad matches)
- [ ] 14.15.7 All generated materials saved to generated_materials table + Output/{Company}_{Role}_{Date}/

### Technical (14.9-14.12)
- [ ] 14.9 ATS site config system (47 platforms, tiered priority)
- [ ] 14.10 Minimal permissions (activeTab, storage, tabs — no cookies, no webRequest)
- [ ] 14.11 Shadow DOM isolation for injected UI elements
- [ ] 14.12 5 new backend endpoints (plugin health, profile bundle, materials orchestrator, ATS config, URL dedup)

---

## 15. Batch Operations & Workflow Automation

### 15.1 Batch Operations
Operations that process multiple items at once to save time.
- [ ] Batch gap analysis: run fit scoring against N saved jobs in one action
- [ ] Batch resume tailoring: generate tailored resumes for a queue of jobs
- [ ] Batch company research: pull fundamentals/dossiers for a list of companies
- [ ] Batch outreach: draft personalized messages for multiple contacts
- [ ] Batch status update: mark multiple applications as rejected/ghosted/archived
- [ ] Batch import: add multiple jobs from a spreadsheet, email list, or URL list
- [ ] Progress tracking for all batch operations (X of Y, ETA, errors)
- [ ] REST API: POST /api/batch/{operation} with job/item IDs
- [ ] MCP tools: batch_gap_analysis, batch_research, batch_outreach

### 15.2 Workflow Automation Engine
Configurable trigger-action workflows (like Zapier for your job search).
- [ ] Workflow definition table (trigger, conditions, actions, enabled, last_run)
- [ ] Trigger types:
  - [ ] Job discovered (new entry in fresh_jobs)
  - [ ] Job saved (moved from fresh_jobs to saved_jobs)
  - [ ] Application status changed
  - [ ] Email received matching an application
  - [ ] Follow-up overdue
  - [ ] Contact relationship cooling
  - [ ] Time-based (daily, weekly)
- [ ] Action types:
  - [ ] Run gap analysis
  - [ ] Generate tailored resume
  - [ ] Draft outreach/follow-up message
  - [ ] Send notification (see 2.6)
  - [ ] Move to next pipeline stage
  - [ ] Auto-archive / expire
  - [ ] Pull company research
  - [ ] Create task/reminder
- [ ] Condition filters (e.g., "only if fit_score > 70", "only for target companies")
- [ ] Example workflows:
  - "Job saved → auto gap analysis → if fit > 70% → auto-tailor resume → notify"
  - "Applied + 14 days no response → draft follow-up → notify"
  - "Applied + 30 days no response + no follow-up response → mark ghosted"
  - "New recruiter email → create fresh job → auto-score → if high fit → notify urgent"
  - "Interview scheduled → auto-generate prep materials → create calendar reminder"
- [ ] Workflow log (what ran, when, what it did, any errors)
- [ ] REST API: CRUD workflows + enable/disable + manual trigger
- [ ] Frontend: visual workflow builder (drag-and-drop trigger → condition → action)

---

## 16. Market Intelligence

### 16.1 Salary & Compensation Tracking
- [x] salary_benchmarks table (12 roles) + cola_markets (7 markets)
- [ ] Salary trend monitoring over time (track changes in benchmarks)
- [ ] Compensation package comparison (base + bonus + equity + benefits)
- [ ] Offer evaluation calculator (compare offer against benchmarks + COLA)
- [ ] Historical offer tracking (what was offered vs. what was negotiated)

### 16.2 Macro Labor Market Signals
Government and institutional data sources that indicate overall market strength/weakness. These drive search strategy... aggressive in hot markets, patient/networked in cold ones.

#### 16.2.1 JOLTS Report (Bureau of Labor Statistics)
Monthly Job Openings and Labor Turnover Survey — the best leading indicator of market direction.
- [ ] Track key JOLTS metrics monthly: job openings, hires, quits ("leavers"), layoffs/discharges
- [ ] **Interpretation engine:**
  - Quits rate rising = workers confident, market thawing, easier to find jobs
  - Quits rate flat + layoffs rising = tightening market, harder near-term, lean into networking
  - Openings-to-unemployed ratio trending down = fewer chairs when music stops
  - Hires rate rising = companies actually filling roles, not just posting
- [ ] Filter by industry sector (tech, finance, healthcare, government, etc.)
- [ ] Historical trend charts (12-month rolling)
- [ ] Alert on significant month-over-month changes
- [ ] Data source: BLS JOLTS API (https://www.bls.gov/jlt/)

#### 16.2.2 True Rate of Unemployment (LISEP)
Ludwig Institute for Shared Economic Prosperity — the real unemployment picture beyond U-3.
- [ ] Track TRU (True Rate of Unemployment) vs. official U-3 rate
- [ ] TRU includes: functionally unemployed (working part-time involuntarily, working full-time below poverty wage)
- [ ] **Interpretation engine:**
  - TRU >> U-3 = lots of underemployed competition for good roles, expect more applicants per opening
  - TRU narrowing toward U-3 = market genuinely tightening, real demand for talent
- [ ] Historical trend comparison (TRU vs. U-3 over time)
- [ ] Data source: LISEP TRU reports (https://www.lisep.org/tru)

#### 16.2.3 WARN Act Notices (Mass Layoff Tracking)
Worker Adjustment and Retraining Notification Act — 60-day advance notice of mass layoffs.
- [ ] Aggregate WARN filings by state (filed with state labor departments)
- [ ] Track: company name, location, number of affected workers, layoff date, industry
- [ ] **Trend analysis:**
  - Rising WARN filings in your industry = defensive posture, network harder, secure offers faster
  - Falling WARN filings = market stabilizing
  - WARN filings at target companies = red flag, deprioritize or pause applications there
- [ ] Cross-reference with target company list (alert if a target company files WARN)
- [ ] Data sources: state labor department WARN databases (many publish CSV/RSS)

#### 16.2.4 News-Based Signals (Layoff & Hiring Aggregation)
Aggregate news mentions to build a real-time market sentiment index.
- [ ] Track layoff announcements: aggregate counts by company, industry, month
- [ ] Track hiring spree announcements: companies announcing expansion, new offices, headcount growth
- [ ] **Layoff-to-hiring ratio** by industry: rising ratio = contracting market, falling = expanding
- [ ] Sources: Layoffs.fyi, TrueUp tech layoff tracker, news RSS feeds, Google News alerts
- [ ] Cross-reference with target company list:
  - Target company in layoff news → alert + deprioritize
  - Target company in hiring news → alert + prioritize + check for matching roles
- [ ] Sentiment trend line: are things getting better or worse in your target industries
- [ ] Monthly market briefing: auto-generated summary of macro signals + what it means for your search strategy

### 16.3 Job Market Micro Signals
Signals specific to your role type, skills, and target market.
- [ ] Skill demand analysis: which skills appear most in JDs matching your profile
- [ ] Skill trend tracking: rising/declining skills over time
- [ ] Hiring volume trends by role type, industry, geography
- [ ] Industry hiring cycle awareness (when do companies typically hire for your level)
- [ ] Remote vs. hybrid vs. onsite trend tracking
- [ ] Company hiring velocity (how fast are target companies posting new roles)

### 16.4 Competitive Landscape
- [ ] Similar candidates: what profiles compete for the same roles (anonymized from JD requirements)
- [ ] Differentiator analysis: what makes your profile stand out vs. typical requirements
- [ ] Skills gap to market: what skills would unlock the most additional opportunities
- [ ] Certification ROI: which certifications appear most in high-paying matching JDs

### 16.5 Campaign Performance Analytics
- [ ] Weekly/monthly campaign digest (automated report)
- [ ] Response rate trends over time
- [ ] Application-to-interview conversion rate
- [ ] Interview-to-offer conversion rate
- [ ] Average time-to-response by company/source/role level
- [ ] Best performing resume variant tracking
- [ ] Optimal application timing (day of week, time of day correlations)
- [ ] Source ROI: which job boards/channels yield the most interviews per application
- [ ] Networking ROI: which contacts/channels lead to the most warm intros/referrals
- [ ] Activity recommendations engine ("you haven't applied in 5 days", "3 follow-ups overdue", "resume V32 outperforms V31 by 2x")

---

## 17. Anti-AI Detection Integration

Integrate with the AntiAI Detection MCP server — a separate locally-hosted project that detects AI-generated patterns in text and humanizes output. The AntiAI tool runs as its own MCP server alongside SuperTroopers. Users can run either project standalone, but the combination is the recommended setup for job seekers.

**Dependency:** The AntiAI Detection project is being built separately. Integration here is DEFERRED until that project exposes stable MCP endpoints. These requirements define what SuperTroopers needs from it and where it plugs in.

**Architecture:** AntiAI runs as a separate MCP server (its own repo, its own Docker container or local process). SuperTroopers calls it via MCP tool calls or HTTP, depending on how the AntiAI server exposes its interface. No code from AntiAI is embedded in SuperTroopers... it's a peer service, not a dependency.

### 17.1 AntiAI MCP Connection
- [ ] AntiAI MCP server registered in `.mcp.json` alongside SuperTroopers MCP
- [ ] Health check: verify AntiAI MCP is reachable before attempting calls
- [ ] Graceful degradation: if AntiAI MCP is unavailable, content generation still works (skip detection, warn user)
- [ ] Connection config in Settings page (AntiAI endpoint URL, enable/disable toggle)
- [ ] Status indicator on frontend dashboard (connected / disconnected / not configured)

### 17.2 AI Detection Scanning
Run AI detection on all generated content before presenting to the user. Every content generation endpoint should have an optional "scan" step.
- [ ] **Resume bullets**: after generating or rewriting bullets, scan for AI patterns
- [ ] **Professional summaries**: scan generated summary variants
- [ ] **Cover letters**: scan full cover letter text (7.1)
- [ ] **Outreach messages**: scan cold/warm outreach drafts (7.2)
- [ ] **Thank-you notes**: scan generated thank-you text (7.3)
- [ ] **LinkedIn posts**: scan generated post content (9.4.5)
- [ ] **Interview prep talking points**: scan generated talking points (8.2)
- [ ] **Open-ended ATS answers**: scan auto-generated application question answers (14.4.4)
- [ ] Detection result includes: AI probability score, flagged patterns/phrases, confidence level
- [ ] Configurable threshold: user sets their acceptable AI detection score (default: flag if >20% AI probability)
- [ ] Results displayed inline with generated content (highlight flagged phrases, show score)

### 17.3 Humanization Pipeline
When AI detection flags content above threshold, automatically humanize it.
- [ ] **Auto-humanize mode**: if detection score exceeds threshold, send to AntiAI humanizer before presenting
- [ ] **Manual humanize mode**: user reviews detection results, clicks "Humanize" on flagged sections
- [ ] **Iterative loop**: humanize → re-scan → if still flagged → humanize again (max 3 iterations, then present with warning)
- [ ] **Voice preservation**: humanized output must still pass SuperTroopers voice rules (`check_voice`). If humanization breaks voice rules, rewrite using both voice rules AND humanization guidance
- [ ] **Before/after comparison**: show original AI-generated text alongside humanized version so user can pick
- [ ] **Selective humanization**: user can choose to humanize specific paragraphs/bullets rather than entire document

### 17.4 Integration Points in Existing Workflows
Where AntiAI detection plugs into existing SuperTroopers flows:

#### 17.4.1 Resume Generation (Section 3)
- [ ] Post-generation scan: after `generate_resume` produces output, scan all generated text blocks
- [ ] Recipe-level setting: per-recipe toggle for auto-humanize (some recipes may be for internal use, don't need it)
- [ ] ATS score + AI detection score shown side-by-side in resume builder (11.3)

#### 17.4.2 Application Materials (Section 7)
- [ ] Cover letter generation pipeline: generate → voice check → AI scan → humanize if needed → final voice check → present
- [ ] Outreach message pipeline: same flow as cover letters
- [ ] Thank-you note pipeline: same flow
- [ ] All materials in `generated_materials` table get an `ai_detection_score` column (nullable, populated when scanned)

#### 17.4.3 Browser Plugin (Section 14)
- [ ] One-click materials generation (14.3) includes AI detection step before download
- [ ] Batch apply pipeline (14.15) includes AI scan + auto-humanize per application
- [ ] Open-ended question answers (14.4.4) scanned before form fill

#### 17.4.4 LinkedIn Content (Section 9.4)
- [ ] Post generation (9.4.5) includes AI detection before presenting draft
- [ ] LinkedIn voice check + AI detection as combined quality gate
- [ ] Content calendar posts auto-scanned on generation

#### 17.4.5 Workflow Automation (Section 15.2)
- [ ] New action type: "Scan for AI patterns" (can be added to any workflow)
- [ ] New action type: "Humanize text" (runs after scan, conditional on score)
- [ ] Example workflow: "Generate cover letter → scan AI → if score > 20% → humanize → voice check → notify"

### 17.5 Reporting & Analytics
- [ ] AI detection score history: track average scores over time (are we getting better at human-sounding output?)
- [ ] Per-content-type breakdown: which types of content score highest on AI detection (resumes vs. cover letters vs. outreach)
- [ ] Humanization effectiveness: before/after scores showing improvement
- [ ] Flag patterns that repeatedly trigger detection (feed back into voice rules as new banned patterns)
- [ ] Dashboard widget: "AI Detection Health" showing recent scan results and trends (11.9)

### 17.6 Voice Rules Feedback Loop
AI detection findings should feed back into the voice system to prevent future AI-sounding output.
- [ ] When a specific phrase or pattern is repeatedly flagged by AI detection, suggest adding it to voice_rules as a banned pattern
- [ ] Periodic review: "These 10 phrases triggered AI detection most often this month — add to banned list?"
- [ ] AntiAI detection categories mapped to voice rule categories (so detection insights are actionable)

### 17.7 Multi-User & Configuration
- [ ] Per-user AntiAI settings: detection threshold, auto-humanize on/off, which content types to scan
- [ ] Global default settings in platform config
- [ ] API endpoints for AntiAI configuration CRUD
- [ ] Settings page section for AntiAI preferences (under existing Settings, see 11.11)

---

## 18. LinkedIn Content Archival

> Full requirements: [linkedin_content_sync.md](linkedin_content_sync.md)

Automated LinkedIn content archival via two strategies: passive capture through the browser extension and scheduled headless scraping. Feeds into existing `scraped_posts`, `scraped_comments`, `scraped_messages` tables.

**Scraper code:** `code/utils/linkedin_scraper/` (copied from `local_code/scrapers/`)

### 18.1 Extension Passive Capture
- [ ] Content script on `*.linkedin.com/*` pages (separate from job-board content script)
- [ ] Capture posts, comments from activity feed via MutationObserver
- [ ] Capture messages from `/messaging/` pages
- [ ] Capture SSI score from `/sales/ssi` (new `linkedin_ssi_scores` table)
- [ ] Batch and forward captured data to backend `-live` import endpoints
- [ ] Incremental dedup: backend skips existing URNs

### 18.2 Session/Cookie Capture
- [ ] Extension captures `li_at`, `JSESSIONID`, `li_mc` cookies (requires `cookies` permission)
- [ ] Cookies encrypted with Fernet, stored in `linkedin_sessions` table
- [ ] Periodic validation (every 4h) with notification on expiry
- [ ] Manual refresh button in extension Settings

### 18.3 Headless Scheduled Scraping
- [ ] `--headless --cookies-from-db` mode added to scraper CLI
- [ ] Scheduler job `linkedin_content_sync` (every 6h, opt-in)
- [ ] Cookie validation job `linkedin_cookie_check` (every 4h)
- [ ] Graceful degradation: skip scrape + notify user when cookies expire
- [ ] `scraper_runs` table for run history and diagnostics

### 18.4 Settings UI
- [ ] LinkedIn Sync section in extension Settings panel
- [ ] Session status indicator (active/expiring/expired)
- [ ] Passive capture toggle (default: off)
- [ ] Scheduled scraping toggle + frequency selector
- [ ] Sync history (recent scraper_runs with item counts)
