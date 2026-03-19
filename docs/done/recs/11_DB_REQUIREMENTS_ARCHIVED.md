# 11. Database & Application Platform — Requirements

Parent: [REQUIREMENTS.md](../../../recs/REQUIREMENTS.md) Section 11

The data layer and application stack that powers the Reverse Recruiting Super Tool. Turns flat files (markdown, Excel, emails) into a queryable, searchable, embeddable database with a web UI and API.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                  React Frontend                  │
│   (Dashboard, Resume Editor, Tracker, Search)    │
├─────────────────────────────────────────────────┤
│                  Flask Backend                    │
│   (API, Cron Jobs, ETL Pipelines, RAG Queries)   │
├─────────────────────────────────────────────────┤
│            PostgreSQL + pgvector                  │
│   (Structured Data + Vector Embeddings)           │
├─────────────────────────────────────────────────┤
│              MCP Server (Docker)                  │
│   (Claude Code integration, tool interface)       │
├─────────────────────────────────────────────────┤
│           External Integrations                   │
│   (Gmail, Calendar, Indeed, LinkedIn, WebSearch)  │
└─────────────────────────────────────────────────┘
```

---

## 11.1 Database Schema
**Schema:** [11_DB_SCHEMA.md](11_DB_SCHEMA.md)

- [x] Core identity tables: career_history, bullets, skills, summary_variants
- [x] Job search pipeline: companies, applications, interviews, contacts
- [x] Email & document store: emails, documents, resume_versions
- [x] Content & knowledge: content_sections, voice_rules, salary_benchmarks, cola_markets
- [x] Resume generation: resume_templates, resume_header, education, certifications
- [ ] Resume recipes: resume_recipes, career_history.career_links (Migration 006)
- [x] Analytics views: application_funnel, source_effectiveness, monthly_activity

---

## 11.2 ETL Pipelines

### 11.2.0 Load Order (Dependencies Matter)

ETL scripts must run in this order. Later scripts depend on IDs created by earlier ones.

```
Phase 1 — Core Identity (no dependencies)
  1. load_knowledge_base.py    → career_history, bullets, skills, summary_variants
  2. load_companies.py         → companies

Phase 2 — Pipeline (depends on companies)
  3. load_applications.py      → applications (creates missing companies too)
  4. load_contacts.py          → contacts

Phase 3 — Content (depends on applications)
  5. load_emails.py            → emails (links to applications by company+role)
  6. load_documents.py         → documents, resume_versions
  7. load_interviews.py        → interviews (links to applications)

Phase 4 — Content Migration (no dependencies, reads from Archived/Notes/)
  8. load_content_sections.py  → content_sections (candidate_profile, rejection_analysis, etc.)
  9. load_voice_rules.py       → voice_rules (173 rules from Voice Guide)
  10. load_salary_benchmarks.py → salary_benchmarks + cola_markets

Phase 5 — Enrichment (depends on all above)
  11. generate_embeddings.py   → vector embeddings on bullets, summaries, JDs, emails, docs

Full reload command:
  python load_knowledge_base.py load && \
  python load_companies.py load && \
  python load_applications.py load && \
  python load_contacts.py load && \
  python load_emails.py load && \
  python load_documents.py load && \
  python load_interviews.py load && \
  python load_content_sections.py && \
  python load_voice_rules.py && \
  python load_salary_benchmarks.py && \
  python generate_embeddings.py
```

### 11.2.1 Data Loaders
- [x] `load_knowledge_base.py` — parse KNOWLEDGE_BASE.md → career_history (19), bullets (232), skills (255), summary_variants (8)
- [x] `load_companies.py` — parse target_companies.xlsx → companies (120 + 39 from applications)
- [x] `load_applications.py` — parse APPLICATION_HISTORY.md + Excel tracker → applications (48)
- [x] `load_contacts.py` — parse CANDIDATE_PROFILE.md references → contacts (26)
- [x] `load_content_sections.py` — parse Notes/*.md → content_sections (77 sections: 40 candidate profile, 20 rejection analysis, 10 application history, 7 email scan)
- [x] `load_voice_rules.py` — parse VOICE_GUIDE.md → voice_rules (173 rules across 8 parts)
- [x] `load_salary_benchmarks.py` — parse SALARY_RESEARCH.md → salary_benchmarks (12 roles) + cola_markets (7 markets)
- [ ] `load_emails.py` — fetch Gmail via MCP, parse into emails table, categorize, link to applications
- [ ] `load_documents.py` — scan Originals/, Templates/, Imports/Organized/ and index all documents
- [ ] `load_interviews.py` — parse from Google Calendar events, link to applications
- [ ] `generate_embeddings.py` — run embeddings on all text fields for RAG

### 11.2.2 Cron Jobs
- [ ] `scan_gmail.py` — periodic Gmail scan for new application emails, auto-categorize, update tracker
- [ ] `scan_indeed.py` — run saved Indeed searches, find new postings, auto-score fit
- [ ] `check_calendar.py` — pull upcoming interviews from Google Calendar, prep materials
- [ ] `follow_up_check.py` — flag applications with no response after 7/14/21 days
- [ ] `refresh_companies.py` — check target companies for new job postings

### 11.2.3 RAG / Search
- [ ] `semantic_search.py` — "find me a bullet about X" queries against pgvector embeddings
- [ ] `jd_matcher.py` — given a JD, find best-matching bullets, generate gap analysis, suggest resume edits
- [ ] `story_finder.py` — given an interview question category, find best STAR stories
- [ ] `network_check.py` — given a company, check contacts table for warm intro paths

---

## 11.3 Flask API

### 11.3.1 Endpoints
- [x] `GET /api/applications` — list/filter/search applications
- [x] `POST /api/applications` — add new application
- [x] `PATCH /api/applications/:id` — update status, add notes
- [x] `GET /api/companies` — list/filter target companies
- [x] `GET /api/bullets/search` — semantic search across bullets
- [x] `POST /api/gap-analysis` — submit JD text, get gap analysis + recommended bullets
- [x] `GET /api/analytics/funnel` — application funnel stats
- [x] `GET /api/analytics/monthly` — monthly activity breakdown
- [x] `GET /api/analytics/sources` — source effectiveness
- [x] `GET /api/contacts` — network contacts with company cross-reference
- [x] `GET /api/interviews` — upcoming + past interviews
- [x] `POST /api/resume/generate` — generate tailored resume from spec or recipe
- [ ] `GET /api/resume/recipes` — list resume recipes
- [ ] `GET /api/resume/recipes/<id>` — get recipe with full JSON
- [ ] `POST /api/resume/recipes` — create resume recipe
- [ ] `PUT /api/resume/recipes/<id>` — update recipe
- [ ] `DELETE /api/resume/recipes/<id>` — soft delete recipe
- [ ] `POST /api/resume/recipes/<id>/generate` — generate .docx from recipe
- [x] `GET /api/emails` — search/filter emails
- [x] `GET /api/content/<document>` — full document reconstruction from content_sections (supports ?format=text for markdown)
- [x] `GET /api/content` — list all available documents with section counts
- [x] `GET /api/voice-rules` — voice rules with category/part filtering (supports ?format=text)
- [x] `POST /api/voice-rules/check` — check text against banned words/constructions
- [x] `GET /api/salary-benchmarks` — salary benchmarks with role/tier filtering
- [x] `GET /api/cola-markets` — COLA market reference data

### 11.3.2 Auth & Config
- [x] Local-only for now (no auth needed — single user)
- [x] Config file for DB connection, API keys (embeddings), MCP server settings
- [x] Health check endpoint

---

## 11.4 React Frontend

### 11.4.1 Dashboard
- [ ] Pipeline overview (applications by status, weekly/monthly trends)
- [ ] Source effectiveness chart
- [ ] Upcoming interviews
- [ ] Stale applications needing follow-up
- [ ] Recent activity feed

### 11.4.2 Application Tracker
- [ ] Table view with sort/filter/search
- [ ] Kanban board view (columns = statuses)
- [ ] Click into application for full detail (JD, resume used, notes, emails, interviews)
- [ ] Quick-add new application
- [ ] Status change with timestamp

### 11.4.3 Resume Builder
- [ ] View/edit Knowledge Base bullets
- [ ] Drag-and-drop bullet selection for tailored resume
- [ ] JD paste → auto gap analysis → suggested bullets
- [ ] Preview generated resume
- [ ] Export to DOCX/PDF

### 11.4.4 Company Research
- [ ] Target company list with scores, contacts, engagement status
- [ ] Click into company for dossier (Indeed data, news, contacts, past applications)
- [ ] Network check ("do I know anyone here?")

### 11.4.5 Search & RAG
- [ ] Semantic search bar — "find stories about M&A integration"
- [ ] Interview prep mode — select question category, get matching STAR stories
- [ ] Email search with category filters

### 11.4.6 Contacts & Network
- [ ] Contact list with relationship strength, last contact
- [ ] Company cross-reference
- [ ] Follow-up reminders

---

## 11.5 MCP Server (Docker)

### 11.5.1 Purpose
Custom MCP server that gives Claude Code direct access to the database, replacing file-based workflows with structured queries.

### 11.5.2 Tools Exposed (20 total)

#### Career & Knowledge Base
- [x] `search_bullets(query, tags, role_type, industry)` — search resume bullets
- [x] `get_career_history(employer)` — career positions with bullets
- [x] `get_summary_variant(role_type)` — professional summary for a role
- [x] `get_skills(category)` — skills inventory

#### Content & Voice
- [x] `get_candidate_profile(section, format)` — identity, positioning, references
- [x] `get_voice_rules(category, part, format)` — voice guide rules
- [x] `check_voice(text)` — validate text against banned patterns
- [x] `get_salary_data(role, tier)` — salary benchmarks + COLA
- [x] `get_rejection_analysis(section, format)` — interview outcomes, patterns

#### Job Search Pipeline
- [x] `match_jd(jd_text)` — gap analysis against bullets
- [x] `search_applications(status, company, source)` — query tracker
- [x] `add_application(company_name, role, ...)` — log new application
- [x] `update_application(id, status, notes)` — update status

#### Companies & Network
- [x] `search_companies(query, priority, sector)` — find target companies
- [x] `get_company_dossier(name)` — full company info
- [x] `search_contacts(company, name)` — find contacts
- [x] `network_check(company)` — warm intro research

#### Email & Analytics
- [x] `search_emails(query, category, after, before)` — search parsed Gmail
- [x] `get_analytics()` — pipeline stats, funnel, source effectiveness

#### Resume Generation
- [x] `generate_resume(version, variant, output_path)` — generate resume from spec
- [ ] `generate_resume(recipe_id)` — generate resume from recipe (recipe path)
- [x] `get_resume_data(version, variant, section)` — get resume data for reconstruction

### 11.5.3 Docker Setup
- [x] Dockerfile for backend (Python + Flask + MCP combined)
- [x] docker-compose.yml: Postgres + pgvector (port 5555) + Flask/MCP backend (ports 8055/8056)
- [x] Volume mounts for DB persistence (local_code/db_data/)
- [x] Environment variables for DB connection (.env pattern)
- [ ] Add React frontend container to docker-compose
- [ ] Volume mounts for document storage

---

## 11.6 Reusability / Open Source

### 11.6.1 Design for Others
- [ ] Generic schema (not hardcoded to Stephen)
- [ ] Onboarding script: "load your resume" → parse → populate career_history + bullets
- [ ] Gmail connector with OAuth setup guide
- [ ] LinkedIn data import (from export CSV)
- [ ] Indeed/job board connectors
- [ ] Voice guide template (customizable banned words, style rules)
- [ ] Docker one-command setup (`docker-compose up`)

### 11.6.2 Documentation
- [ ] README with setup instructions
- [ ] API docs (Swagger/OpenAPI)
- [ ] Schema migration guide
- [ ] Contributing guide

---

## 11.7 Code Structure

```
code/
├── db/
│   ├── migrations/          # SQL migration scripts (001_initial.sql, etc.)
│   ├── seeds/               # Seed data scripts
│   ├── dumps/               # DB backup dumps
│   └── schema.sql           # Full schema reference
├── backend/
│   ├── app.py               # Flask app entry point
│   ├── config.py            # Configuration
│   ├── models/              # SQLAlchemy models
│   ├── routes/              # API route handlers
│   ├── etl/                 # Data loaders and parsers
│   ├── cron/                # Scheduled jobs
│   ├── rag/                 # Embedding generation, semantic search
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/           # Dashboard, Tracker, Builder, etc.
│   │   ├── api/             # API client
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── mcp/
│   ├── server.py            # MCP server implementation
│   ├── tools.py             # Tool definitions
│   └── Dockerfile
├── utils/                   # Shared/generic utilities (NOT user-specific scripts)
│   ├── docx_parser.py       # Generic DOCX reading
│   ├── pdf_parser.py        # Generic PDF reading
│   ├── resume_generator.py  # Resume generation from DB data
│   └── embedding_utils.py   # Embedding generation helpers
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── CODE.md                  # Developer guide
```

---

## 11.8 Implementation Phases

### 11.8.1 Database + ETL — DONE (Sessions 2-4)
- [x] Postgres DB with pgvector (Docker, port 5555)
- [x] Schema: 5 migrations (001_initial, 002_seed, 003_content, 004_resume_gen, 005_template_placeholders) -> 18 tables
- [x] 10 ETL loaders (KB, companies, apps, contacts, emails, documents, interviews, content_sections, voice_rules, salary_benchmarks)
- [x] Analytics views (funnel, source effectiveness, monthly activity)
- [ ] Generate embeddings (deferred)

### 11.8.2 Flask API + MCP Server — DONE (Sessions 2-4)
- [x] Flask API: full CRUD, search, analytics, gap analysis, content, voice rules, salary (port 8055)
- [x] MCP server: 20 tools via SSE (port 8056)
- [x] Docker: 2 containers (db + app), docker-compose, .env config
- [x] Claude Code integration: SKILLS + CLAUDE.md rewritten for MCP
- [ ] Resume generation endpoint
- [ ] Cron job framework

### 11.8.3 Backend Enhancements — IN PROGRESS
- [x] Resume generation: placeholder template system (migration 005)
  - [x] `templatize_resume.py` — converts full .docx → placeholder template with {{SLOT}} markers
  - [x] `generate_resume.py` — fills placeholders from DB spec/header/education/certs
  - [x] Template map (JSONB) stores slot types, formatting rules, original text
  - [x] V32 Placeholder template stored in resume_templates (79 slots, 14 static)
  - [x] Bold-label formatting preserved (colon-split for bullets, pipe-split for edu/certs)
  - [x] 97.7% text match vs original (2 diffs = intentional curly→straight quote normalization)
- [ ] Flask endpoint: POST /api/resume/generate
- [ ] Cron: follow_up_check (flag stale applications)
- [ ] Cron: scan_gmail (auto-categorize new emails, update tracker)
- [ ] Cron: scan_indeed (run saved searches, auto-score)
- [ ] Open source prep: copy CLAUDE.md + skills to code/ for other users
- [ ] Vector embeddings for semantic search

### 11.8.4 Recipe-Based Resume Generation System
**Requirements:** [11.1_RECIPE_GENERATION_SYSTEM.md](11.1_RECIPE_GENERATION_SYSTEM.md) | **Schema:** [11_DB_SCHEMA.md](11_DB_SCHEMA.md) Section 6

Replaces inline text specs with pointer-based references so resumes become lightweight recipes
that assemble content from the knowledge base at generation time.

- [ ] Migration 006: resume_recipes table + career_links column
- [ ] `create_v32_recipe.py` — decompose V32 spec into recipe format
- [ ] `resolve_recipe()` in generate_resume.py — resolves references to content_map
- [ ] `--recipe-id` CLI path in generate_resume.py
- [ ] V32 recipe verified against text snapshot (0 diffs)
- [ ] V31 base + 3 variant recipes created and verified
- [ ] Integration tests (pytest, real DB, snapshot comparison)
- [ ] MCP tool: add recipe_id param to generate_resume
- [ ] Flask routes: recipe CRUD + recipe-based generation
- [ ] KB decomposition: parse content_sections into bullets/career_history (deferred)

### 11.8.5 Template Editor Architecture (Future — React Frontend)
Templates are self-describing via `template_map` JSONB:
- **Slot types**: header, headline, summary, highlight, keywords, job_header, job_title,
  job_intro, job_subtitle, job_bullet, additional_exp, education, certification,
  ref_header, ref_link, section_header, spacer
- **Formatting rules per slot**: bold, bold_label (colon or pipe separator),
  size_pt, Word style (e.g., List Paragraph)
- **Generic job blocks**: JOB_1..JOB_N (not employer-specific), spec maps employers to slots
- **Template editor flow**: drag sections → name slots → set formatting → save as new template
- **Generation flow**: template blob + spec + header/edu/certs → filled .docx

### 11.8.6 React Frontend
- [ ] Dashboard (pipeline overview, trends, upcoming interviews)
- [ ] Application tracker (table + kanban)
- [ ] Resume builder with JD matching and drag-drop bullets
- [ ] Template editor (drag-and-drop layout, named slots, formatting rules)
- [ ] Company research view with network check

### 11.8.7 Open Source / Reusability
- [ ] Generic schema (not hardcoded to one user)
- [ ] Onboarding flow ("load your resume" → parse → populate)
- [ ] OAuth setup guides (Gmail, LinkedIn)
- [ ] Documentation (README, API docs, schema guide)
- [ ] One-command Docker setup
