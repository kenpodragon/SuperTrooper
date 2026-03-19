-- Migration 006: Resume Recipes
-- Recipe-based resume generation system. Replaces inline text specs with
-- pointer-based references ({table, id, column}) for lightweight, reusable
-- resume composition from the knowledge base.

BEGIN;

-- Resume recipes table
CREATE TABLE IF NOT EXISTS resume_recipes (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    headline        TEXT,
    template_id     INTEGER NOT NULL REFERENCES resume_templates(id),
    recipe          JSONB NOT NULL,
    application_id  INTEGER REFERENCES applications(id) ON DELETE SET NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_resume_recipes_template ON resume_recipes(template_id);
CREATE INDEX idx_resume_recipes_application ON resume_recipes(application_id);
CREATE INDEX idx_resume_recipes_is_active ON resume_recipes(is_active);

-- Add career_links to career_history for proof/portfolio links per employer
ALTER TABLE career_history ADD COLUMN IF NOT EXISTS career_links JSONB;

-- Track migration
INSERT INTO schema_migrations (version, name)
VALUES (6, '006_resume_recipes')
ON CONFLICT DO NOTHING;

COMMIT;
