# Networking

How to manage contacts, track relationships, find warm introductions, and maintain your professional network.

---

## Concepts

**Contact** -- A person in your professional network with name, company, title, relationship notes, and communication history.

**Relationship Health** -- A computed score based on recency and frequency of contact. Low scores mean the relationship needs attention.

**Touchpoint** -- Any interaction with a contact: email, call, coffee, LinkedIn message, referral, etc.

**Warm Path** -- A connection chain to a target company through your existing contacts.

**Networking Task** -- A scheduled action like "Follow up with Jane at Acme Corp" with a due date.

---

## Workflow 1: Manage Contacts

### Search your contacts

> "Who do I know at Google?"
> "Find my contact Sarah"

Calls `search_contacts` with company or name filters.

### Add a new contact

Use the API or dashboard to create contacts. From Claude:

> "Add a contact: Jane Smith, VP Engineering at Acme Corp, met at re:Invent 2024"

### Update contact info

> "Update Jane Smith's title to CTO"

### View all contacts at a company

> "Show me all my contacts at Lockheed Martin"

---

## Workflow 2: Track Relationship Health

### Check who needs attention

> "Which relationships need attention?"

Calls `get_relationship_health` and returns contacts ranked by health score (lowest first). Contacts you haven't interacted with recently bubble to the top.

### Check a specific contact

> "How's my relationship with Jane Smith?"

Returns the health score, last touchpoint date, and interaction history.

### Update relationship stage

> "Move Jane Smith to 'warm' relationship stage"

Stages help you categorize contacts: cold, warming, warm, strong, dormant.

---

## Workflow 3: Log Interactions

### Log a touchpoint

> "I had coffee with Jane Smith today"
> "I sent a LinkedIn message to Bob at Acme Corp"
> "Jane referred me to the VP Engineering role at Acme Corp"

Calls `log_touchpoint` with the contact ID, interaction type, channel, and notes. This automatically updates the last_touchpoint_at timestamp and recalculates relationship health.

### Touchpoint types

| Type | Examples |
|------|----------|
| email | Sent/received email |
| linkedin | LinkedIn message or comment |
| phone | Phone call |
| meeting | Coffee, lunch, video call |
| event | Conference, meetup |
| referral | They referred you or vice versa |
| intro | They made an introduction |

---

## Workflow 4: Find Warm Introductions

### Check for warm paths to a company

> "Do I have any connections at Palantir?"

Calls `network_check` and returns:
- Direct contacts at the company
- Related email threads
- Application history
- Whether you have a warm intro available

### Find warm paths

> "Find warm intro paths to Acme Corp"

Calls `find_warm_paths` which analyzes your contact network to find:
- Direct contacts at the company
- Contacts who previously worked there
- Contacts connected to people at the company
- Strength rating for each path

---

## Workflow 5: Networking Tasks

### View upcoming tasks

> "What networking tasks do I have this week?"

Calls `get_networking_tasks` and returns pending tasks sorted by due date.

### Create a task

> "Remind me to follow up with Jane Smith next Tuesday"

### Complete a task

> "Mark networking task 5 as complete"

---

## Workflow 6: Import LinkedIn Connections

### Import connections

If you export your LinkedIn connections as CSV:

> "Import my LinkedIn connections from the CSV"

Calls `import_linkedin_connections` which creates contact records for each connection with name, company, title, and connection date.

### Import profile data

> "Import my LinkedIn profile data"

Calls `import_linkedin_profile` which adds career history and skills from your LinkedIn profile to supplement your resume data.

---

## Workflow 7: Outreach

### Generate outreach messages

> "Draft an outreach message to Jane Smith about the VP Engineering role at Acme Corp"

Claude uses your contact history, company dossier, and voice rules to craft a personalized message.

### Batch outreach

> "Generate outreach for my top 5 contacts at target companies"

Calls `batch_outreach` to draft messages for multiple contacts in one pass.

### Track outreach

> "Show me my pending outreach follow-ups"

Returns outreach messages that are waiting for a response.

---

## Workflow 8: Referral Tracking

### Log a referral

Use the dashboard or API to track referrals received and given.

### View referrals

> "Show me my referrals"

Returns all referral records with status and outcome.

---

## Tips

- Log every meaningful interaction as a touchpoint... the relationship health score depends on it
- Review relationship health weekly and reach out to contacts going dormant
- Before applying to a company, always check for warm paths first
- Import LinkedIn connections early to populate your contact database
- Use networking tasks to stay disciplined about follow-ups
- When someone refers you, log both the referral and a touchpoint
- Keep contact notes detailed... "Met at re:Invent 2024, discussed cloud migration" is much more useful than just "conference contact"
