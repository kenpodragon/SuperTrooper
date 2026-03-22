-- 021_references.sql — Extend contacts for reference management
BEGIN;

ALTER TABLE contacts ADD COLUMN IF NOT EXISTS reference_topics TEXT[];
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS reference_role_types TEXT[];
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS reference_times_used INTEGER DEFAULT 0;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS reference_last_used DATE;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS reference_effectiveness JSONB;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS is_reference BOOLEAN DEFAULT FALSE;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS reference_priority VARCHAR(20);

CREATE INDEX IF NOT EXISTS idx_contacts_is_reference ON contacts (is_reference) WHERE is_reference = TRUE;

COMMIT;
