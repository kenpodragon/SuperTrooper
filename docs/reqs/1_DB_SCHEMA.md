# 1. Database Schema

Parent: [0_APPLICATION_REQUIREMENTS.md](0_APPLICATION_REQUIREMENTS.md) Section 1

All table definitions for the platform database.

---

## 1. Core Identity Tables

### `career_history`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `employer` | `VARCHAR(200)` | Company name. `NOT NULL`. |
| `title` | `VARCHAR(200)` | Job title. `NOT NULL`. |
| `start_date` | `DATE` | Role start date. Nullable. |
| `end_date` | `DATE` | Role end date. Nullable (null = current). |
| `location` | `VARCHAR(200)` | Office location. Nullable. |
| `industry` | `VARCHAR(100)` | Industry sector. Nullable. |
| `team_size` | `INTEGER` | Size of team managed. Nullable. |
| `budget_usd` | `NUMERIC(12,2)` | Budget responsibility. Nullable. |
| `revenue_impact` | `VARCHAR(200)` | Revenue impact description. Nullable. |
| `is_current` | `BOOLEAN` | Currently active role. Default `false`. |
| `linkedin_dates` | `VARCHAR(50)` | Authoritative dates from LinkedIn. Nullable. |
| `intro_text` | `TEXT` | Job intro paragraph for resume. Nullable. (Migration 004) |
| `career_links` | `JSONB` | Array of `{text, url, description}` proof/portfolio links. Nullable. (Migration 006) |
| `notes` | `TEXT` | Internal notes. Nullable. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |
| `updated_at` | `TIMESTAMP` | Default `NOW()`. |

### `bullets`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `career_history_id` | `INTEGER FK` | References `career_history.id`. Nullable (for standalone bullets). |
| `text` | `TEXT` | Bullet text. `NOT NULL`. |
| `type` | `VARCHAR(50)` | core, alternate, deep_cut, interview_only. Nullable. |
| `star_situation` | `TEXT` | STAR: Situation. Nullable. |
| `star_task` | `TEXT` | STAR: Task. Nullable. |
| `star_action` | `TEXT` | STAR: Action. Nullable. |
| `star_result` | `TEXT` | STAR: Result. Nullable. |
| `metrics_json` | `JSONB` | `{metric, measurement, methodology, confidence}`. Nullable. |
| `tags` | `TEXT[]` | Topic tags. e.g. `['leadership', 'AI/ML', 'defense']`. |
| `role_suitability` | `TEXT[]` | Which role types this bullet fits. e.g. `['CTO', 'VP Eng']`. |
| `industry_suitability` | `TEXT[]` | Which industries this resonates with. |
| `detail_recall` | `VARCHAR(20)` | Confidence: high, medium, low. Default `'high'`. |
| `source_file` | `VARCHAR(500)` | Where this bullet was extracted from. Nullable. |
| `embedding` | `vector(1536)` | pgvector embedding for RAG search. Nullable. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |

### `skills`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `name` | `VARCHAR(100)` | Skill name. `NOT NULL`. |
| `category` | `VARCHAR(50)` | language, framework, platform, methodology, tool. Nullable. |
| `proficiency` | `VARCHAR(20)` | expert, proficient, familiar. Nullable. |
| `last_used_year` | `INTEGER` | Last year this skill was used. Nullable. |
| `career_history_ids` | `INTEGER[]` | Which roles used this skill. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |

### `summary_variants`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `role_type` | `VARCHAR(50)` | CTO, VP Eng, Director, AI Architect, etc. `UNIQUE NOT NULL`. |
| `text` | `TEXT` | Full summary text. `NOT NULL`. |
| `embedding` | `vector(1536)` | pgvector embedding. Nullable. |
| `updated_at` | `TIMESTAMP` | Default `NOW()`. |

---

## 2. Job Search Pipeline Tables

### `companies`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `name` | `VARCHAR(200)` | Company name. `NOT NULL`. |
| `sector` | `VARCHAR(100)` | Industry sector. Nullable. |
| `hq_location` | `VARCHAR(200)` | HQ location. Nullable. |
| `size` | `VARCHAR(50)` | startup, mid-market, enterprise. Nullable. |
| `stage` | `VARCHAR(50)` | startup, growth, mature, Fortune 500. Nullable. |
| `fit_score` | `INTEGER` | Fit score 1-100. Nullable. |
| `priority` | `CHAR(1)` | A, B, C. Nullable. |
| `target_role` | `VARCHAR(200)` | Target role at this company. Nullable. |
| `resume_variant` | `VARCHAR(50)` | Which resume variant to use. Nullable. |
| `key_differentiator` | `TEXT` | Why Stephen fits here. Nullable. |
| `melbourne_relevant` | `VARCHAR(50)` | Melbourne FL relevance. Nullable. |
| `comp_range` | `VARCHAR(100)` | Compensation range. Nullable. |
| `notes` | `TEXT` | Internal notes. Nullable. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |
| `updated_at` | `TIMESTAMP` | Default `NOW()`. |

### `applications`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `company_id` | `INTEGER FK` | References `companies.id`. Nullable. |
| `company_name` | `VARCHAR(200)` | Denormalized company name. |
| `role` | `VARCHAR(200)` | Role applied for. |
| `date_applied` | `DATE` | Date of application. |
| `source` | `VARCHAR(50)` | Indeed, LinkedIn, Dice, Direct, Recruiter, Referral. |
| `status` | `VARCHAR(50)` | Saved, Applied, Phone Screen, Interview, Technical, Final, Offer, Accepted, Rejected, Ghosted, Withdrawn, Rescinded. |
| `resume_version` | `VARCHAR(100)` | Which resume was used. |
| `cover_letter_path` | `VARCHAR(500)` | Path to cover letter. Nullable. |
| `jd_text` | `TEXT` | Job description text. Nullable. |
| `jd_url` | `VARCHAR(500)` | Job posting URL. Nullable. |
| `jd_embedding` | `vector(1536)` | JD embedding for bullet matching. Nullable. |
| `contact_name` | `VARCHAR(200)` | Primary contact. Nullable. |
| `contact_email` | `VARCHAR(200)` | Contact email. Nullable. |
| `notes` | `TEXT` | Internal notes. Nullable. |
| `last_status_change` | `TIMESTAMP` | Last status update. Nullable. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |
| `updated_at` | `TIMESTAMP` | Default `NOW()`. |

### `interviews`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `application_id` | `INTEGER FK` | References `applications.id`. |
| `date` | `TIMESTAMP` | Interview date/time. |
| `type` | `VARCHAR(50)` | phone, video, onsite, technical, panel, final. |
| `interviewers` | `TEXT[]` | Interviewer names. |
| `calendar_event_id` | `VARCHAR(200)` | Google Calendar event ID. Nullable. |
| `outcome` | `VARCHAR(50)` | passed, failed, pending, ghosted. |
| `feedback` | `TEXT` | Interview feedback. Nullable. |
| `thank_you_sent` | `BOOLEAN` | Default `false`. |
| `notes` | `TEXT` | Nullable. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |

### `contacts`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `name` | `VARCHAR(200)` | Contact name. `NOT NULL`. |
| `company` | `VARCHAR(200)` | Company they work at. Nullable. |
| `title` | `VARCHAR(200)` | Job title. Nullable. |
| `relationship` | `VARCHAR(50)` | recruiter, hiring_manager, peer, referral, reference, connection. |
| `email` | `VARCHAR(200)` | Nullable. |
| `phone` | `VARCHAR(50)` | Nullable. |
| `linkedin_url` | `VARCHAR(500)` | Nullable. |
| `relationship_strength` | `VARCHAR(20)` | strong, warm, cold, stale. |
| `last_contact` | `DATE` | Last interaction date. Nullable. |
| `source` | `VARCHAR(50)` | gmail, linkedin, archive, manual. |
| `notes` | `TEXT` | Nullable. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |
| `updated_at` | `TIMESTAMP` | Default `NOW()`. |

---

## 3. Email & Document Tables

### `emails`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `gmail_id` | `VARCHAR(50)` | Gmail message ID. `UNIQUE`. |
| `thread_id` | `VARCHAR(50)` | Gmail thread ID. |
| `date` | `TIMESTAMP` | Email date. |
| `from_address` | `VARCHAR(200)` | Sender email. |
| `from_name` | `VARCHAR(200)` | Sender display name. |
| `to_address` | `VARCHAR(200)` | Recipient email. |
| `subject` | `TEXT` | Email subject. |
| `snippet` | `TEXT` | Preview snippet. |
| `body` | `TEXT` | Full email body. |
| `category` | `VARCHAR(50)` | application, rejection, interview, recruiter, reference, other. |
| `application_id` | `INTEGER FK` | References `applications.id`. Nullable. |
| `labels` | `TEXT[]` | Gmail labels. |
| `embedding` | `vector(1536)` | Nullable. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |

### `documents`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `path` | `VARCHAR(500)` | File path. `NOT NULL`. |
| `filename` | `VARCHAR(200)` | File name. |
| `type` | `VARCHAR(50)` | resume, cover_letter, coaching, reference_letter, questionnaire, transcript. |
| `content_text` | `TEXT` | Extracted text content. Nullable. |
| `content_hash` | `VARCHAR(64)` | SHA-256 for dedup. Nullable. |
| `version` | `VARCHAR(50)` | Document version. Nullable. |
| `variant` | `VARCHAR(50)` | Document variant. Nullable. |
| `extracted_date` | `DATE` | Nullable. |
| `embedding` | `vector(1536)` | Nullable. |
| `metadata_json` | `JSONB` | Nullable. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |

### `resume_versions`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `version` | `VARCHAR(20)` | v32, v31, etc. |
| `variant` | `VARCHAR(50)` | base, AI Architect, SW Architect, PM, Simplified. |
| `docx_path` | `VARCHAR(500)` | Path to .docx file. Nullable. |
| `pdf_path` | `VARCHAR(500)` | Path to .pdf file. Nullable. |
| `summary` | `TEXT` | Description. Nullable. |
| `target_role_type` | `VARCHAR(50)` | Which role type this targets. Nullable. |
| `document_id` | `INTEGER FK` | References `documents.id`. `UNIQUE`. Nullable. |
| `is_current` | `BOOLEAN` | Default `false`. |
| `spec` | `JSONB` | Legacy text-based resume spec. Nullable. (Migration 004) |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |

---

## 4. Content & Knowledge Tables (Migration 003)

### `content_sections`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `source_document` | `VARCHAR(100)` | candidate_profile, voice_guide, salary_research, etc. `NOT NULL`. |
| `section` | `VARCHAR(200)` | Section heading. `NOT NULL`. |
| `subsection` | `VARCHAR(200)` | Subsection heading. Nullable. |
| `sort_order` | `INTEGER` | Display order. `NOT NULL DEFAULT 0`. |
| `content` | `TEXT` | Section content. `NOT NULL`. |
| `content_format` | `VARCHAR(20)` | Default `'markdown'`. |
| `tags` | `TEXT[]` | Topic tags. Nullable. |
| `metadata` | `JSONB` | Nullable. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |
| `updated_at` | `TIMESTAMP` | Default `NOW()`. |

### `voice_rules`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `part` | `INTEGER` | Voice Guide part 1-8. `NOT NULL`. |
| `part_title` | `VARCHAR(200)` | Part title. `NOT NULL`. |
| `category` | `VARCHAR(50)` | banned_word, banned_construction, etc. `NOT NULL`. |
| `subcategory` | `VARCHAR(100)` | Nullable. |
| `rule_text` | `TEXT` | The rule. `NOT NULL`. |
| `explanation` | `TEXT` | Why this rule exists. Nullable. |
| `examples_bad` | `TEXT[]` | Bad examples. Nullable. |
| `examples_good` | `TEXT[]` | Good examples. Nullable. |
| `sort_order` | `INTEGER` | `NOT NULL DEFAULT 0`. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |

### `salary_benchmarks`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `role_title` | `VARCHAR(200)` | Role name. `NOT NULL`. |
| `tier` | `INTEGER` | Tier level. `NOT NULL`. |
| `tier_name` | `VARCHAR(100)` | Tier description. `NOT NULL`. |
| `national_median_range` | `VARCHAR(100)` | National salary range. |
| `melbourne_range` | `VARCHAR(100)` | Melbourne FL adjusted range. |
| `remote_range` | `VARCHAR(100)` | Remote salary range. |
| `hcol_range` | `VARCHAR(100)` | High cost of living range. |
| `target_realistic` | `TEXT` | Realistic target. |
| `sort_order` | `INTEGER` | `NOT NULL DEFAULT 0`. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |

### `cola_markets`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `market_name` | `VARCHAR(100)` | Market name. `NOT NULL`. |
| `col_index_approx` | `VARCHAR(20)` | Cost of living index. |
| `cola_factor` | `NUMERIC(4,2)` | COLA multiplier. |
| `melbourne_200k_equiv` | `INTEGER` | $200K Melbourne equivalent. |
| `melbourne_250k_equiv` | `INTEGER` | $250K Melbourne equivalent. |
| `notes` | `TEXT` | Nullable. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |

---

## 5. Resume Templates & Generation (Migrations 004-005)

### `resume_templates`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `name` | `VARCHAR(100)` | Template name. `NOT NULL`. |
| `filename` | `VARCHAR(200)` | Original filename. Nullable. |
| `template_blob` | `BYTEA` | The .docx template file. `NOT NULL`. |
| `description` | `TEXT` | Nullable. |
| `is_active` | `BOOLEAN` | Default `true`. |
| `template_map` | `JSONB` | Slot types, formatting rules, original_text. Nullable. (Migration 005) |
| `template_type` | `VARCHAR(20)` | 'full' or 'placeholder'. Default `'full'`. (Migration 005) |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |
| `updated_at` | `TIMESTAMP` | Default `NOW()`. |

### `resume_header`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `full_name` | `VARCHAR(200)` | Candidate name. `NOT NULL`. |
| `credentials` | `VARCHAR(200)` | Credential suffixes (PhD, MBA, etc.). |
| `location` | `VARCHAR(200)` | Location. |
| `location_note` | `VARCHAR(200)` | Location qualifier (e.g. "Open to Remote"). |
| `email` | `VARCHAR(200)` | Contact email. |
| `phone` | `VARCHAR(50)` | Contact phone. |
| `linkedin_url` | `VARCHAR(500)` | LinkedIn profile URL. |

### `education`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `degree` | `VARCHAR(200)` | Degree name. `NOT NULL`. |
| `field` | `VARCHAR(200)` | Field of study. Nullable. |
| `institution` | `VARCHAR(200)` | School name. Nullable. |
| `location` | `VARCHAR(200)` | School location. Nullable. |
| `sort_order` | `INTEGER` | Display order. Default `0`. |

### `certifications`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `name` | `VARCHAR(200)` | Certification name. `NOT NULL`. |
| `issuer` | `VARCHAR(200)` | Issuing body. Nullable. |
| `is_active` | `BOOLEAN` | Default `true`. |
| `sort_order` | `INTEGER` | Display order. Default `0`. |

---

## 6. Resume Recipes (Migration 006)

### `resume_recipes`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `name` | `VARCHAR(200)` | Recipe name (e.g. "V32 AI Architect - Optum"). `NOT NULL`. |
| `description` | `TEXT` | What this recipe is for. Nullable. |
| `headline` | `TEXT` | Recipe-specific resume headline. First-class column for querying. Nullable. |
| `template_id` | `INTEGER FK` | References `resume_templates.id`. `NOT NULL`. |
| `recipe` | `JSONB` | Slot-to-source mapping. `NOT NULL`. See [3.3_RESUME_GENERATION.md](3.3_RESUME_GENERATION.md). |
| `application_id` | `INTEGER FK` | References `applications.id`. `ON DELETE SET NULL`. Nullable. |
| `is_active` | `BOOLEAN` | Default `true`. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |
| `updated_at` | `TIMESTAMP` | Default `NOW()`. |

---

## 7. Planned Tables (Not Yet Created)

### `saved_jobs` (Section 4.1)
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `url` | `VARCHAR(500)` | Job posting URL. |
| `title` | `VARCHAR(200)` | Job title. |
| `company_name` | `VARCHAR(200)` | Company name (denormalized). |
| `company_id` | `INTEGER FK` | References `companies.id`. Nullable. |
| `location` | `VARCHAR(200)` | Job location. |
| `salary_range` | `VARCHAR(100)` | Posted salary range. Nullable. |
| `source` | `VARCHAR(50)` | Indeed, LinkedIn, Dice, etc. |
| `jd_text` | `TEXT` | Job description text. |
| `fit_score` | `INTEGER` | Quick fit score 1-100. Nullable. |
| `status` | `VARCHAR(50)` | saved, evaluating, applying, passed. |
| `notes` | `TEXT` | Nullable. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |
| `updated_at` | `TIMESTAMP` | Default `NOW()`. |

### `gap_analyses` (Section 5.2)
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `application_id` | `INTEGER FK` | References `applications.id`. Nullable. |
| `saved_job_id` | `INTEGER FK` | References `saved_jobs.id`. Nullable. |
| `jd_parsed` | `JSONB` | Structured parsed JD (must-have skills, experience, education, etc.). |
| `strong_matches` | `JSONB` | Array of {bullet_id, evidence, score}. |
| `partial_matches` | `JSONB` | Array of {requirement, bridge_strategy}. |
| `gaps` | `JSONB` | Array of {requirement, mitigation}. |
| `bonus_value` | `JSONB` | Array of extra value points. |
| `fit_scores` | `JSONB` | {technical, leadership, industry, culture} each X/10. |
| `recommendation` | `VARCHAR(50)` | Strong Apply, Apply with Tailoring, Stretch, Pass. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |

### `application_status_history` (Section 6.1)
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `application_id` | `INTEGER FK` | References `applications.id`. `NOT NULL`. |
| `old_status` | `VARCHAR(50)` | Previous status. Nullable (first entry). |
| `new_status` | `VARCHAR(50)` | New status. `NOT NULL`. |
| `changed_at` | `TIMESTAMP` | Default `NOW()`. |
| `notes` | `TEXT` | Reason for change. Nullable. |

### `generated_materials` (Section 6.1)
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `application_id` | `INTEGER FK` | References `applications.id`. `NOT NULL`. |
| `type` | `VARCHAR(50)` | resume, cover_letter, outreach, thank_you. |
| `recipe_id` | `INTEGER FK` | References `resume_recipes.id`. Nullable. |
| `file_path` | `VARCHAR(500)` | Path to generated file. |
| `generated_at` | `TIMESTAMP` | Default `NOW()`. |
| `notes` | `TEXT` | Nullable. |

### `follow_ups` (Section 6.3)
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `application_id` | `INTEGER FK` | References `applications.id`. `NOT NULL`. |
| `attempt_number` | `INTEGER` | 1, 2, 3, etc. |
| `date_sent` | `TIMESTAMP` | When follow-up was sent. |
| `method` | `VARCHAR(50)` | email, linkedin, phone. |
| `response_received` | `BOOLEAN` | Default `false`. |
| `notes` | `TEXT` | Nullable. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |

### `interview_prep` (Section 8.2)
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `interview_id` | `INTEGER FK` | References `interviews.id`. `NOT NULL`. |
| `company_dossier` | `JSONB` | Cached company research. |
| `prepared_questions` | `JSONB` | Questions to ask the interviewer. |
| `talking_points` | `JSONB` | Key points to mention. |
| `star_stories` | `JSONB` | Array of bullet_ids selected for this interview. |
| `notes` | `TEXT` | Nullable. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |

### `interview_debriefs` (Section 8.3)
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `interview_id` | `INTEGER FK` | References `interviews.id`. `NOT NULL`. |
| `went_well` | `TEXT` | What went well. |
| `went_poorly` | `TEXT` | What didn't go well. |
| `questions_asked` | `JSONB` | Array of questions they asked. |
| `answers_given` | `JSONB` | How you answered (with quality notes). |
| `next_steps` | `TEXT` | What was agreed as next steps. |
| `overall_feeling` | `VARCHAR(20)` | confident, neutral, concerned. |
| `lessons_learned` | `TEXT` | What to do differently next time. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |

### `outreach_messages` (Section 9.1)
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `contact_id` | `INTEGER FK` | References `contacts.id`. `NOT NULL`. |
| `application_id` | `INTEGER FK` | References `applications.id`. Nullable. |
| `channel` | `VARCHAR(50)` | email, linkedin, phone. |
| `direction` | `VARCHAR(10)` | sent, received. |
| `subject` | `VARCHAR(500)` | Message subject. Nullable. |
| `body` | `TEXT` | Message content. |
| `sent_at` | `TIMESTAMP` | Default `NOW()`. |
| `response_received` | `BOOLEAN` | Default `false`. |
| `notes` | `TEXT` | Nullable. |

### `referrals` (Section 9.1)
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `contact_id` | `INTEGER FK` | References `contacts.id`. `NOT NULL`. |
| `application_id` | `INTEGER FK` | References `applications.id`. Nullable. |
| `saved_job_id` | `INTEGER FK` | References `saved_jobs.id`. Nullable. |
| `referral_date` | `DATE` | When the referral was made. |
| `status` | `VARCHAR(50)` | requested, submitted, acknowledged. |
| `notes` | `TEXT` | Nullable. |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |

### `activity_log` (Section 1.1)
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PK` | Auto-incrementing primary key. |
| `entity_type` | `VARCHAR(50)` | application, recipe, contact, bullet, etc. |
| `entity_id` | `INTEGER` | ID of the entity changed. |
| `action` | `VARCHAR(50)` | created, updated, deleted, generated, sent. |
| `details` | `JSONB` | What changed (old/new values, context). |
| `created_at` | `TIMESTAMP` | Default `NOW()`. |

### Schema changes to existing tables
- `contacts`: add `company_id INTEGER FK REFERENCES companies(id)` (currently VARCHAR only)
- `applications`: add `saved_job_id INTEGER FK REFERENCES saved_jobs(id)` (link to evaluation queue)
- `applications`: add `gap_analysis_id INTEGER FK REFERENCES gap_analyses(id)` (link to analysis)

---

## 8. Analytics Views

### `application_funnel`
Application counts by status with percentage of total.

### `source_effectiveness`
Response rate and interview rate by application source.

### `monthly_activity`
Monthly counts of applications, interviews, rejections, ghosted, offers.

---

## Migration History

| # | Name | Tables/Changes |
|---|------|----------------|
| 001 | initial | career_history, bullets, skills, summary_variants, companies, applications, interviews, contacts, emails, documents, resume_versions, analytics views |
| 002 | seed | Initial data load |
| 003 | content_tables | content_sections, voice_rules, salary_benchmarks, cola_markets |
| 004 | resume_generation | resume_templates, resume_header, education, certifications, resume_versions.spec, career_history.intro_text |
| 005 | template_placeholders | resume_templates.template_map, resume_templates.template_type |
| 006 | resume_recipes | resume_recipes, career_history.career_links |
