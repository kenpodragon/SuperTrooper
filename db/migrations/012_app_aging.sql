BEGIN;

-- Add posting status tracking to saved_jobs
ALTER TABLE saved_jobs ADD COLUMN IF NOT EXISTS posting_closed BOOLEAN DEFAULT FALSE;
ALTER TABLE saved_jobs ADD COLUMN IF NOT EXISTS posting_closed_at TIMESTAMP;
ALTER TABLE saved_jobs ADD COLUMN IF NOT EXISTS last_link_check_at TIMESTAMP;
ALTER TABLE saved_jobs ADD COLUMN IF NOT EXISTS link_status VARCHAR(20) DEFAULT 'unknown';  -- unknown, active, closed, error

-- Add posting status tracking to applications
ALTER TABLE applications ADD COLUMN IF NOT EXISTS posting_closed BOOLEAN DEFAULT FALSE;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS posting_closed_at TIMESTAMP;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS last_link_check_at TIMESTAMP;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS link_status VARCHAR(20) DEFAULT 'unknown';

-- Index for finding stale items
CREATE INDEX IF NOT EXISTS idx_saved_jobs_link_status ON saved_jobs(link_status);
CREATE INDEX IF NOT EXISTS idx_applications_link_status ON applications(link_status);
CREATE INDEX IF NOT EXISTS idx_saved_jobs_posting_closed ON saved_jobs(posting_closed) WHERE posting_closed = TRUE;
CREATE INDEX IF NOT EXISTS idx_applications_posting_closed ON applications(posting_closed) WHERE posting_closed = TRUE;

COMMIT;
