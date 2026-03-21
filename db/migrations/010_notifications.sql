BEGIN;

CREATE TABLE IF NOT EXISTS notifications (
  id SERIAL PRIMARY KEY,
  type VARCHAR(50) NOT NULL,  -- new_job, status_change, follow_up_due, stale_warning, interview_reminder, contact_follow_up, digest_ready, email_matched
  severity VARCHAR(20) DEFAULT 'info',  -- info, action_needed, urgent
  title TEXT NOT NULL,
  body TEXT,
  link TEXT,  -- frontend route path, e.g., /applications/42
  entity_type VARCHAR(50),  -- polymorphic: application, saved_job, contact, fresh_job
  entity_id INTEGER,
  read BOOLEAN DEFAULT FALSE,
  dismissed BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read) WHERE read = FALSE;
CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(type);
CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at DESC);

CREATE TABLE IF NOT EXISTS notification_preferences (
  id SERIAL PRIMARY KEY,
  notification_type VARCHAR(50) NOT NULL UNIQUE,
  enabled BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Seed default preferences for all notification types
INSERT INTO notification_preferences (notification_type, enabled) VALUES
  ('new_job', TRUE),
  ('status_change', TRUE),
  ('follow_up_due', TRUE),
  ('stale_warning', TRUE),
  ('interview_reminder', TRUE),
  ('contact_follow_up', TRUE),
  ('digest_ready', TRUE),
  ('email_matched', TRUE)
ON CONFLICT (notification_type) DO NOTHING;

COMMIT;
