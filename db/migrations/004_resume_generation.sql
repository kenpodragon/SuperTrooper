-- Migration 004: Resume generation support
-- Tables: resume_templates (blob storage), resume_header (contact info)
-- Alters: resume_versions (add spec JSONB), career_history (add intro_text for resume job intros)

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. resume_templates — stores .docx template blobs
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS resume_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,          -- "V32 Base", "V31 Base"
    filename VARCHAR(200),               -- "Resume_Base_v32.docx"
    template_blob BYTEA NOT NULL,        -- the raw .docx file
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 2. resume_header — candidate contact info for resume headers
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS resume_header (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(200) NOT NULL,
    credentials VARCHAR(200),            -- "PhD, CSM, PMP, MBA"
    location VARCHAR(200),               -- "Melbourne, FL"
    location_note VARCHAR(200),          -- "Open to Relocate"
    email VARCHAR(200),
    phone VARCHAR(50),
    linkedin_url VARCHAR(500),
    website_url VARCHAR(500),
    calendly_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 3. education — degree/certificate entries
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS education (
    id SERIAL PRIMARY KEY,
    degree VARCHAR(200) NOT NULL,        -- "PhD", "MBA", "BS"
    field VARCHAR(200),                  -- "Industrial/Organizational Psychology"
    institution VARCHAR(200) NOT NULL,
    location VARCHAR(200),               -- "Minneapolis, MN"
    type VARCHAR(50) DEFAULT 'degree',   -- degree, certificate, professional_development
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 4. certifications
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS certifications (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,          -- "Certified Scrum Master (CSM)"
    issuer VARCHAR(200),                 -- "Scrum Alliance"
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 5. Add spec JSONB to resume_versions for reconstruction mapping
-- ---------------------------------------------------------------------------

ALTER TABLE resume_versions ADD COLUMN IF NOT EXISTS spec JSONB;
-- spec structure:
-- {
--   "headline": "VP of Software Engineering & Digital Transformation",
--   "summary_text": "I build highly scalable...",
--   "highlight_bullet_ids": [id, id, ...],
--   "keywords": ["Digital Transformation", ...],
--   "experience": [
--     {"career_history_id": 1, "bullet_ids": [8,14,10,11,12], "intro": "Recruited directly..."},
--     ...
--   ],
--   "additional_experience": [
--     {"career_history_id": 5, "display": "Fractional CPO | Datavers.ai | Feb 2026 - Present"},
--     ...
--   ],
--   "education_ids": [1,2,3,4],
--   "certification_ids": [1,2,3,...],
--   "executive_keywords": ["Enterprise Digital Transformation", ...],
--   "technical_keywords": ["Generative AI (LangChain, RAG)", ...],
--   "references": [{"section": "Enterprise M&A...", "links": [...]}]
-- }

-- ---------------------------------------------------------------------------
-- 6. Add intro_text to career_history for resume job introductions
-- ---------------------------------------------------------------------------

ALTER TABLE career_history ADD COLUMN IF NOT EXISTS intro_text TEXT;
-- The paragraph that appears under a job title before the bullets
-- e.g. "Recruited directly by the CEO via Atlas YC Miami to take an AI-driven..."

-- ---------------------------------------------------------------------------
-- Record migration
-- ---------------------------------------------------------------------------

INSERT INTO schema_migrations (version, name) VALUES (4, '004_resume_generation');

COMMIT;
