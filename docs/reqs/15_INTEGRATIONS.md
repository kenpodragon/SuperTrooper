# 15. Settings Integrations & Setup Wizards

## Overview

External service integrations for SuperTroopers. Each integration connects via the simplest viable transport, runs inside the existing backend container (no extra containers for end users), and degrades gracefully when unavailable.

---

## Integration Matrix

| Integration | Transport | Required? | Auth | Config Location |
|------------|-----------|-----------|------|----------------|
| AI Provider (Claude/Gemini/OpenAI) | CLI subprocess | Recommended | `.claude/` mount (existing) | `settings` table |
| Google Workspace (Gmail, Calendar, Drive) | MCP stdio subprocess | Optional | Google OAuth `credentials.json` + `token.json` | `secrets/google/` |
| AntiAI / GhostBusters | REST API | Optional | None (localhost) | `settings.integrations` JSONB |
| Indeed | Claude CLI tunnel | Auto (via AI Provider) | Via AI Provider auth | None |

---

## 15.1 Google Workspace MCP

### Architecture

```
supertroopers-app container:
  Flask API (main process)
    -> spawns google-workspace-mcp (stdio subprocess)
    -> Python MCP client communicates via stdin/stdout
```

### Package

- `google-workspace-mcp` by taylorwilsdon (Python, v1.15.0, 1.9k stars, MIT)
- Covers: Gmail, Calendar, Drive, Docs, Sheets, Slides, Forms, Tasks, Contacts, Chat
- OAuth 2.1 stateless mode (tokens in memory after load)
- Security audited: no telemetry, no phoning home, only calls Google APIs

### OAuth Setup (one-time, per user)

1. Go to Google Cloud Console -> APIs & Services -> Credentials
2. Create OAuth 2.0 Client ID (Desktop application type)
3. Enable APIs: Gmail API, Google Calendar API, Google Drive API
4. Download `credentials.json`
5. Place in `code/secrets/google/credentials.json`
6. Run consent flow: `python -m google_workspace_mcp.auth --credentials secrets/google/credentials.json`
7. Browser opens, user authorizes, `token.json` is written to `secrets/google/token.json`
8. Both files are bind-mounted into the container

### Docker Changes

**Dockerfile additions:**
```dockerfile
RUN pip install --no-cache-dir google-workspace-mcp
```

**docker-compose.yml volume mount:**
```yaml
volumes:
  - ./secrets/google:/app/secrets/google:ro
```

### Backend Client (`integrations/google_client.py`)

- On startup (or first use), spawn `google-workspace-mcp` as stdio subprocess
- Use `mcp` Python SDK's `StdioClient` to communicate
- Expose helper methods: `gmail_search()`, `gmail_read()`, `gcal_list_events()`, `gdrive_list()`, etc.
- Lazy initialization: subprocess only starts when first Google tool is called
- Health check: attempt `list_tools()` call, return available tool names
- Graceful shutdown: kill subprocess on app exit

### Tools Available (subset relevant to SuperTroopers)

| Tool | Purpose in SuperTroopers |
|------|-------------------------|
| `gmail_search` | Recruiter email detection, application status |
| `gmail_read` | Read email content for parsing |
| `gmail_send` / `gmail_draft` | Outreach, follow-ups, thank-you notes |
| `gcal_list_events` | Interview detection |
| `gcal_create_event` | Schedule interview prep reminders |
| `gdrive_list` | Resume/doc management |
| `gdrive_upload` | Push generated resumes to Drive |

---

## 15.2 AntiAI / GhostBusters

### Architecture

```
Host machine (or remote server):
  GhostBusters Flask API (port 8066)
  GhostBusters MCP SSE (port 8067)

supertroopers-app container:
  -> REST calls to http://host.docker.internal:8066/api/*
```

### Connection

- Purely optional. User installs GhostBusters separately.
- Backend makes direct REST calls (no MCP client needed, simpler).
- URL is configurable in settings (default: `http://host.docker.internal:8066`).
- All AntiAI features gracefully skip when not configured or unreachable.

### Backend Client (`integrations/antiai_client.py`)

- Simple `requests`-based REST client
- Methods: `analyze(text)`, `rewrite(text, voice_profile_id)`, `score(text)`, `health()`
- Timeout: 30s for analyze/rewrite (AI calls), 5s for health
- Returns `None` on connection failure (caller handles gracefully)

### Endpoints Used

| GhostBusters Endpoint | Purpose |
|----------------------|---------|
| `GET /api/health` | Connection test |
| `POST /api/analyze` | AI detection scoring |
| `POST /api/rewrite` | Humanize flagged text |
| `POST /api/score` | Quick heuristics-only score |

### Integration Points in SuperTroopers

When AntiAI is connected and enabled, add scan step to:
- Resume generation (`generate_resume`)
- Cover letter generation
- Outreach message generation
- Thank-you note generation
- LinkedIn post generation
- Interview prep talking points

Pipeline: generate -> voice check -> AntiAI scan -> humanize if flagged -> re-check voice -> present

---

## 15.3 Indeed

### Architecture

```
supertroopers-app container:
  -> Claude CLI subprocess: claude -p "Use indeed to search for..."
  -> Parse JSON response
```

### Connection

- Requires AI Provider (Claude) to be configured and healthy
- No separate setup needed
- Indeed MCP tools are available through Claude's cloud infrastructure
- Falls back to web scraping / manual entry if Claude CLI unavailable

### Backend Client (`integrations/indeed_client.py`)

- Wraps Claude CLI calls for Indeed-specific operations
- Methods: `search_jobs(query, location)`, `get_job_details(url)`, `get_company(name)`
- Parses structured JSON from Claude CLI response
- Timeout: 60s (CLI calls can be slow)

---

## 15.4 Settings & Configuration

### Database Migration

Add `integrations` JSONB column to `settings` table:

```sql
ALTER TABLE settings ADD COLUMN IF NOT EXISTS integrations JSONB DEFAULT '{}';
```

Schema:
```json
{
  "google": {
    "enabled": true,
    "credentials_path": "secrets/google/credentials.json",
    "token_path": "secrets/google/token.json",
    "scopes": ["gmail", "calendar", "drive"]
  },
  "antiai": {
    "enabled": false,
    "api_url": "http://host.docker.internal:8066",
    "mcp_url": "http://host.docker.internal:8067/sse"
  },
  "indeed": {
    "enabled": true,
    "method": "claude_cli"
  }
}
```

### Backend Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /api/integrations` | GET | List all integrations with status |
| `POST /api/integrations/:name/test` | POST | Test connection for specific integration |
| `PUT /api/integrations/:name/config` | PUT | Update integration config |
| `POST /api/integrations/google/authorize` | POST | Initiate Google OAuth flow |

### Integration Status Response Shape

```json
{
  "integrations": [
    {
      "name": "google",
      "label": "Google Workspace",
      "description": "Gmail, Calendar, Drive",
      "status": "connected",
      "enabled": true,
      "services": ["gmail", "calendar", "drive"],
      "setup_required": false,
      "config": { "scopes": ["gmail", "calendar", "drive"] }
    },
    {
      "name": "antiai",
      "label": "AntiAI / GhostBusters",
      "description": "AI detection and humanization",
      "status": "disconnected",
      "enabled": false,
      "setup_required": true,
      "config": { "api_url": "" }
    },
    {
      "name": "indeed",
      "label": "Indeed",
      "description": "Job search and company data",
      "status": "available",
      "enabled": true,
      "setup_required": false,
      "config": { "method": "claude_cli" }
    },
    {
      "name": "ai_provider",
      "label": "AI Provider",
      "description": "Claude, Gemini, or OpenAI",
      "status": "connected",
      "enabled": true,
      "setup_required": false,
      "config": { "provider": "claude", "model": "claude-3-5-sonnet" }
    }
  ]
}
```

---

## 15.5 Frontend Settings Wizards

### Integrations Tab Layout

Each integration shown as a card with:
- Status light (green/yellow/red)
- Name + description
- Enable/disable toggle
- "Configure" button -> opens wizard modal
- "Test Connection" button

### Wizard Modals

**AI Provider Wizard:**
1. Select provider (Claude/Gemini/OpenAI)
2. Test connection
3. Shows model info, version

**Google Workspace Wizard:**
1. Status check: are `credentials.json` and `token.json` present?
2. If not: step-by-step instructions with links to Google Cloud Console
3. Scope selection checkboxes (Gmail, Calendar, Drive)
4. "Test Connection" button -> backend tests MCP subprocess
5. Shows which Google services are available

**AntiAI Wizard:**
1. URL input (default: `http://localhost:8066`)
2. "Test Connection" button -> backend calls `/api/health`
3. Enable/disable toggle
4. Brief description: "Scans generated content for AI patterns and humanizes flagged text"
5. Link to GhostBusters setup instructions (external)

**Indeed Wizard:**
1. Shows "Available via AI Provider" status
2. Requires Claude CLI healthy
3. "Test Connection" -> backend runs lightweight Indeed call via CLI
4. No manual config needed

---

## 15.6 Secrets Handling

### File Structure

```
code/
  secrets/
    google/
      .gitkeep              # Tracked placeholder
      credentials.json      # NOT tracked (in .gitignore)
      token.json            # NOT tracked (in .gitignore)
    .gitignore              # Ignores all secrets except .gitkeep
```

### .gitignore additions

```
# Secrets - never commit
code/secrets/google/credentials.json
code/secrets/google/token.json
code/secrets/**/*.json
!code/secrets/**/.gitkeep
```

### Docker bind mount

```yaml
# docker-compose.yml
services:
  backend:
    volumes:
      - ./secrets/google:/app/secrets/google:ro
```

---

## 15.7 Verification

| Test | Method | Expected |
|------|--------|----------|
| Google MCP subprocess starts | `POST /api/integrations/google/test` | Returns tool list |
| Google OAuth token valid | Google MCP `gmail_search` call | Returns results |
| AntiAI health check | `POST /api/integrations/antiai/test` | Returns `{status: "ok"}` |
| AntiAI analyze | `POST /api/analyze` via client | Returns scores |
| Indeed via CLI | `POST /api/integrations/indeed/test` | Returns job results |
| Missing Google creds | Start without `credentials.json` | Graceful skip, status "setup_required" |
| Missing AntiAI | Start without GhostBusters running | Graceful skip, status "disconnected" |
| Missing Claude CLI | Start without `.claude` mount | Indeed unavailable, AI features fall back to rules |

---

## 15.8 User Setup Guide (TODO)

A user-facing setup guide must be written at `code/docs/guides/integrations-setup.md` covering:
- Google Cloud Console project creation (screenshots)
- OAuth credential download and placement
- Running the consent flow
- GhostBusters installation and connection
- Verifying all integrations from the Settings page
- Troubleshooting common issues (expired tokens, wrong scopes, firewall)

**This is tracked in `recs/TODO.md` under "Living Documentation".**
