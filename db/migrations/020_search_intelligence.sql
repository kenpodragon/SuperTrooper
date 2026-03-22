-- Migration 020: Search Intelligence & Email Intelligence
-- Phase 5H: S4.4, S4.5, S4.6, S6.3

BEGIN;

-- Saved searches table
CREATE TABLE IF NOT EXISTS saved_searches (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    keywords TEXT,
    location VARCHAR(200),
    role_type VARCHAR(100),
    salary_min NUMERIC(12,2),
    salary_max NUMERIC(12,2),
    sources TEXT[],
    filters JSONB,
    schedule VARCHAR(30) DEFAULT 'daily',
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    results_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_saved_searches_active ON saved_searches(is_active);

-- Extend emails for intelligence scanning
ALTER TABLE emails ADD COLUMN IF NOT EXISTS scan_status VARCHAR(30) DEFAULT 'unscanned';
ALTER TABLE emails ADD COLUMN IF NOT EXISTS scan_confidence NUMERIC(3,2);
ALTER TABLE emails ADD COLUMN IF NOT EXISTS auto_categorized BOOLEAN DEFAULT FALSE;
ALTER TABLE emails ADD COLUMN IF NOT EXISTS extracted_data JSONB;

-- Extend fresh_jobs for source tracking
ALTER TABLE fresh_jobs ADD COLUMN IF NOT EXISTS discovery_source VARCHAR(50);
ALTER TABLE fresh_jobs ADD COLUMN IF NOT EXISTS discovery_url TEXT;
ALTER TABLE fresh_jobs ADD COLUMN IF NOT EXISTS saved_search_id INTEGER REFERENCES saved_searches(id);

COMMIT;
