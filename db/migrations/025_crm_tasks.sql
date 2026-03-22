BEGIN;

-- CRM Tasks: richer task/reminder system with status workflow and snooze
CREATE TABLE IF NOT EXISTS crm_tasks (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER REFERENCES contacts(id),
    task_type TEXT NOT NULL DEFAULT 'follow_up',
    description TEXT,
    due_date DATE,
    status TEXT NOT NULL DEFAULT 'pending',
    snoozed_until DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_crm_tasks_due ON crm_tasks(due_date) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_crm_tasks_contact ON crm_tasks(contact_id);
CREATE INDEX IF NOT EXISTS idx_crm_tasks_status ON crm_tasks(status);

-- Contact enrichment tracking columns
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMPTZ;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS enrichment_source TEXT;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS merged_into_id INTEGER REFERENCES contacts(id);

COMMIT;
