# Job Search

How to find jobs, evaluate fit, triage your inbox, and save promising opportunities.

---

## Concepts

**Fresh Jobs Inbox** -- New job leads from any source (Indeed, LinkedIn, recruiter emails, manual saves) land here first. They stay in "new" status until you triage them.

**Saved Jobs** -- Jobs you've decided to evaluate further. They sit in a queue where you can run gap analyses, score fit, and decide whether to apply.

**Triage** -- The process of reviewing fresh jobs and deciding: save (move to evaluation queue), pass (not interested), or snooze (revisit later).

---

## Workflow 1: Search and Save Jobs

### Search with an external tool

If you have the Indeed MCP integration configured:

> "Search Indeed for VP Engineering roles in Florida"

Or use any job board manually and paste the job description to Claude.

### Save a job manually

> "Save this job: VP Engineering at Acme Corp, here's the URL: https://..."

Claude calls `save_job` with the title, company, URL, and any JD text you provide.

### Save with job description text

> "Save this job and here's the full description: [paste JD]"

Having the JD text stored enables automated gap analysis and fit scoring.

---

## Workflow 2: Triage Fresh Jobs

### Check your inbox

> "What fresh jobs do I have?"

This calls `get_fresh_jobs(status="new")` and shows unreviewed leads.

### Triage one at a time

> "Triage job 15 as save" -- moves to evaluation queue
> "Triage job 16 as pass" -- marks as not interested
> "Triage job 17 as snooze" -- revisit later

### Batch triage

> "Batch triage: save jobs 15 and 18, pass on 16 and 17"

Claude calls `batch_triage` with your decisions in one call.

---

## Workflow 3: Evaluate Fit

### Quick fit score

> "What's my fit score for saved job 12?"

Calls `quick_fit_score` for a keyword-based match against your skills.

### Full gap analysis

> "Run a gap analysis on saved job 12"

Or paste the JD directly:

> "How well do I match this role? [paste JD]"

Claude calls `match_jd` and returns:
- Strong matches with your best bullets
- Gaps where you lack coverage
- Overall coverage percentage
- Recommendation (apply / consider / pass)

### Save the analysis

> "Save this gap analysis linked to saved job 12"

Stores the results in the database for later reference.

---

## Workflow 4: Manage Your Saved Jobs Queue

### List saved jobs by status

> "Show me my saved jobs"
> "What jobs am I currently evaluating?"
> "Which saved jobs have I decided to apply for?"

### Update a saved job

> "Mark saved job 12 as applying with fit score 8.5"
> "Add notes to saved job 12: strong match on cloud architecture"

### Convert to application

When you're ready to apply:

> "Convert saved job 12 to an application"

This creates an application record and links it to the saved job.

---

## Workflow 5: Skill Demand Analysis

### See what skills are in demand

> "What skills are employers looking for across my saved JDs?"

Calls `analyze_skill_demand` to aggregate skill requirements across all stored job descriptions.

### Check for trending skills

> "Check for skill trend alerts"

Identifies trending skills that appear frequently in JDs but are missing from your profile.

---

## Workflow 6: Recruiter Email Detection

### Scan for recruiter outreach

> "Scan my emails for recruiter messages"

Calls `detect_recruiter_emails` which identifies recruiter outreach and automatically creates fresh job entries and contact records.

---

## Workflow 7: Market Intelligence

### Track market signals

> "What market intelligence do I have?"
> "Add a market signal: Acme Corp just raised Series C"

### View market summary

> "Give me a market summary"

Shows signal counts by type, trending sectors, and recent highlights.

---

## Tips

- Save JD text whenever possible... it enables automated gap analysis and skill demand tracking
- Triage fresh jobs regularly to keep the inbox manageable
- Use fit scores to prioritize which applications to invest time in
- Link gap analyses to saved jobs so you can reference them during resume tailoring
- Check stale saved jobs periodically: "Show me saved jobs I haven't touched in 2 weeks"
