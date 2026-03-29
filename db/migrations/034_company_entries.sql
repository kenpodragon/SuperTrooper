-- Migration 034: Company-level entries in career_history
-- Adds is_company_entry flag so each employer can have a company-level row
-- that holds company synopses and bullets (distinct from role-level content).

ALTER TABLE career_history ADD COLUMN IF NOT EXISTS is_company_entry BOOLEAN NOT NULL DEFAULT FALSE;

-- Create company entries for each distinct employer that doesn't already have one
INSERT INTO career_history (employer, title, is_company_entry)
SELECT DISTINCT employer, '_COMPANY_OVERVIEW', TRUE
FROM career_history
WHERE employer IS NOT NULL AND employer <> ''
AND employer NOT IN (
    SELECT employer FROM career_history WHERE is_company_entry = TRUE
)
ON CONFLICT (employer, title) DO NOTHING;

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_career_history_company_entry
ON career_history (employer) WHERE is_company_entry = TRUE;
