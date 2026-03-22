-- Migration 018: Application Materials Generation — extend existing tables
-- Tables generated_materials and outreach_messages already exist, add new columns

BEGIN;

-- Extend generated_materials with new columns for materials generation
ALTER TABLE generated_materials ADD COLUMN IF NOT EXISTS saved_job_id INTEGER REFERENCES saved_jobs(id);
ALTER TABLE generated_materials ADD COLUMN IF NOT EXISTS contact_id INTEGER REFERENCES contacts(id);
ALTER TABLE generated_materials ADD COLUMN IF NOT EXISTS company_name TEXT;
ALTER TABLE generated_materials ADD COLUMN IF NOT EXISTS role_title TEXT;
ALTER TABLE generated_materials ADD COLUMN IF NOT EXISTS content TEXT;
ALTER TABLE generated_materials ADD COLUMN IF NOT EXISTS content_format VARCHAR(20) DEFAULT 'text';
ALTER TABLE generated_materials ADD COLUMN IF NOT EXISTS voice_check_passed BOOLEAN DEFAULT FALSE;
ALTER TABLE generated_materials ADD COLUMN IF NOT EXISTS voice_violations JSONB;
ALTER TABLE generated_materials ADD COLUMN IF NOT EXISTS generation_context JSONB;
ALTER TABLE generated_materials ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft';
ALTER TABLE generated_materials ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Extend outreach_messages with new columns for outreach generation
ALTER TABLE outreach_messages ADD COLUMN IF NOT EXISTS message_type VARCHAR(30) DEFAULT 'networking';
ALTER TABLE outreach_messages ADD COLUMN IF NOT EXISTS personalization_context JSONB;
ALTER TABLE outreach_messages ADD COLUMN IF NOT EXISTS voice_check_passed BOOLEAN DEFAULT FALSE;
ALTER TABLE outreach_messages ADD COLUMN IF NOT EXISTS gmail_draft_id TEXT;
ALTER TABLE outreach_messages ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft';
ALTER TABLE outreach_messages ADD COLUMN IF NOT EXISTS response_received_at TIMESTAMP;
ALTER TABLE outreach_messages ADD COLUMN IF NOT EXISTS outcome VARCHAR(30);

-- New indexes (IF NOT EXISTS handled by CREATE INDEX)
CREATE INDEX IF NOT EXISTS idx_generated_materials_status ON generated_materials(status);
CREATE INDEX IF NOT EXISTS idx_outreach_messages_type ON outreach_messages(message_type);
CREATE INDEX IF NOT EXISTS idx_outreach_messages_status ON outreach_messages(status);

COMMIT;
