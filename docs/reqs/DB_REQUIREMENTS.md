# DB_REQUIREMENTS.md — Hiring Platform Backend

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

## 1. Database Schema

### 1.1 Core Identity

```sql
-- Career history (employer records)
CREATE TABLE career_history (
    id SERIAL PRIMARY KEY,
    employer VARCHAR(200) NOT NULL,
    title VARCHAR(200) NOT NULL,
    start_date DATE,
    end_date DATE,
    location VARCHAR(200),
    industry VARCHAR(100),
    team_size INTEGER,
    budget_usd NUMERIC(12,2),
    revenue_impact VARCHAR(200),
    is_current BOOLEAN DEFAULT FALSE,
    linkedin_dates VARCHAR(50),  -- authoritative dates from LinkedIn
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Resume bullets (the atomic unit of the Knowledge Base)
CREATE TABLE bullets (
    id SERIAL PRIMARY KEY,
    career_history_id INTEGER REFERENCES career_history(id),
    text TEXT NOT NULL,
    type VARCHAR(50),  -- core, alternate, deep_cut, interview_only
    star_situation TEXT,
    star_task TEXT,
    star_action TEXT,
    star_result TEXT,
    metrics_json JSONB,  -- {"metric": "$380M", "measurement": "inventory reduction", "methodology": "...", "confidence": "high"}
    tags TEXT[],  -- ['leadership', 'AI/ML', 'defense', 'scale']
    role_suitability TEXT[],  -- ['CTO', 'VP Eng', 'Director']
    industry_suitability TEXT[],  -- ['defense', 'manufacturing']
    detail_recall VARCHAR(20) DEFAULT 'high',  -- high, medium, low
    source_file VARCHAR(500),
    embedding vector(1536),  -- pgvector for RAG
    created_at TIMESTAMP DEFAULT NOW()
);

-- Skills and technologies
CREATE TABLE skills (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50),  -- language, framework, platform, methodology, tool
    proficiency VARCHAR(20),  -- expert, proficient, familiar
    last_used_year INTEGER,
    career_history_ids INTEGER[],  -- which roles used this skill
    created_at TIMESTAMP DEFAULT NOW()
);

-- Professional summary variants
CREATE TABLE summary_variants (
    id SERIAL PRIMARY KEY,
    role_type VARCHAR(50) NOT NULL,  -- CTO, VP Eng, Director, AI Architect, SW Architect, PM, Sr SWE
    text TEXT NOT NULL,
    embedding vector(1536),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 1.2 Job Search Pipeline

```sql
-- Target companies
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    sector VARCHAR(100),
    hq_location VARCHAR(200),
    size VARCHAR(50),  -- startup, mid-market, enterprise
    stage VARCHAR(50),  -- startup, growth, mature, Fortune 500
    fit_score INTEGER,
    priority CHAR(1),  -- A, B, C
    target_role VARCHAR(200),
    resume_variant VARCHAR(50),
    key_differentiator TEXT,
    melbourne_relevant VARCHAR(50),
    comp_range VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Applications
CREATE TABLE applications (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    company_name VARCHAR(200),  -- denormalized for easy access
    role VARCHAR(200),
    date_applied DATE,
    source VARCHAR(50),  -- Indeed, LinkedIn, Dice, ZipRecruiter, Direct, Recruiter, Referral
    status VARCHAR(50),  -- Saved, Applied, Phone Screen, Interview, Technical, Final, Offer, Accepted, Rejected, Ghosted, Withdrawn, Rescinded
    resume_version VARCHAR(100),
    cover_letter_path VARCHAR(500),
    jd_text TEXT,
    jd_url VARCHAR(500),
    jd_embedding vector(1536),  -- for matching against bullets
    contact_name VARCHAR(200),
    contact_email VARCHAR(200),
    notes TEXT,
    last_status_change TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Interviews
CREATE TABLE interviews (
    id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES applications(id),
    date TIMESTAMP,
    type VARCHAR(50),  -- phone, video, onsite, technical, panel, final
    interviewers TEXT[],
    calendar_event_id VARCHAR(200),
    outcome VARCHAR(50),  -- passed, failed, pending, ghosted
    feedback TEXT,
    thank_you_sent BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Contacts / Network
CREATE TABLE contacts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    company VARCHAR(200),
    title VARCHAR(200),
    relationship VARCHAR(50),  -- recruiter, hiring_manager, peer, referral, reference, connection
    email VARCHAR(200),
    phone VARCHAR(50),
    linkedin_url VARCHAR(500),
    relationship_strength VARCHAR(20),  -- strong, warm, cold, stale
    last_contact DATE,
    source VARCHAR(50),  -- gmail, linkedin, archive, manual
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 1.3 Email & Document Store

```sql
-- Emails (parsed from Gmail)
CREATE TABLE emails (
    id SERIAL PRIMARY KEY,
    gmail_id VARCHAR(50) UNIQUE,
    thread_id VARCHAR(50),
    date TIMESTAMP,
    from_address VARCHAR(200),
    from_name VARCHAR(200),
    to_address VARCHAR(200),
    subject TEXT,
    snippet TEXT,
    body TEXT,
    category VARCHAR(50),  -- application, rejection, interview, recruiter, reference, other
    application_id INTEGER REFERENCES applications(id),
    labels TEXT[],
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Documents (resumes, cover letters, coaching materials, etc.)
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    path VARCHAR(500) NOT NULL,
    filename VARCHAR(200),
    type VARCHAR(50),  -- resume, cover_letter, coaching, reference_letter, questionnaire, transcript
    content_text TEXT,
    content_hash VARCHAR(64),  -- SHA-256 for dedup
    version VARCHAR(50),
    variant VARCHAR(50),
    extracted_date DATE,
    embedding vector(1536),
    metadata_json JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Resume versions
CREATE TABLE resume_versions (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20),  -- v32, v31, etc.
    variant VARCHAR(50),  -- base, AI Architect, SW Architect, PM, Simplified
    docx_path VARCHAR(500),
    pdf_path VARCHAR(500),
    summary TEXT,
    target_role_type VARCHAR(50),
    document_id INTEGER REFERENCES documents(id),
    is_current BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 1.4 Content & Knowledge Tables (Migration 003)

```sql
-- Content sections — generic document store for full reconstruction + querying
CREATE TABLE content_sections (
    id SERIAL PRIMARY KEY,
    source_document VARCHAR(100) NOT NULL,   -- candidate_profile, voice_guide, salary_research, etc.
    section VARCHAR(200) NOT NULL,
    subsection VARCHAR(200),
    sort_order INTEGER NOT NULL DEFAULT 0,
    content TEXT NOT NULL,
    content_format VARCHAR(20) DEFAULT 'markdown',
    tags TEXT[],
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Voice rules — structured rules for content generation validation
CREATE TABLE voice_rules (
    id SERIAL PRIMARY KEY,
    part INTEGER NOT NULL,                   -- 1-8 maps to Voice Guide parts
    part_title VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL,           -- banned_word, banned_construction, etc.
    subcategory VARCHAR(100),
    rule_text TEXT NOT NULL,
    explanation TEXT,
    examples_bad TEXT[],
    examples_good TEXT[],
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Salary benchmarks — role-by-role salary data
CREATE TABLE salary_benchmarks (
    id SERIAL PRIMARY KEY,
    role_title VARCHAR(200) NOT NULL,
    tier INTEGER NOT NULL,
    tier_name VARCHAR(100) NOT NULL,
    national_median_range VARCHAR(100),
    melbourne_range VARCHAR(100),
    remote_range VARCHAR(100),
    hcol_range VARCHAR(100),
    target_realistic TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- COLA markets — cost of living reference data
CREATE TABLE cola_markets (
    id SERIAL PRIMARY KEY,
    market_name VARCHAR(100) NOT NULL,
    col_index_approx VARCHAR(20),
    cola_factor NUMERIC(4,2),
    melbourne_200k_equiv INTEGER,
    melbourne_250k_equiv INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 1.5 Analytics Views

```sql
-- Application funnel
CREATE VIEW application_funnel AS
SELECT
    status,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as pct
FROM applications
GROUP BY status
ORDER BY CASE status
    WHEN 'Saved' THEN 1 WHEN 'Applied' THEN 2 WHEN 'Phone Screen' THEN 3
    WHEN 'Interview' THEN 4 WHEN 'Technical' THEN 5 WHEN 'Final' THEN 6
    WHEN 'Offer' THEN 7 WHEN 'Accepted' THEN 8
    ELSE 9 END;

-- Source effectiveness
CREATE VIEW source_effectiveness AS
SELECT
    source,
    COUNT(*) as total_apps,
    COUNT(*) FILTER (WHERE status IN ('Phone Screen','Interview','Technical','Final','Offer','Accepted')) as got_response,
    ROUND(COUNT(*) FILTER (WHERE status IN ('Phone Screen','Interview','Technical','Final','Offer','Accepted')) * 100.0 / NULLIF(COUNT(*), 0), 1) as response_rate_pct,
    COUNT(*) FILTER (WHERE status IN ('Interview','Technical','Final','Offer','Accepted')) as got_interview,
    ROUND(COUNT(*) FILTER (WHERE status IN ('Interview','Technical','Final','Offer','Accepted')) * 100.0 / NULLIF(COUNT(*), 0), 1) as interview_rate_pct
FROM applications
GROUP BY source
ORDER BY interview_rate_pct DESC NULLS LAST;

-- Monthly activity
CREATE VIEW monthly_activity AS
SELECT
    DATE_TRUNC('month', date_applied) as month,
    COUNT(*) as applications,
    COUNT(*) FILTER (WHERE status IN ('Interview','Technical','Final')) as interviews,
    COUNT(*) FILTER (WHERE status = 'Rejected') as rejections,
    COUNT(*) FILTER (WHERE status = 'Ghosted') as ghosted,
    COUNT(*) FILTER (WHERE status IN ('Offer','Rescinded')) as offers
FROM applications
GROUP BY DATE_TRUNC('month', date_applied)
ORDER BY month DESC;

-- Bullet search (semantic via pgvector)
-- Usage: SELECT text, 1 - (embedding <=> query_embedding) as similarity
-- FROM bullets ORDER BY embedding <=> query_embedding LIMIT 10;
```

---

## 2. ETL Pipelines

### 2.0 Load Order (Dependencies Matter)

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

### 2.1 Data Loaders
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

### 2.2 Cron Jobs
- [ ] `scan_gmail.py` — periodic Gmail scan for new application emails, auto-categorize, update tracker
- [ ] `scan_indeed.py` — run saved Indeed searches, find new postings, auto-score fit
- [ ] `check_calendar.py` — pull upcoming interviews from Google Calendar, prep materials
- [ ] `follow_up_check.py` — flag applications with no response after 7/14/21 days
- [ ] `refresh_companies.py` — check target companies for new job postings

### 2.3 RAG / Search
- [ ] `semantic_search.py` — "find me a bullet about X" queries against pgvector embeddings
- [ ] `jd_matcher.py` — given a JD, find best-matching bullets, generate gap analysis, suggest resume edits
- [ ] `story_finder.py` — given an interview question category, find best STAR stories
- [ ] `network_check.py` — given a company, check contacts table for warm intro paths

---

## 3. Flask API

### 3.1 Endpoints
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
- [ ] `POST /api/resume/generate` — generate tailored resume from bullets + JD
- [x] `GET /api/emails` — search/filter emails
- [x] `GET /api/content/<document>` — full document reconstruction from content_sections (supports ?format=text for markdown)
- [x] `GET /api/content` — list all available documents with section counts
- [x] `GET /api/voice-rules` — voice rules with category/part filtering (supports ?format=text)
- [x] `POST /api/voice-rules/check` — check text against banned words/constructions
- [x] `GET /api/salary-benchmarks` — salary benchmarks with role/tier filtering
- [x] `GET /api/cola-markets` — COLA market reference data

### 3.2 Auth & Config
- [x] Local-only for now (no auth needed — single user)
- [x] Config file for DB connection, API keys (embeddings), MCP server settings
- [x] Health check endpoint

---

## 4. React Frontend

### 4.1 Dashboard
- [ ] Pipeline overview (applications by status, weekly/monthly trends)
- [ ] Source effectiveness chart
- [ ] Upcoming interviews
- [ ] Stale applications needing follow-up
- [ ] Recent activity feed

### 4.2 Application Tracker
- [ ] Table view with sort/filter/search
- [ ] Kanban board view (columns = statuses)
- [ ] Click into application for full detail (JD, resume used, notes, emails, interviews)
- [ ] Quick-add new application
- [ ] Status change with timestamp

### 4.3 Resume Builder
- [ ] View/edit Knowledge Base bullets
- [ ] Drag-and-drop bullet selection for tailored resume
- [ ] JD paste → auto gap analysis → suggested bullets
- [ ] Preview generated resume
- [ ] Export to DOCX/PDF

### 4.4 Company Research
- [ ] Target company list with scores, contacts, engagement status
- [ ] Click into company for dossier (Indeed data, news, contacts, past applications)
- [ ] Network check ("do I know anyone here?")

### 4.5 Search & RAG
- [ ] Semantic search bar — "find stories about M&A integration"
- [ ] Interview prep mode — select question category, get matching STAR stories
- [ ] Email search with category filters

### 4.6 Contacts & Network
- [ ] Contact list with relationship strength, last contact
- [ ] Company cross-reference
- [ ] Follow-up reminders

---

## 5. MCP Server (Docker)

### 5.1 Purpose
Custom MCP server that gives Claude Code direct access to the database, replacing file-based workflows with structured queries.

### 5.2 Tools Exposed (20 total)

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

#### Future
- [ ] `generate_resume(application_id)` — generate tailored resume from bullets + JD

### 5.3 Docker Setup
- [x] Dockerfile for backend (Python + Flask + MCP combined)
- [x] docker-compose.yml: Postgres + pgvector (port 5555) + Flask/MCP backend (ports 8055/8056)
- [x] Volume mounts for DB persistence (local_code/db_data/)
- [x] Environment variables for DB connection (.env pattern)
- [ ] Add React frontend container to docker-compose
- [ ] Volume mounts for document storage

---

## 6. Reusability / Open Source

### 6.1 Design for Others
- [ ] Generic schema (not hardcoded to Stephen)
- [ ] Onboarding script: "load your resume" → parse → populate career_history + bullets
- [ ] Gmail connector with OAuth setup guide
- [ ] LinkedIn data import (from export CSV)
- [ ] Indeed/job board connectors
- [ ] Voice guide template (customizable banned words, style rules)
- [ ] Docker one-command setup (`docker-compose up`)

### 6.2 Documentation
- [ ] README with setup instructions
- [ ] API docs (Swagger/OpenAPI)
- [ ] Schema migration guide
- [ ] Contributing guide

---

## 7. Code Structure

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

## 8. Implementation Phases

### Phase 1: Database + ETL — DONE (Sessions 2-4)
- [x] Postgres DB with pgvector (Docker, port 5555)
- [x] Schema: 5 migrations (001_initial, 002_seed, 003_content, 004_resume_gen, 005_template_placeholders) → 18 tables
- [x] 10 ETL loaders (KB, companies, apps, contacts, emails, documents, interviews, content_sections, voice_rules, salary_benchmarks)
- [x] Analytics views (funnel, source effectiveness, monthly activity)
- [ ] Generate embeddings (deferred)

### Phase 2: Flask API + MCP Server — DONE (Sessions 2-4)
- [x] Flask API: full CRUD, search, analytics, gap analysis, content, voice rules, salary (port 8055)
- [x] MCP server: 20 tools via SSE (port 8056)
- [x] Docker: 2 containers (db + app), docker-compose, .env config
- [x] Claude Code integration: SKILLS + CLAUDE.md rewritten for MCP
- [ ] Resume generation endpoint
- [ ] Cron job framework

### Phase 3: Backend Enhancements — IN PROGRESS
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

### Phase 3.5: Spec De-Normalization (Recipe-Based Resume Specs)
Current V32 spec stores full text copies of bullets. Target: specs become **recipes**
referencing content by ID. Single source of truth for all content.

**Spec recipe format:**
```json
{
  "headline": "VP of Software Engineering...",
  "summary_variant_id": 3,
  "highlight_bullet_ids": [8, 26, 70, 28, 63],
  "job_blocks": [
    {"career_history_id": 3, "bullet_ids": [8, 9, 10, 11, 12]},
    {"career_history_id": 4, "bullet_ids": [26, 27, 28, 29, 30, 31]}
  ],
  "education_ids": [1, 2, 3, 4],
  "certification_ids": [1, 2, 3, 4, 5, 6, 7, 8],
  "keywords": ["..."],
  "executive_keywords": ["..."],
  "technical_keywords": ["..."]
}
```

**Benefits:**
- Hundreds of resume versions stored for near-zero space (just ID references)
- Edit a bullet once → every resume that references it updates
- Full version history of all 127+ resume_versions becomes queryable
- Enables "what bullets did I use for Company X?" analytics

**Work items:**
- [ ] `denormalize_specs.py` — convert existing text-based specs to ID references
  - Match spec bullet text to bullets table by fuzzy/exact match
  - Map career_history intro text, education, certs to their IDs
  - Preserve original text specs as `spec_legacy` JSONB for rollback
- [ ] Update `load_resume_data.py` to create recipe-format specs for new versions
- [ ] Update `generate_resume.py` to resolve ID references → text during generation
- [ ] Update `get_resume_data` MCP tool to hydrate recipe specs into full content
- [ ] Migration: add `spec_format` column to resume_versions ('text' vs 'recipe')

### Phase 3.6: Template Editor Architecture (Future — React Frontend)
Templates are self-describing via `template_map` JSONB:
- **Slot types**: header, headline, summary, highlight, keywords, job_header, job_title,
  job_intro, job_subtitle, job_bullet, additional_exp, education, certification,
  ref_header, ref_link, section_header, spacer
- **Formatting rules per slot**: bold, bold_label (colon or pipe separator),
  size_pt, Word style (e.g., List Paragraph)
- **Generic job blocks**: JOB_1..JOB_N (not employer-specific), spec maps employers to slots
- **Template editor flow**: drag sections → name slots → set formatting → save as new template
- **Generation flow**: template blob + spec + header/edu/certs → filled .docx

### Phase 4: React Frontend
- [ ] Dashboard (pipeline overview, trends, upcoming interviews)
- [ ] Application tracker (table + kanban)
- [ ] Resume builder with JD matching and drag-drop bullets
- [ ] Template editor (drag-and-drop layout, named slots, formatting rules)
- [ ] Company research view with network check

### Phase 5: Open Source / Reusability
- [ ] Generic schema (not hardcoded to one user)
- [ ] Onboarding flow ("load your resume" → parse → populate)
- [ ] OAuth setup guides (Gmail, LinkedIn)
- [ ] Documentation (README, API docs, schema guide)
- [ ] One-command Docker setup
