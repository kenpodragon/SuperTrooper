# Database Dictionary — SuperTroopers

**Last updated:** 2026-03-23 (Session 8)
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
| resume_templates | 4 | 004+005 | .docx template blob + template_map JSONB |
| resume_header | 1 | 004 | Candidate contact info for resume headers |
| education | 4 | 004 | Degree and certificate entries |
| certifications | 8 | 004 | Professional certifications |
| resume_recipes | 5 | 006 | Recipe-based resume assembly (slot -> {table,id,column}) |
| saved_jobs | 0 | 007 | Job evaluation queue before applying |
| gap_analyses | 0 | 007 | Persisted gap analysis results |
| application_status_history | 0 | 007 | Auto-logged status transitions |
| generated_materials | 0 | 007 | Track resumes/cover letters generated per application |
| follow_ups | 0 | 007 | Follow-up attempts per application |
| interview_prep | 0 | 007 | Company-specific interview prep materials |
| interview_debriefs | 0 | 007 | Structured post-interview capture |
| outreach_messages | 7,324 | 007 | Sent/received messages across channels |
| referrals | 0 | 007 | Contact referrals to jobs |
| activity_log | 0 | 007 | Action audit trail |
| linkedin_scraped_posts | 819 | 028 | Scraped LinkedIn posts with engagement metrics |
| linkedin_scraped_comments | 1,821 | 028 | Stephen's comments on others' LinkedIn posts |
| schema_migrations | 7 | 001 | Migration version tracking |

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
| saved_job_id | INTEGER FK | YES | → saved_jobs(id) ON DELETE SET NULL (added 007) |
| gap_analysis_id | INTEGER FK | YES | → gap_analyses(id) ON DELETE SET NULL (added 007) |
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
| company | VARCHAR(200) | YES | Denormalized company name |
| company_id | INTEGER FK | YES | → companies(id) ON DELETE SET NULL (added 007) |
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

### saved_jobs
Job evaluation queue. Jobs saved for review before deciding to apply.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| url | VARCHAR(1000) | YES | Job posting URL |
| title | VARCHAR(300) | NO | |
| company | VARCHAR(200) | YES | |
| company_id | INTEGER FK | YES | → companies(id) |
| location | VARCHAR(200) | YES | |
| salary_range | VARCHAR(100) | YES | |
| source | VARCHAR(50) | YES | indeed, linkedin, dice, manual, plugin |
| jd_text | TEXT | YES | Full job description |
| jd_url | VARCHAR(1000) | YES | |
| fit_score | NUMERIC(4,1) | YES | 0.0-10.0 |
| status | VARCHAR(30) | YES | saved, evaluating, applying, applied, passed |
| notes | TEXT | YES | |
| created_at | TIMESTAMP | YES | |
| updated_at | TIMESTAMP | YES | |

### gap_analyses
Persisted gap analysis results linked to application or saved job.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| application_id | INTEGER FK | YES | → applications(id) |
| saved_job_id | INTEGER FK | YES | → saved_jobs(id) |
| jd_text | TEXT | YES | Raw JD text analyzed |
| jd_parsed | JSONB | YES | Structured JD breakdown by category |
| strong_matches | JSONB | YES | [{skill, evidence, metric}] |
| partial_matches | JSONB | YES | [{skill, bridge_strategy}] |
| gaps | JSONB | YES | [{requirement, mitigation}] |
| bonus_value | JSONB | YES | [{item, description}] |
| fit_scores | JSONB | YES | {technical, leadership, industry, culture} |
| overall_score | NUMERIC(4,1) | YES | 0.0-10.0 |
| recommendation | VARCHAR(50) | YES | strong_apply, apply_with_tailoring, stretch, pass |
| notes | TEXT | YES | |
| created_at | TIMESTAMP | YES | |
| updated_at | TIMESTAMP | YES | |

### application_status_history
Auto-logged status transitions for applications.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| application_id | INTEGER FK | NO | → applications(id) ON DELETE CASCADE |
| old_status | VARCHAR(50) | YES | NULL on first entry |
| new_status | VARCHAR(50) | NO | |
| changed_at | TIMESTAMP | YES | Default NOW() |
| notes | TEXT | YES | |

### generated_materials
Track resumes, cover letters, and other materials generated per application.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| application_id | INTEGER FK | YES | → applications(id) |
| type | VARCHAR(50) | NO | resume, cover_letter, outreach, thank_you |
| recipe_id | INTEGER FK | YES | → resume_recipes(id) |
| file_path | VARCHAR(500) | YES | |
| file_blob | BYTEA | YES | Optional inline storage |
| version_label | VARCHAR(100) | YES | e.g. "v1", "tailored-2026-03-19" |
| notes | TEXT | YES | |
| generated_at | TIMESTAMP | YES | Default NOW() |

### follow_ups
Follow-up attempts per application.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| application_id | INTEGER FK | NO | → applications(id) ON DELETE CASCADE |
| attempt_number | INTEGER | YES | Default 1 |
| date_sent | DATE | YES | |
| method | VARCHAR(30) | YES | email, linkedin, phone |
| response_received | BOOLEAN | YES | Default FALSE |
| notes | TEXT | YES | |
| created_at | TIMESTAMP | YES | |

### interview_prep
Company-specific interview preparation materials.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| interview_id | INTEGER FK | NO | → interviews(id) ON DELETE CASCADE |
| company_dossier | JSONB | YES | Cached company research snapshot |
| prepared_questions | JSONB | YES | [{question, suggested_answer, star_bullet_id}] |
| talking_points | JSONB | YES | [{topic, notes}] |
| star_stories_selected | JSONB | YES | [{bullet_id, question_category}] |
| questions_to_ask | JSONB | YES | [{question, why}] |
| notes | TEXT | YES | |
| created_at | TIMESTAMP | YES | |
| updated_at | TIMESTAMP | YES | |

### interview_debriefs
Structured post-interview capture.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| interview_id | INTEGER FK | NO | → interviews(id) ON DELETE CASCADE |
| went_well | JSONB | YES | [{item, detail}] |
| went_poorly | JSONB | YES | [{item, detail}] |
| questions_asked | JSONB | YES | [{question, my_answer, quality}] |
| next_steps | TEXT | YES | |
| overall_feeling | VARCHAR(30) | YES | great, good, neutral, concerned, poor |
| lessons_learned | TEXT | YES | |
| notes | TEXT | YES | |
| created_at | TIMESTAMP | YES | |
| updated_at | TIMESTAMP | YES | |

### outreach_messages
Sent/received messages across channels (email, LinkedIn, phone).

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| contact_id | INTEGER FK | YES | → contacts(id) |
| application_id | INTEGER FK | YES | → applications(id) |
| interview_id | INTEGER FK | YES | → interviews(id) — for thank-you notes |
| channel | VARCHAR(30) | NO | email, linkedin, phone, other |
| direction | VARCHAR(10) | NO | sent, received |
| subject | VARCHAR(500) | YES | |
| body | TEXT | YES | |
| sent_at | TIMESTAMP | YES | |
| response_received | BOOLEAN | YES | Default FALSE |
| notes | TEXT | YES | |
| created_at | TIMESTAMP | YES | |

### referrals
Track "contact A referred me to job B".

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| contact_id | INTEGER FK | NO | → contacts(id) ON DELETE CASCADE |
| application_id | INTEGER FK | YES | → applications(id) |
| saved_job_id | INTEGER FK | YES | → saved_jobs(id) |
| referral_date | DATE | YES | |
| status | VARCHAR(30) | YES | pending, submitted, confirmed, declined |
| notes | TEXT | YES | |
| created_at | TIMESTAMP | YES | |
| updated_at | TIMESTAMP | YES | |

### activity_log
Action audit trail for the platform.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| action | VARCHAR(100) | NO | e.g. application_created, status_changed, resume_generated |
| entity_type | VARCHAR(50) | YES | application, contact, recipe, interview, etc. |
| entity_id | INTEGER | YES | |
| details | JSONB | YES | Action-specific payload |
| created_at | TIMESTAMP | YES | Default NOW() |

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
| 5 | 005_template_placeholders | 2026-03-19 | resume_templates.template_map + template_type |
| 6 | 006_resume_recipes | 2026-03-19 | resume_recipes + career_history.career_links |
| 7 | 007_platform_tables | 2026-03-19 | 10 new tables (saved_jobs, gap_analyses, application_status_history, generated_materials, follow_ups, interview_prep, interview_debriefs, outreach_messages, referrals, activity_log) + FK columns on contacts (company_id) and applications (saved_job_id, gap_analysis_id) |
| 28 | 028_linkedin_scraped | 2026-03-23 | linkedin_scraped_posts, linkedin_scraped_comments with URN dedup indexes |

### linkedin_scraped_posts
Scraped LinkedIn posts from browser scraper. Deduped by URN.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| urn | TEXT | YES | UNIQUE dedup key (urn:li:activity:XXX) |
| text | TEXT | YES | Post content |
| post_type | VARCHAR(30) | YES | Default 'text' |
| likes | INTEGER | YES | Default 0 |
| comments | INTEGER | YES | Default 0 |
| reposts | INTEGER | YES | Default 0 |
| media_files | JSONB | YES | Default '[]' |
| url | TEXT | YES | LinkedIn post URL |
| original_author | TEXT | YES | Non-null for reposts |
| posted_at | TIMESTAMPTZ | YES | |
| imported_at | TIMESTAMP | YES | Default NOW() |

### linkedin_scraped_comments
Stephen's comments on others' LinkedIn posts. Deduped by URN.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | SERIAL PK | NO | |
| original_author | TEXT | YES | Author of the post commented on |
| original_snippet | TEXT | YES | First ~200 chars of original post |
| original_post_url | TEXT | YES | |
| comment_text | TEXT | YES | Stephen's comment |
| comment_url | TEXT | YES | |
| urn | TEXT | YES | UNIQUE dedup key |
| commented_at | TIMESTAMPTZ | YES | |
| imported_at | TIMESTAMP | YES | Default NOW() |

---

## Key Relationships

```
career_history (1) ──── (N) bullets
companies (1) ──── (N) applications
companies (1) ──── (N) contacts (via company_id)
companies (1) ──── (N) saved_jobs (via company_id)
saved_jobs (1) ──── (N) applications (via saved_job_id)
saved_jobs (1) ──── (N) gap_analyses (via saved_job_id)
saved_jobs (1) ──── (N) referrals (via saved_job_id)
applications (1) ──── (N) interviews
applications (1) ──── (N) emails
applications (1) ──── (N) application_status_history
applications (1) ──── (N) generated_materials
applications (1) ──── (N) follow_ups
applications (1) ──── (N) gap_analyses
applications (1) ──── (N) outreach_messages
applications (1) ──── (N) referrals
interviews (1) ──── (1) interview_prep
interviews (1) ──── (1) interview_debriefs
interviews (1) ──── (N) outreach_messages (thank-you notes)
contacts (1) ──── (N) outreach_messages
contacts (1) ──── (N) referrals
resume_recipes (1) ──── (N) generated_materials
resume_versions (1) ──── (1) documents
resume_versions.spec ──→ references career_history, bullets by employer name
linkedin_scraped_posts ──→ bridged into linkedin_posts (via url = linkedin_url)
linkedin_scraped_posts ──→ bridged into linkedin_post_engagement (via post_id)
```

## Indexes

Key indexes beyond primary keys:
- `companies`: name (unique), sector, size, stage, fit_score, priority
- `content_sections`: source_document, (source_document + section), tags (GIN)
- `voice_rules`: part, category
- `bullets`: career_history_id, tags (GIN), role_suitability (GIN), industry_suitability (GIN)
- `emails`: gmail_id (unique), category, date, application_id
- `linkedin_scraped_posts`: urn (unique), posted_at DESC
- `linkedin_scraped_comments`: urn (unique), commented_at DESC
