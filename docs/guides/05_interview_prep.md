# Interview Prep

How to prepare for interviews, run mock sessions, and capture debriefs.

---

## Concepts

**Interview Prep** -- Structured preparation materials for an upcoming interview: company research, prepared questions, STAR stories, talking points, and questions to ask the interviewer.

**Mock Interview** -- A practice session where Claude asks you questions based on the role and company, then evaluates your responses.

**Interview Debrief** -- A structured post-interview record capturing what went well, what went poorly, questions asked, lessons learned, and next steps.

---

## Workflow 1: Prepare for an Interview

### Auto-generate prep materials

> "Prepare me for my interview at Acme Corp (interview ID 5)"

When you set `auto_generate=True`, the tool automatically:
- Pulls the company dossier with latest intelligence
- Selects relevant STAR stories from your bullet database
- Pulls mock interview questions for similar roles
- Generates suggested questions to ask the interviewer

### Manual prep

> "Save interview prep for interview 5 with these talking points: [list]"

You can provide any combination of:
- Company dossier (research snapshot)
- Prepared questions and answers
- Talking points
- Selected STAR stories
- Questions to ask the interviewer

### Review your prep

> "Show me my prep for interview 5"

Returns all saved prep materials for that interview.

---

## Workflow 2: Company Research

Before any interview, get a full company dossier:

> "Give me a full dossier on Acme Corp"

Calls `get_company_dossier` and returns:
- Company overview (sector, size, location, stage)
- Your contacts at the company
- Application history
- Related emails
- Interview history
- Hiring patterns

### Check for warm introductions

> "Do I have any connections at Acme Corp?"

Calls `network_check` to find contacts and related communications.

---

## Workflow 3: Mock Interviews

### Create a mock interview

> "Set up a mock interview for a VP Engineering role at Acme Corp"

Claude creates a mock interview session with role-appropriate questions covering:
- Behavioral questions (STAR format)
- Technical questions
- Leadership scenarios
- Culture fit

### Run the mock

> "Start the mock interview"

Claude asks questions one at a time, waits for your response, then asks follow-up questions as a real interviewer would.

### Get evaluated

> "Evaluate my mock interview performance"

Returns feedback on:
- Answer quality and structure
- STAR story completeness
- Areas of strength
- Areas for improvement
- Suggested practice areas

---

## Workflow 4: Post-Interview Debrief

### Record a debrief immediately after

> "Debrief my interview at Acme Corp (interview 5)"

Claude walks you through a structured debrief:

**What went well:**
> "The conversation about cloud migration really clicked. They seemed impressed by the $2.3M savings metric."

**What went poorly:**
> "I stumbled on the question about Kubernetes orchestration at scale."

**Questions asked:**
> "They asked about my experience with distributed teams and how I handle underperformers."

**Overall feeling:**
> "Good... I think I'm moving forward but the technical depth concern is real."

**Next steps:**
> "They said they'd get back within a week. I should send a thank-you to the panel."

**Lessons learned:**
> "Need to prepare better examples for container orchestration at scale."

### Review past debriefs

> "Show me my debrief for interview 5"
> "What lessons have I learned from my interviews?"

### Interview analytics

> "Show me my interview analytics"

Calls `get_interview_analytics` for aggregate performance data across all interviews.

---

## Workflow 5: Thank-You Messages

After an interview:

> "Draft a thank-you note for my interview at Acme Corp"

Claude uses the debrief data to craft a personalized thank-you that:
- References specific conversation points
- Reinforces your strongest talking points
- Addresses any concerns raised
- Follows your voice rules

---

## Workflow 6: Calendar Intelligence

### Detect upcoming interviews

> "Check my calendar for upcoming interviews"

If Google Calendar MCP is connected, this scans for interview-like events and links them to applications.

### Find interviews needing prep

> "Which interviews need prep?"

Returns upcoming interviews that don't have prep materials saved yet.

---

## Tips

- Always debrief immediately after an interview while details are fresh
- Use auto_generate for prep to save time... it pulls everything from your database
- Review debrief lessons before your next interview at the same company
- Link interview prep to the application so all context stays connected
- Run mock interviews for roles you really want... practice makes a measurable difference
- Send thank-you notes within 24 hours of the interview
