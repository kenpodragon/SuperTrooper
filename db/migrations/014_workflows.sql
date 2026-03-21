BEGIN;

CREATE TABLE IF NOT EXISTS workflows (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  trigger_type VARCHAR(30) NOT NULL,  -- schedule, event
  trigger_config JSONB NOT NULL,  -- schedule: {"cron": "0 9 * * 1"}, event: {"entity": "application", "event": "status_changed"}
  conditions JSONB,  -- simple: {"field": "new_status", "equals": "interview_scheduled"}
  action_type VARCHAR(30) NOT NULL,  -- create_notification, update_field, log_activity
  action_config JSONB NOT NULL,  -- depends on action_type
  enabled BOOLEAN DEFAULT TRUE,
  last_run_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_log (
  id SERIAL PRIMARY KEY,
  workflow_id INTEGER REFERENCES workflows(id),
  triggered_at TIMESTAMP DEFAULT NOW(),
  trigger_data JSONB,
  action_result JSONB,
  success BOOLEAN DEFAULT TRUE,
  error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_workflows_enabled ON workflows(enabled) WHERE enabled = TRUE;
CREATE INDEX IF NOT EXISTS idx_workflows_trigger_type ON workflows(trigger_type);
CREATE INDEX IF NOT EXISTS idx_workflow_log_workflow ON workflow_log(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_log_triggered ON workflow_log(triggered_at DESC);

COMMIT;
