-- Migration 018: Application Materials Generation
-- Rollback: DROP TABLE IF EXISTS outreach_messages, generated_materials CASCADE;

BEGIN;

CREATE TABLE IF NOT EXISTS generated_materials (
  id SERIAL PRIMARY KEY,
  material_type VARCHAR(30) NOT NULL,  -- cover_letter, thank_you, outreach, linkedin_post, resume_variant
  application_id INTEGER REFERENCES applications(id),
  saved_job_id INTEGER REFERENCES saved_jobs(id),
  contact_id INTEGER REFERENCES contacts(id),
  company_name TEXT,
  role_title TEXT,
  content TEXT NOT NULL,
  content_format VARCHAR(20) DEFAULT 'text',  -- text, markdown, html
  voice_check_passed BOOLEAN DEFAULT FALSE,
  voice_violations JSONB,  -- any violations found during generation
  generation_context JSONB,  -- what data was used: gap_analysis_id, dossier data, debrief notes, etc.
  file_path TEXT,  -- path to saved .docx/.pdf if generated
  status VARCHAR(20) DEFAULT 'draft',  -- draft, reviewed, sent, archived
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS outreach_messages (
  id SERIAL PRIMARY KEY,
  contact_id INTEGER REFERENCES contacts(id),
  application_id INTEGER REFERENCES applications(id),
  message_type VARCHAR(30) NOT NULL,  -- cold_outreach, warm_intro_request, follow_up, thank_you, networking, recruiter
  channel VARCHAR(20) DEFAULT 'email',  -- email, linkedin, phone
  subject TEXT,
  body TEXT NOT NULL,
  personalization_context JSONB,  -- what made this personalized: shared_history, mutual_connections, etc.
  voice_check_passed BOOLEAN DEFAULT FALSE,
  gmail_draft_id TEXT,  -- if created as Gmail draft
  status VARCHAR(20) DEFAULT 'draft',  -- draft, sent, replied, no_response, bounced
  sent_at TIMESTAMP,
  response_received_at TIMESTAMP,
  outcome VARCHAR(30),  -- positive, negative, no_response, intro_made, meeting_scheduled
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generated_materials_type ON generated_materials(material_type);
CREATE INDEX IF NOT EXISTS idx_generated_materials_app ON generated_materials(application_id);
CREATE INDEX IF NOT EXISTS idx_generated_materials_status ON generated_materials(status);
CREATE INDEX IF NOT EXISTS idx_outreach_messages_contact ON outreach_messages(contact_id);
CREATE INDEX IF NOT EXISTS idx_outreach_messages_type ON outreach_messages(message_type);
CREATE INDEX IF NOT EXISTS idx_outreach_messages_status ON outreach_messages(status);

COMMIT;
