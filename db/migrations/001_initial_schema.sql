-- ============================================================================
-- Migration 001: Initial Schema for Supertroopers (Hiring 2026 Platform)
-- Created: 2026-03-18
-- Requires: PostgreSQL 15+, pgvector extension
-- ============================================================================

-- Create the database if it doesn't exist (run this block as a superuser
-- connected to the 'postgres' database BEFORE running the rest of this script).
-- After creating the DB, reconnect to 'supertroopers' and run everything below.
--
-- DO $$
-- BEGIN
--     IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'supertroopers') THEN
--         PERFORM dblink_exec('dbname=postgres', 'CREATE DATABASE supertroopers');
--     END IF;
-- END
-- $$;
--
-- NOTE: CREATE DATABASE cannot run inside a transaction. Use the helper script
-- or run manually:
--   CREATE DATABASE supertroopers;
-- Then connect to it and run this migration.

-- ============================================================================
-- Everything below runs inside a transaction against the 'supertroopers' DB
-- ============================================================================
BEGIN;

-- ----------------------------------------------------------------------------
-- Extensions
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;  -- pgvector for embeddings

-- ----------------------------------------------------------------------------
-- Utility: auto-update updated_at timestamp trigger
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_updated_at_column() IS
    'Trigger function that auto-sets updated_at to NOW() on row update.';

-- ============================================================================
-- 1.1 Core Identity
-- ============================================================================

-- ---------- career_history ----------
CREATE TABLE career_history (
    id              SERIAL PRIMARY KEY,
    employer        VARCHAR(200)    NOT NULL,
    title           VARCHAR(200)    NOT NULL,
    start_date      DATE,
    end_date        DATE,
    location        VARCHAR(200),
    industry        VARCHAR(100),
    team_size       INTEGER,
    budget_usd      NUMERIC(12, 2),
    revenue_impact  VARCHAR(200),
    is_current      BOOLEAN         DEFAULT FALSE,
    linkedin_dates  VARCHAR(50),
    notes           TEXT,
    created_at      TIMESTAMP       DEFAULT NOW(),
    updated_at      TIMESTAMP       DEFAULT NOW()
);

COMMENT ON TABLE career_history IS 'Employer records from the candidate career timeline.';
COMMENT ON COLUMN career_history.linkedin_dates IS 'Authoritative date range as shown on LinkedIn profile.';
COMMENT ON COLUMN career_history.is_current IS 'TRUE if this is the current/most recent position.';

CREATE INDEX idx_career_history_employer   ON career_history (employer);
CREATE INDEX idx_career_history_industry   ON career_history (industry);
CREATE INDEX idx_career_history_is_current ON career_history (is_current);
CREATE INDEX idx_career_history_start_date ON career_history (start_date);

CREATE TRIGGER trg_career_history_updated_at
    BEFORE UPDATE ON career_history
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ---------- bullets ----------
CREATE TABLE bullets (
    id                  SERIAL PRIMARY KEY,
    career_history_id   INTEGER         REFERENCES career_history(id) ON DELETE SET NULL,
    text                TEXT            NOT NULL,
    type                VARCHAR(50),
    star_situation      TEXT,
    star_task           TEXT,
    star_action         TEXT,
    star_result         TEXT,
    metrics_json        JSONB,
    tags                TEXT[],
    role_suitability    TEXT[],
    industry_suitability TEXT[],
    detail_recall       VARCHAR(20)     DEFAULT 'high',
    source_file         VARCHAR(500),
    embedding           vector(1536),
    created_at          TIMESTAMP       DEFAULT NOW()
);

COMMENT ON TABLE bullets IS 'Atomic resume bullets from the Knowledge Base. The core unit of resume generation.';
COMMENT ON COLUMN bullets.type IS 'Bullet classification: core, alternate, deep_cut, interview_only.';
COMMENT ON COLUMN bullets.metrics_json IS 'Structured metric data: {"metric": "$380M", "measurement": "inventory reduction", "methodology": "...", "confidence": "high"}.';
COMMENT ON COLUMN bullets.detail_recall IS 'How well the candidate can recall details in an interview: high, medium, low.';
COMMENT ON COLUMN bullets.embedding IS '1536-dim vector embedding for semantic (RAG) search.';

CREATE INDEX idx_bullets_career_history_id ON bullets (career_history_id);
CREATE INDEX idx_bullets_type              ON bullets (type);
CREATE INDEX idx_bullets_detail_recall     ON bullets (detail_recall);
CREATE INDEX idx_bullets_tags              ON bullets USING GIN (tags);
CREATE INDEX idx_bullets_role_suitability  ON bullets USING GIN (role_suitability);
CREATE INDEX idx_bullets_industry_suit     ON bullets USING GIN (industry_suitability);
CREATE INDEX idx_bullets_metrics_json      ON bullets USING GIN (metrics_json);

-- HNSW index for fast approximate nearest-neighbor on bullet embeddings
-- m=16, ef_construction=64 are good defaults for <100k rows
CREATE INDEX idx_bullets_embedding ON bullets
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ---------- skills ----------
CREATE TABLE skills (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(100)    NOT NULL,
    category            VARCHAR(50),
    proficiency         VARCHAR(20),
    last_used_year      INTEGER,
    career_history_ids  INTEGER[],
    created_at          TIMESTAMP       DEFAULT NOW()
);

COMMENT ON TABLE skills IS 'Skills and technologies with proficiency levels.';
COMMENT ON COLUMN skills.category IS 'Skill type: language, framework, platform, methodology, tool.';
COMMENT ON COLUMN skills.proficiency IS 'Proficiency level: expert, proficient, familiar.';
COMMENT ON COLUMN skills.career_history_ids IS 'Array of career_history IDs where this skill was used.';

CREATE INDEX idx_skills_name           ON skills (name);
CREATE INDEX idx_skills_category       ON skills (category);
CREATE INDEX idx_skills_proficiency    ON skills (proficiency);
CREATE INDEX idx_skills_last_used_year ON skills (last_used_year);
CREATE INDEX idx_skills_career_ids     ON skills USING GIN (career_history_ids);

-- ---------- summary_variants ----------
CREATE TABLE summary_variants (
    id              SERIAL PRIMARY KEY,
    role_type       VARCHAR(50)     NOT NULL,
    text            TEXT            NOT NULL,
    embedding       vector(1536),
    updated_at      TIMESTAMP       DEFAULT NOW()
);

COMMENT ON TABLE summary_variants IS 'Professional summary text variants, one per target role type.';
COMMENT ON COLUMN summary_variants.role_type IS 'Target role: CTO, VP Eng, Director, AI Architect, SW Architect, PM, Sr SWE.';

CREATE INDEX idx_summary_variants_role_type ON summary_variants (role_type);

CREATE INDEX idx_summary_variants_embedding ON summary_variants
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE TRIGGER trg_summary_variants_updated_at
    BEFORE UPDATE ON summary_variants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 1.2 Job Search Pipeline
-- ============================================================================

-- ---------- companies ----------
CREATE TABLE companies (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(200)    NOT NULL,
    sector              VARCHAR(100),
    hq_location         VARCHAR(200),
    size                VARCHAR(50),
    stage               VARCHAR(50),
    fit_score           INTEGER,
    priority            CHAR(1),
    target_role         VARCHAR(200),
    resume_variant      VARCHAR(50),
    key_differentiator  TEXT,
    melbourne_relevant  VARCHAR(50),
    comp_range          VARCHAR(100),
    notes               TEXT,
    created_at          TIMESTAMP       DEFAULT NOW(),
    updated_at          TIMESTAMP       DEFAULT NOW()
);

COMMENT ON TABLE companies IS 'Target companies for the job search pipeline.';
COMMENT ON COLUMN companies.size IS 'Company size bucket: startup, mid-market, enterprise.';
COMMENT ON COLUMN companies.stage IS 'Company maturity: startup, growth, mature, Fortune 500.';
COMMENT ON COLUMN companies.priority IS 'Priority tier: A (top), B, C.';
COMMENT ON COLUMN companies.fit_score IS 'Calculated fit score (0-100).';
COMMENT ON COLUMN companies.melbourne_relevant IS 'Whether the company has Melbourne FL presence or remote-friendly.';

CREATE INDEX idx_companies_name      ON companies (name);
CREATE INDEX idx_companies_sector    ON companies (sector);
CREATE INDEX idx_companies_size      ON companies (size);
CREATE INDEX idx_companies_stage     ON companies (stage);
CREATE INDEX idx_companies_priority  ON companies (priority);
CREATE INDEX idx_companies_fit_score ON companies (fit_score);

CREATE TRIGGER trg_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ---------- applications ----------
CREATE TABLE applications (
    id                  SERIAL PRIMARY KEY,
    company_id          INTEGER         REFERENCES companies(id) ON DELETE SET NULL,
    company_name        VARCHAR(200),
    role                VARCHAR(200),
    date_applied        DATE,
    source              VARCHAR(50),
    status              VARCHAR(50),
    resume_version      VARCHAR(100),
    cover_letter_path   VARCHAR(500),
    jd_text             TEXT,
    jd_url              VARCHAR(500),
    jd_embedding        vector(1536),
    contact_name        VARCHAR(200),
    contact_email       VARCHAR(200),
    notes               TEXT,
    last_status_change  TIMESTAMP,
    created_at          TIMESTAMP       DEFAULT NOW(),
    updated_at          TIMESTAMP       DEFAULT NOW()
);

COMMENT ON TABLE applications IS 'Job applications with status tracking and JD embeddings for matching.';
COMMENT ON COLUMN applications.company_name IS 'Denormalized company name for quick access without joins.';
COMMENT ON COLUMN applications.source IS 'Application source: Indeed, LinkedIn, Dice, ZipRecruiter, Direct, Recruiter, Referral.';
COMMENT ON COLUMN applications.status IS 'Pipeline status: Saved, Applied, Phone Screen, Interview, Technical, Final, Offer, Accepted, Rejected, Ghosted, Withdrawn, Rescinded.';
COMMENT ON COLUMN applications.jd_embedding IS '1536-dim embedding of the job description for bullet matching.';

CREATE INDEX idx_applications_company_id        ON applications (company_id);
CREATE INDEX idx_applications_company_name      ON applications (company_name);
CREATE INDEX idx_applications_status            ON applications (status);
CREATE INDEX idx_applications_source            ON applications (source);
CREATE INDEX idx_applications_date_applied      ON applications (date_applied);
CREATE INDEX idx_applications_last_status_change ON applications (last_status_change);

CREATE INDEX idx_applications_jd_embedding ON applications
    USING hnsw (jd_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE TRIGGER trg_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ---------- interviews ----------
CREATE TABLE interviews (
    id                  SERIAL PRIMARY KEY,
    application_id      INTEGER         REFERENCES applications(id) ON DELETE CASCADE,
    date                TIMESTAMP,
    type                VARCHAR(50),
    interviewers        TEXT[],
    calendar_event_id   VARCHAR(200),
    outcome             VARCHAR(50),
    feedback            TEXT,
    thank_you_sent      BOOLEAN         DEFAULT FALSE,
    notes               TEXT,
    created_at          TIMESTAMP       DEFAULT NOW()
);

COMMENT ON TABLE interviews IS 'Individual interview events linked to applications.';
COMMENT ON COLUMN interviews.type IS 'Interview format: phone, video, onsite, technical, panel, final.';
COMMENT ON COLUMN interviews.outcome IS 'Result: passed, failed, pending, ghosted.';

CREATE INDEX idx_interviews_application_id ON interviews (application_id);
CREATE INDEX idx_interviews_date           ON interviews (date);
CREATE INDEX idx_interviews_type           ON interviews (type);
CREATE INDEX idx_interviews_outcome        ON interviews (outcome);
CREATE INDEX idx_interviews_thank_you_sent ON interviews (thank_you_sent);
CREATE INDEX idx_interviews_interviewers   ON interviews USING GIN (interviewers);

-- ---------- contacts ----------
CREATE TABLE contacts (
    id                      SERIAL PRIMARY KEY,
    name                    VARCHAR(200)    NOT NULL,
    company                 VARCHAR(200),
    title                   VARCHAR(200),
    relationship            VARCHAR(50),
    email                   VARCHAR(200),
    phone                   VARCHAR(50),
    linkedin_url            VARCHAR(500),
    relationship_strength   VARCHAR(20),
    last_contact            DATE,
    source                  VARCHAR(50),
    notes                   TEXT,
    created_at              TIMESTAMP       DEFAULT NOW(),
    updated_at              TIMESTAMP       DEFAULT NOW()
);

COMMENT ON TABLE contacts IS 'Professional network contacts for warm intros and referrals.';
COMMENT ON COLUMN contacts.relationship IS 'Contact type: recruiter, hiring_manager, peer, referral, reference, connection.';
COMMENT ON COLUMN contacts.relationship_strength IS 'Strength: strong, warm, cold, stale.';
COMMENT ON COLUMN contacts.source IS 'Where contact was sourced: gmail, linkedin, archive, manual.';

CREATE INDEX idx_contacts_name                  ON contacts (name);
CREATE INDEX idx_contacts_company               ON contacts (company);
CREATE INDEX idx_contacts_relationship          ON contacts (relationship);
CREATE INDEX idx_contacts_relationship_strength ON contacts (relationship_strength);
CREATE INDEX idx_contacts_last_contact          ON contacts (last_contact);
CREATE INDEX idx_contacts_source                ON contacts (source);

CREATE TRIGGER trg_contacts_updated_at
    BEFORE UPDATE ON contacts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 1.3 Email & Document Store
-- ============================================================================

-- ---------- emails ----------
CREATE TABLE emails (
    id              SERIAL PRIMARY KEY,
    gmail_id        VARCHAR(50)     UNIQUE,
    thread_id       VARCHAR(50),
    date            TIMESTAMP,
    from_address    VARCHAR(200),
    from_name       VARCHAR(200),
    to_address      VARCHAR(200),
    subject         TEXT,
    snippet         TEXT,
    body            TEXT,
    category        VARCHAR(50),
    application_id  INTEGER         REFERENCES applications(id) ON DELETE SET NULL,
    labels          TEXT[],
    embedding       vector(1536),
    created_at      TIMESTAMP       DEFAULT NOW()
);

COMMENT ON TABLE emails IS 'Parsed Gmail messages linked to applications for tracking and search.';
COMMENT ON COLUMN emails.gmail_id IS 'Unique Gmail message ID for dedup.';
COMMENT ON COLUMN emails.category IS 'Email classification: application, rejection, interview, recruiter, reference, other.';

CREATE INDEX idx_emails_gmail_id       ON emails (gmail_id);
CREATE INDEX idx_emails_thread_id      ON emails (thread_id);
CREATE INDEX idx_emails_date           ON emails (date);
CREATE INDEX idx_emails_from_address   ON emails (from_address);
CREATE INDEX idx_emails_category       ON emails (category);
CREATE INDEX idx_emails_application_id ON emails (application_id);
CREATE INDEX idx_emails_labels         ON emails USING GIN (labels);

CREATE INDEX idx_emails_embedding ON emails
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ---------- documents ----------
CREATE TABLE documents (
    id              SERIAL PRIMARY KEY,
    path            VARCHAR(500)    NOT NULL,
    filename        VARCHAR(200),
    type            VARCHAR(50),
    content_text    TEXT,
    content_hash    VARCHAR(64),
    version         VARCHAR(50),
    variant         VARCHAR(50),
    extracted_date  DATE,
    embedding       vector(1536),
    metadata_json   JSONB,
    created_at      TIMESTAMP       DEFAULT NOW()
);

COMMENT ON TABLE documents IS 'Indexed documents: resumes, cover letters, coaching materials, transcripts, etc.';
COMMENT ON COLUMN documents.type IS 'Document type: resume, cover_letter, coaching, reference_letter, questionnaire, transcript.';
COMMENT ON COLUMN documents.content_hash IS 'SHA-256 hash of content_text for deduplication.';

CREATE INDEX idx_documents_type          ON documents (type);
CREATE INDEX idx_documents_content_hash  ON documents (content_hash);
CREATE INDEX idx_documents_version       ON documents (version);
CREATE INDEX idx_documents_variant       ON documents (variant);
CREATE INDEX idx_documents_extracted_date ON documents (extracted_date);
CREATE INDEX idx_documents_metadata_json ON documents USING GIN (metadata_json);

CREATE INDEX idx_documents_embedding ON documents
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ---------- resume_versions ----------
CREATE TABLE resume_versions (
    id              SERIAL PRIMARY KEY,
    version         VARCHAR(20),
    variant         VARCHAR(50),
    docx_path       VARCHAR(500),
    pdf_path        VARCHAR(500),
    summary         TEXT,
    target_role_type VARCHAR(50),
    document_id     INTEGER         REFERENCES documents(id) ON DELETE SET NULL,
    is_current      BOOLEAN         DEFAULT FALSE,
    created_at      TIMESTAMP       DEFAULT NOW()
);

COMMENT ON TABLE resume_versions IS 'Resume version registry linking variants to document records.';
COMMENT ON COLUMN resume_versions.version IS 'Version identifier: v32, v31, etc.';
COMMENT ON COLUMN resume_versions.variant IS 'Resume variant: base, AI Architect, SW Architect, PM, Simplified.';
COMMENT ON COLUMN resume_versions.is_current IS 'TRUE if this is the active version for its variant.';

CREATE INDEX idx_resume_versions_version          ON resume_versions (version);
CREATE INDEX idx_resume_versions_variant          ON resume_versions (variant);
CREATE INDEX idx_resume_versions_target_role_type ON resume_versions (target_role_type);
CREATE INDEX idx_resume_versions_document_id      ON resume_versions (document_id);
CREATE INDEX idx_resume_versions_is_current       ON resume_versions (is_current);

-- ============================================================================
-- 1.4 Analytics Views
-- ============================================================================

-- ---------- application_funnel ----------
CREATE VIEW application_funnel AS
SELECT
    status,
    COUNT(*) AS count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
FROM applications
GROUP BY status
ORDER BY CASE status
    WHEN 'Saved'        THEN 1
    WHEN 'Applied'      THEN 2
    WHEN 'Phone Screen' THEN 3
    WHEN 'Interview'    THEN 4
    WHEN 'Technical'    THEN 5
    WHEN 'Final'        THEN 6
    WHEN 'Offer'        THEN 7
    WHEN 'Accepted'     THEN 8
    ELSE 9
END;

COMMENT ON VIEW application_funnel IS 'Application pipeline funnel with counts and percentages per status.';

-- ---------- source_effectiveness ----------
CREATE VIEW source_effectiveness AS
SELECT
    source,
    COUNT(*) AS total_apps,
    COUNT(*) FILTER (WHERE status IN (
        'Phone Screen', 'Interview', 'Technical', 'Final', 'Offer', 'Accepted'
    )) AS got_response,
    ROUND(
        COUNT(*) FILTER (WHERE status IN (
            'Phone Screen', 'Interview', 'Technical', 'Final', 'Offer', 'Accepted'
        )) * 100.0 / NULLIF(COUNT(*), 0), 1
    ) AS response_rate_pct,
    COUNT(*) FILTER (WHERE status IN (
        'Interview', 'Technical', 'Final', 'Offer', 'Accepted'
    )) AS got_interview,
    ROUND(
        COUNT(*) FILTER (WHERE status IN (
            'Interview', 'Technical', 'Final', 'Offer', 'Accepted'
        )) * 100.0 / NULLIF(COUNT(*), 0), 1
    ) AS interview_rate_pct
FROM applications
GROUP BY source
ORDER BY interview_rate_pct DESC NULLS LAST;

COMMENT ON VIEW source_effectiveness IS 'Application source breakdown with response and interview conversion rates.';

-- ---------- monthly_activity ----------
CREATE VIEW monthly_activity AS
SELECT
    DATE_TRUNC('month', date_applied) AS month,
    COUNT(*) AS applications,
    COUNT(*) FILTER (WHERE status IN ('Interview', 'Technical', 'Final')) AS interviews,
    COUNT(*) FILTER (WHERE status = 'Rejected') AS rejections,
    COUNT(*) FILTER (WHERE status = 'Ghosted') AS ghosted,
    COUNT(*) FILTER (WHERE status IN ('Offer', 'Rescinded')) AS offers
FROM applications
GROUP BY DATE_TRUNC('month', date_applied)
ORDER BY month DESC;

COMMENT ON VIEW monthly_activity IS 'Monthly application activity summary with outcome breakdown.';

-- ============================================================================
-- Migration metadata
-- ============================================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR(20) PRIMARY KEY,
    name        VARCHAR(200),
    applied_at  TIMESTAMP DEFAULT NOW()
);

INSERT INTO schema_migrations (version, name)
VALUES ('001', 'initial_schema');

COMMIT;

-- ============================================================================
-- Post-transaction notes:
--
-- Semantic search example (bullets):
--   SELECT text, 1 - (embedding <=> $query_embedding) AS similarity
--   FROM bullets
--   ORDER BY embedding <=> $query_embedding
--   LIMIT 10;
--
-- JD matching example (applications vs bullets):
--   SELECT b.text, 1 - (b.embedding <=> a.jd_embedding) AS similarity
--   FROM bullets b, applications a
--   WHERE a.id = $app_id AND a.jd_embedding IS NOT NULL
--   ORDER BY b.embedding <=> a.jd_embedding
--   LIMIT 20;
-- ============================================================================
