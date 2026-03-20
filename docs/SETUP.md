# SuperTroopers Setup Guide

Your personal reverse recruiting platform. This guide walks you through installing and running SuperTroopers on your Windows PC, step by step. Every command is copy-pasteable. You do not need to be technical to follow this.

**Time to complete:** About 20 minutes (mostly waiting for downloads).

**What you'll have when done:** A local platform that stores your career data, generates tailored resumes, tracks applications, and connects to AI assistants like Claude Code via 42 specialized tools.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Install Docker Desktop](#2-install-docker-desktop)
3. [Install Claude Code](#3-install-claude-code)
4. [Clone and Start the Platform](#4-clone-and-start-the-platform)
5. [Configure MCP Connection](#5-configure-mcp-connection)
6. [Verify Everything Works](#6-verify-everything-works)
7. [Upload Your First Resume](#7-upload-your-first-resume)
8. [Generate a Test Resume](#8-generate-a-test-resume)
9. [Next Steps](#9-next-steps)
10. [Using Other AI Agents](#10-using-other-ai-agents)
11. [Stopping and Starting](#11-stopping-and-starting)

---

## 1. Prerequisites

Before you begin, make sure you have:

- **A Windows PC** with admin access (needed for installing software)
- **Git** installed, OR you can download a ZIP from GitHub instead
- **Node.js LTS** installed (needed for Claude Code)
- **A .docx or .pdf resume** ready to upload

### Check if Git is installed

Open a terminal (search "Terminal" or "Command Prompt" in the Start menu) and run:

```bash
git --version
```

If you see a version number, you're good. If not, you can either:
- Install Git from https://git-scm.com/downloads/win
- Or skip Git entirely and download the ZIP in Step 4

### Install Node.js

Download the LTS version from https://nodejs.org and run the installer. Accept all defaults.

After installing, verify it works:

```bash
node --version
```

You should see something like `v22.x.x` or higher.

> **Mac users:** SuperTroopers has not been tested on Mac. Docker Desktop for Mac should work, and Node.js installs the same way via https://nodejs.org. The commands below are the same on Mac (use Terminal instead of Command Prompt). If you hit issues, check the [Troubleshooting Guide](TROUBLESHOOTING.md) Section 8 for Mac-specific notes.

---

## 2. Install Docker Desktop

Docker runs the platform's three services (database, API, and frontend) in containers so you don't have to install them separately.

### Download and install

1. Go to https://www.docker.com/products/docker-desktop/
2. Click **Download for Windows**
3. Run the installer and accept all defaults
4. Restart your PC if prompted

### Verify Docker is working

Open a terminal and run:

```bash
docker --version
```

Then:

```bash
docker compose version
```

Both should print version numbers.

> **Warning:** Docker Desktop on Windows requires WSL2 (Windows Subsystem for Linux). If Docker fails to start or shows a WSL error, you need to enable WSL2 first. Open PowerShell **as Administrator** and run:
> ```powershell
> wsl --install
> ```
> Then restart your PC and try Docker again. Full instructions: https://learn.microsoft.com/en-us/windows/wsl/install

> **Mac users:** Download Docker Desktop for Mac from the same page. Choose the correct chip (Apple Silicon or Intel). WSL2 does not apply to Mac.

---

## 3. Install Claude Code

Claude Code is the AI assistant that talks to SuperTroopers through MCP (Model Context Protocol). It's a command-line tool from Anthropic.

### Install it

```bash
npm install -g @anthropic-ai/claude-code
```

### Verify it works

```bash
claude --version
```

You should see a version number.

> **Tip:** For full documentation on Claude Code, visit https://docs.anthropic.com/en/docs/claude-code/overview

> **Using a different AI agent?** Any MCP-compatible tool can connect to SuperTroopers. You don't need Claude Code specifically. SuperTroopers exposes an SSE endpoint at `http://localhost:8056/sse` that works with Gemini CLI, Cursor, Windsurf, and other MCP clients. See [Section 10](#10-using-other-ai-agents) for details.

---

## 4. Clone and Start the Platform

### Get the code

**Option A -- With Git:**

```bash
git clone https://github.com/YOUR_USERNAME/supertroopers.git
```

**Option B -- Without Git:**

1. Go to the GitHub repository page
2. Click the green **Code** button
3. Click **Download ZIP**
4. Extract the ZIP to a folder on your desktop (or wherever you like)

### Configure environment variables

Navigate into the code folder:

```bash
cd supertroopers/code
```

Copy the example environment file:

**On Windows (Command Prompt):**
```cmd
copy .env.example .env
```

**On Windows (Git Bash / WSL) or Mac:**
```bash
cp .env.example .env
```

Now open the `.env` file in any text editor (Notepad works) and change the password:

```
DB_PASSWORD=change-me-to-something-secure
```

Replace `change-me-to-something-secure` with any password you like. This is for your local database only... it never leaves your machine.

> **Tip:** The `AI_PROVIDER` setting in `.env` is optional. Leave it as `none` for now. You can change it later if you want the platform to make AI calls directly.

### Start the platform

From the `supertroopers/code` folder:

```bash
docker compose up -d
```

The first time you run this, Docker downloads the required images (~2GB). This takes a few minutes depending on your internet speed. Subsequent starts are fast.

### Check that containers are running

```bash
docker ps
```

You should see **three containers**, all with status "Up":

| Container | Purpose | Port |
|-----------|---------|------|
| `supertroopers-db` | PostgreSQL database (with pgvector) | 5555 |
| `supertroopers-app` | Flask API + MCP SSE server | 8055, 8056 |
| `supertroopers-web` | React frontend | 5175 |

If any container shows "Restarting" or is missing, see the [Troubleshooting Guide](TROUBLESHOOTING.md).

---

## 5. Configure MCP Connection

MCP (Model Context Protocol) is how your AI assistant talks to SuperTroopers. You need a small config file to set this up.

### Copy the example config

The file `code/.mcp.json.example` contains the connection settings. Copy it to `.mcp.json` in the **project root** (one level up from `code/`):

**On Windows (Command Prompt):**
```cmd
cd supertroopers
copy code\.mcp.json.example .mcp.json
```

**On Windows (Git Bash / WSL) or Mac:**
```bash
cd supertroopers
cp code/.mcp.json.example .mcp.json
```

The file should look like this:

```json
{
  "mcpServers": {
    "supertroopers": {
      "type": "sse",
      "url": "http://localhost:8056/sse"
    }
  }
}
```

### Test the connection

Open a terminal in the project root directory (`supertroopers/`) and start Claude Code:

```bash
claude
```

Once Claude starts, ask it:

> "What MCP tools do you have?"

Claude should list the SuperTroopers tools (there are 42 of them). If it does, the connection is working.

> **Tip:** If tools don't appear, quit Claude Code (type `/exit`), make sure `.mcp.json` is in the project root directory (not inside `code/`), make sure Docker containers are running (`docker ps`), and try again.

---

## 6. Verify Everything Works

Before uploading your data, run through this checklist to make sure all services are healthy.

| Check | How | What you should see |
|-------|-----|---------------------|
| **API** | Open http://localhost:8055/api/health in your browser | `{"status":"healthy","db":"connected"}` |
| **Frontend** | Open http://localhost:5175 in your browser | The SuperTroopers dashboard loads |
| **Settings** | Click "Settings" in the sidebar on the dashboard | System Status section shows green indicators |
| **MCP** | In Claude Code, ask "What tools do you have?" | A list of SuperTroopers tools |

If any of these fail, check the [Troubleshooting Guide](TROUBLESHOOTING.md) for solutions.

> **Tip:** Bookmark http://localhost:5175 in your browser. That's your dashboard for the whole platform.

---

## 7. Upload Your First Resume

This is the fun part. SuperTroopers parses your resume, extracts your career history, bullets, and skills, and stores everything in a structured database.

Have your resume file ready (.docx or .pdf).

### Option A -- Via Claude Code (recommended)

Tell Claude:

> "Upload my resume at C:/Users/me/Documents/my_resume.docx"

(Replace the path with your actual file location.)

Claude will use the `onboard_resume` tool automatically.

### Option B -- Via MCP tool directly

In Claude Code, say:

> "Use the onboard_resume tool with file_path C:/Users/me/Documents/my_resume.docx"

### Option C -- Via API

```bash
curl -X POST http://localhost:8055/api/onboard/upload -F "files=@/path/to/resume.docx"
```

### What happens next

The upload pipeline does several things automatically:

1. **Extracts text** from your .docx or .pdf
2. **Parses career history** -- employers, roles, dates
3. **Extracts bullets** -- your accomplishments and responsibilities
4. **Identifies skills** -- technical and professional skills
5. **Creates a template** -- the visual layout of your resume
6. **Builds a recipe** -- instructions for generating new resumes
7. **Generates a test resume** -- to compare against your original

You'll get a report showing:
- Number of employers, bullets, and skills extracted
- Template ID and Recipe ID (you'll use these later)
- Match score (how close the generated resume is to your original)

Check the frontend dashboard at http://localhost:5175 -- your career data should now be populated.

---

## 8. Generate a Test Resume

Now that your data is loaded, generate a resume to make sure everything works end to end.

Tell Claude:

> "Generate a resume using the recipe from my upload"

Or if you know the recipe ID from the upload report:

> "Generate a resume with recipe ID 1"

The output is a .docx file. Open it in Word and compare it to your original. The match score from the upload tells you how close the generated version is.

---

## 9. Next Steps

You're set up. Here's what you can do now:

**Customize your voice** -- Go to Settings in the dashboard and configure voice rules so generated text sounds like you, not like a robot.

**Search for jobs** -- Tell Claude: "Search for VP Engineering roles in tech" (requires Indeed MCP integration).

**Tailor a resume** -- Paste a job description to Claude and ask: "How well do I match this job?" Then: "Tailor my resume for this role."

**Track applications** -- Tell Claude: "I applied to Acme Corp for CTO on March 20."

**Company research** -- Tell Claude: "What do you know about Acme Corp?"

**Manage contacts** -- Tell Claude: "Do I have any connections at Acme Corp?"

For the full list of 42 tools and what they do, see the [MCP Tool Reference](MCP_REFERENCE.md).

---

## 10. Using Other AI Agents

SuperTroopers works with any MCP-compatible AI agent, not just Claude Code.

**Connection endpoint:** `http://localhost:8056/sse` (SSE transport)

### Gemini CLI

Configure MCP in your Gemini settings to point to the SSE endpoint above.

### Cursor / Windsurf

Add an MCP server in your editor settings:
- Type: SSE
- URL: `http://localhost:8056/sse`

### Other MCP clients

Any tool that supports the Model Context Protocol with SSE transport can connect. Use the URL `http://localhost:8056/sse`.

### Project instructions

The `CLAUDE.md` file in the project root contains operational instructions (routing, voice rules, workflows). If your agent supports project-level instructions, adapt `CLAUDE.md` for your agent's format.

---

## 11. Stopping and Starting

### Stop everything

```bash
cd supertroopers/code
docker compose down
```

### Start again

```bash
cd supertroopers/code
docker compose up -d
```

### Your data is safe

The database is stored on your local filesystem (in `local_code/db_data/`). It persists between stops and starts. You only lose data if you delete that folder.

### Rebuild after pulling updates

If you pull new code from GitHub:

```bash
cd supertroopers/code
docker compose up -d --build
```

This rebuilds the containers with the latest code while keeping your data intact.

---

## Quick Reference

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend dashboard | http://localhost:5175 | Your main interface |
| API health check | http://localhost:8055/api/health | Verify API is running |
| MCP SSE endpoint | http://localhost:8056/sse | AI agent connection |

| Doc | Purpose |
|-----|---------|
| [MCP Tool Reference](MCP_REFERENCE.md) | All 42 tools with parameters and examples |
| [Troubleshooting Guide](TROUBLESHOOTING.md) | Fix common issues |

---

*Need help? Check the [Troubleshooting Guide](TROUBLESHOOTING.md) first. If your issue isn't covered there, open a GitHub issue.*
