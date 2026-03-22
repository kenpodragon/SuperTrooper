BEGIN;

-- JD parsing columns on saved_jobs
ALTER TABLE saved_jobs ADD COLUMN IF NOT EXISTS jd_parsed JSONB;
ALTER TABLE saved_jobs ADD COLUMN IF NOT EXISTS salary_min NUMERIC;
ALTER TABLE saved_jobs ADD COLUMN IF NOT EXISTS salary_max NUMERIC;

-- Drip sequences for CRM multi-touch outreach
CREATE TABLE IF NOT EXISTS drip_sequences (
    id              SERIAL PRIMARY KEY,
    sequence_name   VARCHAR(200) NOT NULL,
    contact_id      INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
    steps           JSONB NOT NULL DEFAULT '[]',
    current_step    INTEGER NOT NULL DEFAULT 0,
    status          VARCHAR(30) NOT NULL DEFAULT 'active',
    started_at      TIMESTAMP DEFAULT NOW(),
    completed_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_drip_sequences_contact_id ON drip_sequences(contact_id);
CREATE INDEX IF NOT EXISTS idx_drip_sequences_status ON drip_sequences(status);

COMMIT;
