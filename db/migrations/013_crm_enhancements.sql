BEGIN;

-- Add CRM fields to contacts
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS relationship_stage VARCHAR(20) DEFAULT 'cold';  -- cold, warm, active, close, dormant
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS health_score REAL;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS last_touchpoint_at TIMESTAMP;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS tags TEXT[];  -- array of tags for filtering

CREATE INDEX IF NOT EXISTS idx_contacts_relationship_stage ON contacts(relationship_stage);
CREATE INDEX IF NOT EXISTS idx_contacts_health_score ON contacts(health_score DESC NULLS LAST);

-- Networking tasks (follow-ups, intros to request, etc.)
CREATE TABLE IF NOT EXISTS networking_tasks (
  id SERIAL PRIMARY KEY,
  contact_id INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
  task_type VARCHAR(30) NOT NULL,  -- follow_up, intro_request, coffee_chat, thank_you, share_article, reconnect
  title TEXT NOT NULL,
  due_date DATE,
  completed BOOLEAN DEFAULT FALSE,
  completed_at TIMESTAMP,
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_networking_tasks_contact ON networking_tasks(contact_id);
CREATE INDEX IF NOT EXISTS idx_networking_tasks_due ON networking_tasks(due_date) WHERE completed = FALSE;
CREATE INDEX IF NOT EXISTS idx_networking_tasks_completed ON networking_tasks(completed);

-- Touchpoints (interaction log)
CREATE TABLE IF NOT EXISTS touchpoints (
  id SERIAL PRIMARY KEY,
  contact_id INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
  type VARCHAR(30) NOT NULL,  -- email, linkedin_message, phone_call, coffee, meeting, event, referral
  channel VARCHAR(30),  -- linkedin, email, phone, in_person, slack, other
  direction VARCHAR(10) DEFAULT 'outbound',  -- inbound, outbound
  notes TEXT,
  logged_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_touchpoints_contact ON touchpoints(contact_id);
CREATE INDEX IF NOT EXISTS idx_touchpoints_logged ON touchpoints(logged_at DESC);

COMMIT;
