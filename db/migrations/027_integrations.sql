-- 027: Add integrations JSONB column to settings table
-- Stores per-integration config (google, antiai, indeed)

ALTER TABLE settings ADD COLUMN IF NOT EXISTS integrations JSONB DEFAULT '{}';

-- Seed with defaults
UPDATE settings SET integrations = '{
  "google": {
    "enabled": false,
    "credentials_path": "secrets/google/credentials.json",
    "token_path": "secrets/google/token.json",
    "scopes": ["gmail", "calendar", "drive"]
  },
  "antiai": {
    "enabled": false,
    "api_url": "",
    "mcp_url": ""
  },
  "indeed": {
    "enabled": true,
    "method": "claude_cli"
  }
}'::jsonb WHERE id = 1 AND (integrations IS NULL OR integrations = '{}'::jsonb);
