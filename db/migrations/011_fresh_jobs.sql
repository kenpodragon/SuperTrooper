BEGIN;

CREATE TABLE IF NOT EXISTS fresh_jobs (
  id SERIAL PRIMARY KEY,
  source_type VARCHAR(30) NOT NULL,  -- api_search, plugin_capture, email_parsed, social_scan, rss_feed, manual
  source_url TEXT,
  title TEXT,
  company TEXT,
  location TEXT,
  salary_range TEXT,
  jd_snippet TEXT,
  jd_full TEXT,
  discovered_at TIMESTAMP DEFAULT NOW(),
  status VARCHAR(20) DEFAULT 'new',  -- new, reviewed, saved, passed, expired, snoozed
  auto_score REAL,
  saved_job_id INTEGER REFERENCES saved_jobs(id),  -- populated when triaged to "save"
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fresh_jobs_status ON fresh_jobs(status);
CREATE INDEX IF NOT EXISTS idx_fresh_jobs_source ON fresh_jobs(source_type);
CREATE INDEX IF NOT EXISTS idx_fresh_jobs_discovered ON fresh_jobs(discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_fresh_jobs_score ON fresh_jobs(auto_score DESC NULLS LAST);

COMMIT;
