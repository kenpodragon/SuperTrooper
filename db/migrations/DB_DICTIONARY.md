# Database Dictionary — SuperTroopers

**Last updated:** 2026-03-19 (Session 4)
**Database:** PostgreSQL 17 + pgvector 0.8.2
**Connection:** localhost:5555, db=supertroopers, user=supertroopers

> **Keep this file in sync.** When you add/alter tables, columns, or views, update this dictionary. Reference it when designing new features or writing queries.

---

## Tables Overview

| Table | Rows | Migration | Purpose |
|-------|------|-----------|---------|
| career_history | 19 | 001 | Employer records with dates, industry, team size |
| bullets | 232 | 001 | Resume bullet atoms with STAR, tags, role/industry suitability |
| skills | 255 | 001+002 | Skills inventory with proficiency and category |
| summary_variants | 8 | 001 | Professional summaries by role type (CTO, VP Eng, etc.) |
| companies | 173 | 001 | Target companies with scoring, sector, priority |
| applications | 62 | 001 | Job application pipeline tracker |
| interviews | 38 | 001 | Individual interview events linked to applications |
| contacts | 26 | 001 | Professional network with relationship strength |
| emails | 7,215 | 001 | Parsed Gmail messages by category |
| documents | 134 | 001 | Indexed files (resumes, cover letters, coaching materials) |
| resume_versions | 127 | 001+004 | Resume version registry with spec JSONB |
| content_sections | 131 | 003 | Generic document store for full reconstruction |
| voice_rules | 173 | 003 | Voice guide rules for content generation validation |
| salary_benchmarks | 12 | 003 | Role-by-role salary ranges with COLA mapping |
| cola_markets | 7 | 003 | Cost of living reference data by market |
| resume_templates | 1 | 004 | .docx template blob storage |
| resume_header | 1 | 004 | Candidate contact info for resume headers |
| education | 4 | 004 | Degree and certificate entries |
| certifications | 8 | 004 | Professional certifications |
| schema_migrations | 4 | 001 | Migration version tracking |

## Views

| View | Purpose |
|------|---------|
| application_funnel | Status breakdown with counts and percentages |
| source_effectiveness | Application source → response/interview rates |
| monthly_activity | Monthly apps, interviews, rejections, ghosted, offers |

---

## Table Details

### career_history
Employer records. One row per job. Linked to bullets via career_history_id.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| employer | VARCHAR(200) | NO | Company name |
| title | VARCHAR(200) | NO | Job title |
| start_date | DATE | YES | |
| end_date | DATE | YES | NULL = current |
| location | VARCHAR(200) | YES | |
| industry | VARCHAR(100) | YES | |
| team_size | INTEGER | YES | |
| budget_usd | NUMERIC(12,2) | YES | |
| revenue_impact | VARCHAR(200) | YES | |
| is_current | BOOLEAN | YES | Default FALSE |
| linkedin_dates | VARCHAR(50) | YES | Authoritative dates from LinkedIn |
| intro_text | TEXT | YES | Resume job intro paragraph (added migration 004) |
| notes | TEXT | YES | |
| created_at | TIMESTAMP | YES | Default NOW() |
| updated_at | TIMESTAMP | YES | Default NOW() |

### bullets
Resume bullet atoms. The atomic unit of the Knowledge Base. Tagged for role/industry suitability.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| career_history_id | INTEGER FK | YES | → career_history(id) |
| text | TEXT | NO | The bullet text |
| type | VARCHAR(50) | YES | core, alternate, deep_cut, interview_only |
| star_situation | TEXT | YES | STAR framework |
| star_task | TEXT | YES | |
| star_action | TEXT | YES | |
| star_result | TEXT | YES | |
| metrics_json | JSONB | YES | {"metric": "$380M", "measurement": "...", "confidence": "high"} |
| tags | TEXT[] | YES | ['leadership', 'AI/ML', 'defense', 'scale'] |
| role_suitability | TEXT[] | YES | ['CTO', 'VP Eng', 'Director'] |
| industry_suitability | TEXT[] | YES | ['defense', 'manufacturing'] |
| detail_recall | VARCHAR(20) | YES | high, medium, low. Default 'high' |
| source_file | VARCHAR(500) | YES | |
| embedding | VECTOR(1536) | YES | pgvector for RAG (not yet populated) |
| created_at | TIMESTAMP | YES | Default NOW() |

### skills
Skills and technologies with proficiency levels.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| name | VARCHAR(100) | NO | |
| category | VARCHAR(50) | YES | language, framework, platform, methodology, tool |
| proficiency | VARCHAR(20) | YES | expert, proficient, familiar |
| last_used_year | INTEGER | YES | |
| career_history_ids | INTEGER[] | YES | Which roles used this skill |
| created_at | TIMESTAMP | YES | Default NOW() |

### summary_variants
Professional summary text by target role type.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| role_type | VARCHAR(50) | NO | CTO, VP Eng, Director, AI Architect, SW Architect, PM, Sr SWE |
| text | TEXT | NO | |
| embedding | VECTOR(1536) | YES | Not yet populated |
| updated_at | TIMESTAMP | YES | Default NOW() |

### companies
Target companies with fit scoring and engagement tracking.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| name | VARCHAR(200) | NO | UNIQUE constraint |
| sector | VARCHAR(100) | YES | |
| hq_location | VARCHAR(200) | YES | |
| size | VARCHAR(50) | YES | startup, mid-market, enterprise |
| stage | VARCHAR(50) | YES | startup, growth, mature, Fortune 500 |
| fit_score | INTEGER | YES | 1-10 |
| priority | CHAR(1) | YES | A, B, C |
| target_role | VARCHAR(200) | YES | |
| resume_variant | VARCHAR(50) | YES | |
| key_differentiator | TEXT | YES | |
| melbourne_relevant | VARCHAR(50) | YES | |
| comp_range | VARCHAR(100) | YES | |
| notes | TEXT | YES | |
| created_at | TIMESTAMP | YES | |
| updated_at | TIMESTAMP | YES | |

### applications
Job application pipeline tracker.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| company_id | INTEGER FK | YES | → companies(id) ON DELETE SET NULL |
| company_name | VARCHAR(200) | YES | Denormalized |
| role | VARCHAR(200) | YES | |
| date_applied | DATE | YES | |
| source | VARCHAR(50) | YES | Indeed, LinkedIn, Dice, ZipRecruiter, Direct, Recruiter, Referral |
| status | VARCHAR(50) | YES | Saved, Applied, Phone Screen, Interview, Technical, Final, Offer, Accepted, Rejected, Ghosted, Withdrawn, Rescinded |
| resume_version | VARCHAR(100) | YES | |
| cover_letter_path | VARCHAR(500) | YES | |
| jd_text | TEXT | YES | |
| jd_url | VARCHAR(500) | YES | |
| jd_embedding | VECTOR(1536) | YES | Not yet populated |
| contact_name | VARCHAR(200) | YES | |
| contact_email | VARCHAR(200) | YES | |
| notes | TEXT | YES | |
| last_status_change | TIMESTAMP | YES | |
| created_at | TIMESTAMP | YES | |
| updated_at | TIMESTAMP | YES | |

### interviews
Individual interview events linked to applications.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| application_id | INTEGER FK | YES | → applications(id) |
| date | TIMESTAMP | YES | |
| type | VARCHAR(50) | YES | phone, video, onsite, technical, panel, final |
| interviewers | TEXT[] | YES | |
| calendar_event_id | VARCHAR(200) | YES | |
| outcome | VARCHAR(50) | YES | passed, failed, pending, ghosted |
| feedback | TEXT | YES | |
| thank_you_sent | BOOLEAN | YES | Default FALSE |
| notes | TEXT | YES | |
| created_at | TIMESTAMP | YES | |

### contacts
Professional network with relationship tracking.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| name | VARCHAR(200) | NO | |
| company | VARCHAR(200) | YES | |
| title | VARCHAR(200) | YES | |
| relationship | VARCHAR(50) | YES | recruiter, hiring_manager, peer, referral, reference, connection |
| email | VARCHAR(200) | YES | |
| phone | VARCHAR(50) | YES | |
| linkedin_url | VARCHAR(500) | YES | |
| relationship_strength | VARCHAR(20) | YES | strong, warm, cold, stale |
| last_contact | DATE | YES | |
| source | VARCHAR(50) | YES | gmail, linkedin, archive, manual |
| notes | TEXT | YES | |
| created_at | TIMESTAMP | YES | |
| updated_at | TIMESTAMP | YES | |

### emails
Parsed Gmail messages categorized by type.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| gmail_id | VARCHAR(50) | YES | UNIQUE |
| thread_id | VARCHAR(50) | YES | |
| date | TIMESTAMP | YES | |
| from_address | VARCHAR(200) | YES | |
| from_name | VARCHAR(200) | YES | |
| to_address | VARCHAR(200) | YES | |
| subject | TEXT | YES | |
| snippet | TEXT | YES | |
| body | TEXT | YES | |
| category | VARCHAR(50) | YES | application, rejection, interview, recruiter, reference, other |
| application_id | INTEGER FK | YES | → applications(id) |
| labels | TEXT[] | YES | |
| embedding | VECTOR(1536) | YES | Not yet populated |
| created_at | TIMESTAMP | YES | |

### content_sections
Generic document section store. Supports full document reconstruction via sort_order.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| source_document | VARCHAR(100) | NO | candidate_profile, voice_guide, salary_research, rejection_analysis, application_history, email_scan_deep |
| section | VARCHAR(200) | NO | ## header text |
| subsection | VARCHAR(200) | YES | ### header text |
| sort_order | INTEGER | NO | Default 0. For reconstruction ordering |
| content | TEXT | NO | The actual content |
| content_format | VARCHAR(20) | YES | markdown, table, list. Default 'markdown' |
| tags | TEXT[] | YES | |
| metadata | JSONB | YES | |
| created_at | TIMESTAMP | YES | |
| updated_at | TIMESTAMP | YES | |

**Reconstruction query:** `SELECT content FROM content_sections WHERE source_document = 'X' ORDER BY sort_order`

### voice_rules
Structured rules from the Voice Guide for content generation validation.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| part | INTEGER | NO | 1-8 maps to Voice Guide parts |
| part_title | VARCHAR(200) | NO | "Banned Vocabulary", "Banned Constructions", etc. |
| category | VARCHAR(50) | NO | banned_word, banned_construction, caution_word, structural_tell, resume_rule, cover_letter_rule, final_check, quick_reference, linkedin_pattern, stephen_ism, context_pattern |
| subcategory | VARCHAR(100) | YES | e.g. buzzword_verb, false_authority, engagement_bait |
| rule_text | TEXT | NO | The rule/pattern text |
| explanation | TEXT | YES | Why it's banned/required |
| examples_bad | TEXT[] | YES | |
| examples_good | TEXT[] | YES | |
| sort_order | INTEGER | NO | Default 0 |
| created_at | TIMESTAMP | YES | |

### salary_benchmarks
Role-by-role salary ranges for target roles.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| role_title | VARCHAR(200) | NO | |
| tier | INTEGER | NO | 1=Executive, 2=Director, 3=Sr IC, 4=PM, 5=Academia |
| tier_name | VARCHAR(100) | NO | |
| national_median_range | VARCHAR(100) | YES | |
| melbourne_range | VARCHAR(100) | YES | |
| remote_range | VARCHAR(100) | YES | |
| hcol_range | VARCHAR(100) | YES | |
| target_realistic | TEXT | YES | Assessment text |
| sort_order | INTEGER | NO | Default 0 |
| created_at | TIMESTAMP | YES | |

### cola_markets
Cost of living reference data by market. Melbourne FL is baseline (1.00x).

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| market_name | VARCHAR(100) | NO | |
| col_index_approx | VARCHAR(20) | YES | |
| cola_factor | NUMERIC(4,2) | YES | 1.00 = Melbourne FL |
| melbourne_200k_equiv | INTEGER | YES | |
| melbourne_250k_equiv | INTEGER | YES | |
| notes | TEXT | YES | |
| created_at | TIMESTAMP | YES | |

**COLA formula:** Melbourne-equivalent = Posted Salary × (97 / Market COL Index)

### resume_templates
Stores .docx template blobs for resume generation.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| name | VARCHAR(100) | NO | "V32 Base" |
| filename | VARCHAR(200) | YES | |
| template_blob | BYTEA | NO | Raw .docx file |
| description | TEXT | YES | |
| is_active | BOOLEAN | YES | Default TRUE |
| created_at | TIMESTAMP | YES | |
| updated_at | TIMESTAMP | YES | |

### resume_header
Candidate contact info for resume headers. Single row per user.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| full_name | VARCHAR(200) | NO | |
| credentials | VARCHAR(200) | YES | "PhD, CSM, PMP, MBA" |
| location | VARCHAR(200) | YES | |
| location_note | VARCHAR(200) | YES | "Open to Relocate" |
| email | VARCHAR(200) | YES | |
| phone | VARCHAR(50) | YES | |
| linkedin_url | VARCHAR(500) | YES | |
| website_url | VARCHAR(500) | YES | |
| calendly_url | VARCHAR(500) | YES | |
| created_at | TIMESTAMP | YES | |
| updated_at | TIMESTAMP | YES | |

### education
Degree and certificate entries for resume education section.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| degree | VARCHAR(200) | NO | "PhD", "MBA", "BS" |
| field | VARCHAR(200) | YES | |
| institution | VARCHAR(200) | NO | |
| location | VARCHAR(200) | YES | |
| type | VARCHAR(50) | YES | degree, certificate, professional_development. Default 'degree' |
| sort_order | INTEGER | NO | Default 0 |
| created_at | TIMESTAMP | YES | |

### certifications
Professional certifications.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| name | VARCHAR(200) | NO | |
| issuer | VARCHAR(200) | YES | |
| is_active | BOOLEAN | YES | Default TRUE |
| sort_order | INTEGER | NO | Default 0 |
| created_at | TIMESTAMP | YES | |

### resume_versions
Resume version registry. The `spec` JSONB column maps which content goes where for reconstruction.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| version | VARCHAR(20) | YES | v32, v31 |
| variant | VARCHAR(50) | YES | base, AI Architect, SW Architect, PM, Simplified |
| docx_path | VARCHAR(500) | YES | |
| pdf_path | VARCHAR(500) | YES | |
| summary | TEXT | YES | |
| target_role_type | VARCHAR(50) | YES | |
| document_id | INTEGER FK | YES | → documents(id) |
| is_current | BOOLEAN | YES | Default FALSE |
| spec | JSONB | YES | Full reconstruction mapping (added migration 004) |
| created_at | TIMESTAMP | YES | |

**Spec JSONB structure:**
```json
{
  "headline": "VP of Software Engineering & Digital Transformation",
  "summary_text": "I build highly scalable...",
  "highlight_bullets": ["bullet text", ...],
  "keywords": ["Digital Transformation", ...],
  "experience_employers": ["MealMatch AI", "SMTC", ...],
  "experience_bullets": {"MealMatch AI": ["bullet 1", ...], ...},
  "additional_experience": ["one-liner 1", ...],
  "executive_keywords": [...],
  "technical_keywords": [...],
  "references": [{"section": "...", "links": [...]}]
}
```

### documents
Indexed files (resumes, cover letters, coaching materials).

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| path | VARCHAR(500) | NO | |
| filename | VARCHAR(200) | YES | |
| type | VARCHAR(50) | YES | resume, cover_letter, coaching, reference_letter, questionnaire, transcript |
| content_text | TEXT | YES | |
| content_hash | VARCHAR(64) | YES | SHA-256 for dedup |
| version | VARCHAR(50) | YES | |
| variant | VARCHAR(50) | YES | |
| extracted_date | DATE | YES | |
| embedding | VECTOR(1536) | YES | Not yet populated |
| metadata_json | JSONB | YES | |
| created_at | TIMESTAMP | YES | |

### schema_migrations
Migration version tracking.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| version | VARCHAR(20) | NO | PK |
| name | VARCHAR(200) | YES | |
| applied_at | TIMESTAMP | YES | Default NOW() |

---

## Migrations History

| Version | Name | Date | Changes |
|---------|------|------|---------|
| 1 | 001_initial | 2026-03-18 | 12 tables, 3 views, pgvector, indexes |
| 2 | 002_seed | 2026-03-18 | Seed data for skills |
| 3 | 003_content_tables | 2026-03-19 | content_sections, voice_rules, salary_benchmarks, cola_markets |
| 4 | 004_resume_generation | 2026-03-19 | resume_templates, resume_header, education, certifications + resume_versions.spec + career_history.intro_text |

---

## Key Relationships

```
career_history (1) ──── (N) bullets
companies (1) ──── (N) applications
applications (1) ──── (N) interviews
applications (1) ──── (N) emails
resume_versions (1) ──── (1) documents
resume_versions.spec ──→ references career_history, bullets by employer name
```

## Indexes

Key indexes beyond primary keys:
- `companies`: name (unique), sector, size, stage, fit_score, priority
- `content_sections`: source_document, (source_document + section), tags (GIN)
- `voice_rules`: part, category
- `bullets`: career_history_id, tags (GIN), role_suitability (GIN), industry_suitability (GIN)
- `emails`: gmail_id (unique), category, date, application_id
