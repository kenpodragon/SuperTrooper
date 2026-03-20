-- Migration 007: Platform Tables
-- Adds 10 new tables for saved jobs, gap analysis persistence, application
-- pipeline enhancements, interview prep/debrief, networking, and activity log.
-- Also adds FK columns to contacts and applications.

BEGIN;

-- ============================================================================
-- 1. Saved Jobs / Evaluation Queue (0_APP 4.1)
-- ============================================================================

CREATE TABLE IF NOT EXISTS saved_jobs (
    id              SERIAL PRIMARY KEY,
    url             VARCHAR(1000),
    title           VARCHAR(300) NOT NULL,
    company         VARCHAR(200),
    company_id      INTEGER REFERENCES companies(id) ON DELETE SET NULL,
    location        VARCHAR(200),
    salary_range    VARCHAR(100),
    source          VARCHAR(50),           -- indeed, linkedin, dice, manual, plugin
    jd_text         TEXT,
    jd_url          VARCHAR(1000),
    fit_score       NUMERIC(4,1),          -- 0.0-10.0
    status          VARCHAR(30) DEFAULT 'saved',  -- saved, evaluating, applying, applied, passed
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_saved_jobs_status ON saved_jobs(status);
CREATE INDEX idx_saved_jobs_company_id ON saved_jobs(company_id);
CREATE INDEX idx_saved_jobs_source ON saved_jobs(source);
CREATE INDEX idx_saved_jobs_fit_score ON saved_jobs(fit_score);
CREATE INDEX idx_saved_jobs_created_at ON saved_jobs(created_at);

CREATE TRIGGER trg_saved_jobs_updated_at
    BEFORE UPDATE ON saved_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 2. Gap Analyses (0_APP 5.2)
-- ============================================================================

CREATE TABLE IF NOT EXISTS gap_analyses (
    id                SERIAL PRIMARY KEY,
    application_id    INTEGER REFERENCES applications(id) ON DELETE SET NULL,
    saved_job_id      INTEGER REFERENCES saved_jobs(id) ON DELETE SET NULL,
    jd_text           TEXT,
    jd_parsed         JSONB,                -- structured JD breakdown by category
    strong_matches    JSONB,                -- [{skill, evidence, metric}]
    partial_matches   JSONB,                -- [{skill, bridge_strategy}]
    gaps              JSONB,                -- [{requirement, mitigation}]
    bonus_value       JSONB,                -- [{item, description}]
    fit_scores        JSONB,                -- {technical, leadership, industry, culture}
    overall_score     NUMERIC(4,1),         -- 0.0-10.0
    recommendation    VARCHAR(50),          -- strong_apply, apply_with_tailoring, stretch, pass
    notes             TEXT,
    created_at        TIMESTAMP DEFAULT NOW(),
    updated_at        TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_gap_analyses_application_id ON gap_analyses(application_id);
CREATE INDEX idx_gap_analyses_saved_job_id ON gap_analyses(saved_job_id);
CREATE INDEX idx_gap_analyses_recommendation ON gap_analyses(recommendation);
CREATE INDEX idx_gap_analyses_overall_score ON gap_analyses(overall_score);

CREATE TRIGGER trg_gap_analyses_updated_at
    BEFORE UPDATE ON gap_analyses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 3. Application Status History (0_APP 6.1)
-- ============================================================================

CREATE TABLE IF NOT EXISTS application_status_history (
    id              SERIAL PRIMARY KEY,
    application_id  INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    old_status      VARCHAR(50),
    new_status      VARCHAR(50) NOT NULL,
    changed_at      TIMESTAMP DEFAULT NOW(),
    notes           TEXT
);

CREATE INDEX idx_app_status_history_app_id ON application_status_history(application_id);
CREATE INDEX idx_app_status_history_changed_at ON application_status_history(changed_at);

-- ============================================================================
-- 4. Generated Materials (0_APP 6.1)
-- ============================================================================

CREATE TABLE IF NOT EXISTS generated_materials (
    id              SERIAL PRIMARY KEY,
    application_id  INTEGER REFERENCES applications(id) ON DELETE SET NULL,
    type            VARCHAR(50) NOT NULL,    -- resume, cover_letter, outreach, thank_you
    recipe_id       INTEGER REFERENCES resume_recipes(id) ON DELETE SET NULL,
    file_path       VARCHAR(500),
    file_blob       BYTEA,                   -- optional: store the file directly
    version_label   VARCHAR(100),            -- e.g. "v1", "tailored-2026-03-19"
    notes           TEXT,
    generated_at    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_generated_materials_app_id ON generated_materials(application_id);
CREATE INDEX idx_generated_materials_type ON generated_materials(type);
CREATE INDEX idx_generated_materials_recipe_id ON generated_materials(recipe_id);

-- ============================================================================
-- 5. Follow-Ups (0_APP 6.3)
-- ============================================================================

CREATE TABLE IF NOT EXISTS follow_ups (
    id                  SERIAL PRIMARY KEY,
    application_id      INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    attempt_number      INTEGER DEFAULT 1,
    date_sent           DATE,
    method              VARCHAR(30),          -- email, linkedin, phone
    response_received   BOOLEAN DEFAULT FALSE,
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_follow_ups_app_id ON follow_ups(application_id);
CREATE INDEX idx_follow_ups_date_sent ON follow_ups(date_sent);
CREATE INDEX idx_follow_ups_response ON follow_ups(response_received);

-- ============================================================================
-- 6. Interview Prep (0_APP 8.2)
-- ============================================================================

CREATE TABLE IF NOT EXISTS interview_prep (
    id                    SERIAL PRIMARY KEY,
    interview_id          INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    company_dossier       JSONB,              -- cached company research snapshot
    prepared_questions    JSONB,              -- [{question, suggested_answer, star_bullet_id}]
    talking_points        JSONB,              -- [{topic, notes}]
    star_stories_selected JSONB,              -- [{bullet_id, question_category}]
    questions_to_ask      JSONB,              -- [{question, why}]
    notes                 TEXT,
    created_at            TIMESTAMP DEFAULT NOW(),
    updated_at            TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_interview_prep_interview_id ON interview_prep(interview_id);

CREATE TRIGGER trg_interview_prep_updated_at
    BEFORE UPDATE ON interview_prep
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 7. Interview Debriefs (0_APP 8.3)
-- ============================================================================

CREATE TABLE IF NOT EXISTS interview_debriefs (
    id                SERIAL PRIMARY KEY,
    interview_id      INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    went_well         JSONB,                -- [{item, detail}]
    went_poorly       JSONB,                -- [{item, detail}]
    questions_asked   JSONB,                -- [{question, my_answer, quality: good/ok/weak}]
    next_steps        TEXT,
    overall_feeling   VARCHAR(30),          -- great, good, neutral, concerned, poor
    lessons_learned   TEXT,
    notes             TEXT,
    created_at        TIMESTAMP DEFAULT NOW(),
    updated_at        TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_interview_debriefs_interview_id ON interview_debriefs(interview_id);
CREATE INDEX idx_interview_debriefs_feeling ON interview_debriefs(overall_feeling);

CREATE TRIGGER trg_interview_debriefs_updated_at
    BEFORE UPDATE ON interview_debriefs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 8. Outreach Messages (0_APP 9.1)
-- ============================================================================

CREATE TABLE IF NOT EXISTS outreach_messages (
    id                  SERIAL PRIMARY KEY,
    contact_id          INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    application_id      INTEGER REFERENCES applications(id) ON DELETE SET NULL,
    interview_id        INTEGER REFERENCES interviews(id) ON DELETE SET NULL,
    channel             VARCHAR(30) NOT NULL,   -- email, linkedin, phone, other
    direction           VARCHAR(10) NOT NULL,   -- sent, received
    subject             VARCHAR(500),
    body                TEXT,
    sent_at             TIMESTAMP,
    response_received   BOOLEAN DEFAULT FALSE,
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_outreach_contact_id ON outreach_messages(contact_id);
CREATE INDEX idx_outreach_application_id ON outreach_messages(application_id);
CREATE INDEX idx_outreach_interview_id ON outreach_messages(interview_id);
CREATE INDEX idx_outreach_channel ON outreach_messages(channel);
CREATE INDEX idx_outreach_sent_at ON outreach_messages(sent_at);

-- ============================================================================
-- 9. Referrals (0_APP 9.1)
-- ============================================================================

CREATE TABLE IF NOT EXISTS referrals (
    id              SERIAL PRIMARY KEY,
    contact_id      INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    application_id  INTEGER REFERENCES applications(id) ON DELETE SET NULL,
    saved_job_id    INTEGER REFERENCES saved_jobs(id) ON DELETE SET NULL,
    referral_date   DATE,
    status          VARCHAR(30) DEFAULT 'pending',  -- pending, submitted, confirmed, declined
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_referrals_contact_id ON referrals(contact_id);
CREATE INDEX idx_referrals_application_id ON referrals(application_id);
CREATE INDEX idx_referrals_status ON referrals(status);

CREATE TRIGGER trg_referrals_updated_at
    BEFORE UPDATE ON referrals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 10. Activity Log (0_APP 1.1)
-- ============================================================================

CREATE TABLE IF NOT EXISTS activity_log (
    id              SERIAL PRIMARY KEY,
    action          VARCHAR(100) NOT NULL,     -- e.g. application_created, status_changed, resume_generated
    entity_type     VARCHAR(50),               -- application, contact, recipe, interview, etc.
    entity_id       INTEGER,
    details         JSONB,                     -- action-specific payload
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_activity_log_action ON activity_log(action);
CREATE INDEX idx_activity_log_entity ON activity_log(entity_type, entity_id);
CREATE INDEX idx_activity_log_created_at ON activity_log(created_at);

-- ============================================================================
-- FK Changes to Existing Tables
-- ============================================================================

-- contacts: add company_id FK (currently company is VARCHAR, not linked)
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_company_id ON contacts(company_id);

-- applications: add saved_job_id FK (came from evaluation queue)
ALTER TABLE applications ADD COLUMN IF NOT EXISTS saved_job_id INTEGER REFERENCES saved_jobs(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_applications_saved_job_id ON applications(saved_job_id);

-- applications: add gap_analysis_id FK (linked gap analysis)
ALTER TABLE applications ADD COLUMN IF NOT EXISTS gap_analysis_id INTEGER REFERENCES gap_analyses(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_applications_gap_analysis_id ON applications(gap_analysis_id);

-- ============================================================================
-- Track Migration
-- ============================================================================

INSERT INTO schema_migrations (version, name)
VALUES ('007', '007_platform_tables')
ON CONFLICT DO NOTHING;

COMMIT;
