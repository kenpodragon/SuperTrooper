-- 008_settings_onboard.sql
-- Settings table (single row) + onboard upload tracking

BEGIN;

-- Widen template_type for new uploaded_original/uploaded_converted values
ALTER TABLE resume_templates
    ALTER COLUMN template_type TYPE VARCHAR(50);

-- Platform settings (single row, enforced by CHECK constraint)
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    ai_provider VARCHAR(50) DEFAULT 'none',
    ai_enabled BOOLEAN DEFAULT FALSE,
    ai_model VARCHAR(100),
    default_template_id INTEGER REFERENCES resume_templates(id),
    duplicate_threshold FLOAT DEFAULT 0.85,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT single_row CHECK (id = 1)
);

INSERT INTO settings (id) VALUES (1) ON CONFLICT DO NOTHING;

-- Track file upload history for audit, re-processing, rollback
CREATE TABLE IF NOT EXISTS onboard_uploads (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(500) NOT NULL,
    file_type VARCHAR(10) NOT NULL,
    file_size INTEGER,
    status VARCHAR(50) DEFAULT 'processing',
    parsing_method VARCHAR(50),
    parsing_confidence FLOAT,
    career_history_ids INTEGER[],
    bullet_ids INTEGER[],
    skill_ids INTEGER[],
    template_id INTEGER REFERENCES resume_templates(id),
    recipe_id INTEGER REFERENCES resume_recipes(id),
    match_score FLOAT,
    report JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_onboard_uploads_status ON onboard_uploads(status);
CREATE INDEX idx_onboard_uploads_created ON onboard_uploads(created_at DESC);

COMMIT;
