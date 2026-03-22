# Getting Started

Your first session with SuperTroopers, from install to working data.

---

## What You Need

- Docker Desktop installed and running
- Claude Code (or any MCP-compatible AI agent)
- A .docx or .pdf resume

If you haven't installed yet, follow the [Setup Guide](../SETUP.md) first.

---

## Step 1: Start the Platform

Open a terminal and navigate to the project's `code/` directory:

```bash
cd supertroopers/code
docker compose up -d
```

Wait about 30 seconds for all services to start. Verify with:

```bash
docker ps --filter "name=supertroopers"
```

You should see three containers running: `supertroopers-db`, `supertroopers-app`, `supertroopers-web`.

---

## Step 2: Open the Dashboard

Go to [http://localhost:5175](http://localhost:5175) in your browser. The dashboard will be mostly empty since you haven't loaded any data yet.

---

## Step 3: Connect Your AI Agent

Start Claude Code in the project root directory (one level above `code/`):

```bash
cd supertroopers
claude
```

Claude Code reads `.mcp.json` from the project root and connects to the MCP server automatically. Verify by asking:

> "What MCP tools do you have?"

You should see a list of SuperTroopers tools.

---

## Step 4: Upload Your Resume

Tell Claude:

> "Upload my resume at C:/path/to/my_resume.docx"

The `onboard_resume` tool runs automatically. It:

1. Extracts text from your document
2. Parses employers, roles, dates, and bullets
3. Identifies your skills
4. Creates a resume template from the document layout
5. Builds an initial recipe for regeneration
6. Generates a test resume and compares it to your original

You'll get a report showing how many items were extracted and a match score.

---

## Step 5: Verify Your Data

After uploading, check the dashboard at [http://localhost:5175](http://localhost:5175). You should see:

- **Career History** populated with your employers and roles
- **Bullets** extracted from your resume
- **Skills** identified from your experience
- **Resume Recipes** with your initial recipe

You can also ask Claude:

> "Show me my career history"
> "What skills do I have?"
> "List my resume recipes"

---

## Step 6: Generate a Test Resume

Ask Claude:

> "Generate a resume using my latest recipe"

This produces a .docx file. Open it and compare to your original. The match score from onboarding tells you how close the regeneration is.

---

## What to Do Next

Now that your data is loaded, you can:

- **Tailor resumes** -- paste a job description and ask Claude to match it against your bullets, then generate a tailored version. See [Resume Generation Guide](02_resume_generation.md).
- **Search for jobs** -- ask Claude to find roles that match your profile. See [Job Search Guide](03_job_search.md).
- **Track applications** -- log where you've applied and follow up on stale applications. See [Application Tracking Guide](04_application_tracking.md).
- **Prepare for interviews** -- build prep materials and run debriefs. See [Interview Prep Guide](05_interview_prep.md).
- **Manage your network** -- track contacts and find warm introductions. See [Networking Guide](06_networking.md).

---

## Quick Reference

| What | How |
|------|-----|
| Start platform | `docker compose up -d` from `code/` |
| Stop platform | `docker compose down` from `code/` |
| Dashboard | http://localhost:5175 |
| API health | http://localhost:8055/api/health |
| MCP connection | http://localhost:8056/sse |
| Full tool list | [MCP Tool Reference](../MCP_REFERENCE.md) |
| API endpoints | [API Reference](../API_REFERENCE.md) |
