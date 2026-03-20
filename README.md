# SuperTroopers

Your AI-powered reverse recruiting command center. Upload your resume, and SuperTroopers parses it into structured career data, generates tailored resumes via recipes, tracks applications, analyzes job fit, and manages your entire job search... all from your terminal.

## What It Does

- **Resume Intelligence** -- Upload .docx/.pdf, auto-parse into career history, bullets, and skills
- **Recipe-Based Generation** -- Template system that produces tailored .docx resumes for any role
- **Gap Analysis** -- Match your experience against job descriptions, see what fits and what's missing
- **Application Tracking** -- Full pipeline from saved jobs through applications to interviews and offers
- **Voice Guard** -- Configurable rules to keep AI-generated text sounding like you, not a robot
- **42 MCP Tools** -- Every feature accessible to AI agents via Model Context Protocol

## Architecture

```
Docker Compose (3 containers)
  supertroopers-db    PostgreSQL + pgvector    :5555
  supertroopers-app   Flask API + MCP SSE      :8055 / :8056
  supertroopers-web   React + Vite frontend    :5175

Your AI Agent (Claude Code, Gemini CLI, etc.)
  connects via MCP SSE at localhost:8056
  42 tools for resume, job search, tracking, networking, analytics
```

## Quick Start

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview)
2. Clone this repo and `cd code`
3. `cp .env.example .env && docker compose up -d`
4. Copy `.mcp.json.example` to your project root as `.mcp.json`
5. Run `claude` and ask: "Upload my resume at path/to/resume.docx"

Full walkthrough: [docs/SETUP.md](docs/SETUP.md)

## Documentation

| Doc | What's in it |
|-----|-------------|
| [Setup Guide](docs/SETUP.md) | Step-by-step from zero to working (non-technical friendly) |
| [API Reference](docs/API_REFERENCE.md) | All 105 REST endpoints |
| [MCP Tool Reference](docs/MCP_REFERENCE.md) | All 42 MCP tools with parameters and examples |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and fixes |

## Built For

**Claude Code** (primary) -- Full MCP integration with CLAUDE.md routing and workflows built in.

**Other AI agents** -- Any MCP-compatible tool can connect via SSE at `localhost:8056`. See the [MCP Reference](docs/MCP_REFERENCE.md) for connection details.

**Direct API** -- REST API at `localhost:8055` for custom integrations. See the [API Reference](docs/API_REFERENCE.md).

## Tech Stack

Python / Flask, PostgreSQL + pgvector, React / TypeScript / Vite, Docker, MCP (SSE transport)

## Status

Active development. Core platform complete (33 tables, 105 endpoints, 42 MCP tools, 8 frontend views).

Tested on Windows 11. Mac has not been tested yet.

## License

MIT (placeholder -- update before public release)
