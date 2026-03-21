# Networking & CRM Feature Research — Synthesis for Job Seeker Platform

**Date:** 2026-03-21
**Purpose:** Competitive analysis of CRM/networking tools, distilled into functional requirements for SuperTroopers networking module targeting senior executive job search.

---

## Sources Analyzed

### Job-Seeker Tools
- **Huntr** — Contact tracker with basic fields (name, title, company, email, phone, social handles), linked to job applications
- **Teal** — Contacts tracker with relationship classification, custom tags (Mentor, Colleague, Industry Expert), follow-up scheduling, contact-to-application linking, 40+ email templates

### Sales CRMs (Patterns Applicable to Job Search)
- **HubSpot CRM (Free)** — Contact management, deal pipeline, sequences (timed drip emails), email tracking, task management, reporting
- **Streak CRM** — Gmail-native pipeline, magic columns (auto-track last interaction, engagement metrics), email open/click tracking, follow-up sequences, mail merge, AI deal summaries
- **Folk CRM** — Relationship-first CRM (not deal-first), waterfall enrichment from 6+ providers, AI follow-up assistant detecting stale conversations, Chrome extension for LinkedIn capture
- **Clay** — 150+ enrichment providers via waterfall, buying signals (job changes, funding, hiring trends), AI-personalized outreach, sequence automation
- **Apollo.io** — Contact enrichment (demographic, firmographic, technographic), multi-channel sequences (email, call, social, tasks), prospect scoring, AI research agents

### Networking Intelligence
- **LinkedIn Sales Navigator** — Relationship Explorer (surface decision-makers), Relationship Map (org chart visualization), alerts on job changes/posts, lead scoring by engagement + fit, custom lists, notes on leads

---

## Feature Synthesis: What Matters Most for Executive Job Search

### 1. Contact Enrichment (AUTO-PULL)

**What the best tools do:**
- Clay/Apollo: Waterfall enrichment across 100-150+ data providers until data is found
- Folk: Built-in enrichment from Apollo, People Data Labs, Clearbit, Datagma, Prospeo, DropContact
- Sales Nav: Surface role, tenure, recent activity, mutual connections

**What we should build:**
- On contact creation, auto-enrich from LinkedIn profile URL: current title, company, tenure, location, mutual connections count
- Company enrichment: size, industry, funding stage, recent news, tech stack
- Periodic re-enrichment to catch job changes (a contact changing jobs = warm outreach trigger)
- **Priority: HIGH** — This is table stakes for executive networking. Manual data entry kills adoption.

### 2. Relationship Scoring / Health

**What the best tools do:**
- Apollo: Prospect scoring based on engagement + fit signals
- Streak: Magic columns auto-calculate last interaction date, interaction count, engagement metrics
- Sales Nav: Lead scoring by ICP fit + engagement patterns
- HubSpot: Lead scoring based on properties + behaviors

**What we should build:**
- **Relationship Health Score** (0-100) computed from:
  - Recency of last touchpoint (decays over time)
  - Frequency of interactions (emails sent/received, meetings, LinkedIn engagement)
  - Reciprocity (are they responding? initiating?)
  - Depth (surface networking vs. substantive conversation)
  - Relevance to current targets (are they at a target company? in a decision-making role?)
- **Staleness alerts** when relationships decay below threshold
- **Priority: HIGH** — Executive searches are won through warm relationships. Scoring tells you where to invest time.

### 3. Touchpoint Tracking & Cadence

**What the best tools do:**
- Streak: Auto-logs every email, tracks opens/clicks, interaction timeline per contact
- HubSpot: Full activity timeline, call logging, meeting logging, email tracking
- Folk: AI detects stale conversations, suggests follow-ups with context
- Teal: Follow-up scheduling with reminders

**What we should build:**
- **Automatic touchpoint logging** from email (Gmail integration) — every sent/received email tagged to the contact
- **Manual touchpoint logging** — coffee meetings, phone calls, LinkedIn messages, events, referral requests
- Touchpoint types: Email, Call, Meeting (coffee/lunch/formal), LinkedIn Message, LinkedIn Engagement (like/comment), Event/Conference, Referral Request, Intro Made, Thank You
- **Cadence recommendations** based on relationship stage:
  - New connection: touch within 48 hours
  - Active networking: every 2-3 weeks
  - Warm relationship maintenance: monthly
  - Dormant reactivation: quarterly check-in
- **Priority: HIGH** — The difference between "networking" and "stalking" is cadence intelligence.

### 4. Drip Sequences / Follow-Up Automation

**What the best tools do:**
- Apollo: Multi-step sequences with email, call, social tasks, auto-send or manual review
- HubSpot: Timed email sequences with personalization tokens, auto-unenroll on reply
- Streak: Follow-up sequences triggered by no-reply, with wait times and merge fields
- Clay: AI-personalized email copy using enrichment data

**What we should build:**
- **Sequence templates** for common job search scenarios:
  - Post-application follow-up (Day 3, Day 10, Day 21)
  - Post-informational-interview nurture (Day 1 thank you, Day 14 article share, Day 30 check-in)
  - Recruiter relationship maintenance (monthly value-add touches)
  - Warm intro request sequence (ask, follow-up, thank regardless)
  - Conference/event follow-up (Day 1, Day 7, Day 30)
- **Draft generation** using voice rules + contact context (not generic templates)
- **Auto-pause** on reply (don't send follow-up #2 if they already responded)
- **Task creation** for non-email steps (call them, engage on LinkedIn, send article)
- **Priority: MEDIUM** — Valuable but needs to feel authentic, not automated. For exec search, every touch should feel personal. AI drafts reviewed before send.

### 5. Pipeline Stages for Relationships

**What the best tools do:**
- HubSpot: Customizable deal stages with probability weighting
- Streak: Kanban pipeline with custom stages, drag-and-drop
- Huntr: Job pipeline (Wishlist > Applied > Interview > Offer)
- Sales Nav: Custom lists for organizing leads by status

**What we should build:**
- **Relationship Pipeline** (distinct from application pipeline):
  - **Identified** — Found them, no contact yet
  - **Connected** — LinkedIn connection accepted or email exchanged
  - **Engaged** — Had a real conversation (informational, coffee, call)
  - **Warm** — Mutual value established, they'd take your call
  - **Advocate** — They're actively helping (referring, introducing, recommending)
  - **Dormant** — Was warm, gone cold (needs reactivation)
- Contacts can be in multiple pipelines (relationship pipeline + linked to application pipeline)
- **Priority: HIGH** — This is the core mental model. Every contact should have a clear "where are we" status.

### 6. Email Integration (Tracking Opens, Replies)

**What the best tools do:**
- Streak: Open tracking with real-time notifications, device type, location, click tracking on links
- HubSpot: Email tracking, open/click notifications, activity logging
- Apollo: Email engagement tracking feeding into prospect scoring

**What we should build:**
- **Gmail integration** for automatic send/receive logging to contacts
- **Open tracking** (pixel-based) — know when they read your email
- **Link click tracking** — know when they viewed your resume/portfolio
- **Reply detection** — auto-update touchpoint log and relationship score
- **Thread association** — link email threads to contacts AND applications
- **Priority: MEDIUM** — Open tracking is useful but can feel invasive for executive networking. Reply detection and auto-logging are the real wins.

### 7. Task / Reminder Management

**What the best tools do:**
- HubSpot: Tasks with due dates, queues, associations to contacts/deals
- Streak: Task management with notifications, linked to pipeline items
- Teal: Follow-up reminders and checklists per application
- Folk: AI-suggested follow-ups based on conversation analysis

**What we should build:**
- **Auto-generated tasks** from:
  - Sequence steps (call John on Thursday)
  - Staleness alerts (haven't talked to Sarah in 30 days)
  - Application milestones (follow up 1 week after applying)
  - Interview prep (research company 2 days before interview)
- **Manual tasks** with due dates, linked to contacts and/or applications
- **Daily digest** — "Today: 3 follow-ups due, 2 thank-you notes, 1 intro to request"
- **Priority: HIGH** — Executive job search has dozens of parallel threads. Without task management, balls get dropped.

### 8. Warm Intro / Path Finding

**What the best tools do:**
- Sales Nav: Relationship Explorer surfaces mutual connections, TeamLink shows company network paths
- Apollo: Org charts and reporting structures
- Clay: Signal-based triggers (someone changed jobs to your target company)

**What we should build:**
- **Path finder** — Given a target person/company, show:
  - Direct connections who work there
  - Second-degree connections (who can intro you)
  - Alumni connections (same school, same previous employer)
  - Shared group/community membership
- **Intro request workflow** — Template + tracking for asking a mutual connection to introduce you
- **Job change alerts** — When a contact moves to a target company, flag as warm intro opportunity
- **Priority: HIGH** — At the executive level, warm intros are THE highest-converting channel. This is a differentiator.

### 9. Company Intelligence

**What the best tools do:**
- Clay: Company enrichment (size, funding, tech stack, hiring trends, news)
- Apollo: Firmographic + technographic data, org charts
- Sales Nav: Company insights, headcount growth, new hires in role
- HubSpot: Company records with auto-enrichment

**What we should build:**
- **Company profiles** enriched with: size, industry, funding, leadership, tech stack, Glassdoor rating, recent news
- **Hiring signals** — job postings in your function, headcount growth in your area, new leadership (new CTO = new priorities = new hires)
- **Contact map per company** — all your contacts at Company X, their roles, your relationship stage
- **Company-level relationship score** — aggregate of individual contact scores
- Already partially built via `get_company_dossier` and `search_companies` — extend with networking overlay
- **Priority: MEDIUM** — Good to have, partially exists. The contact map per company is the new piece.

### 10. Reporting & Analytics

**What the best tools do:**
- HubSpot: Dashboards with deal velocity, activity metrics, pipeline conversion
- Streak: Reports on pipeline stages, email performance, campaign metrics
- Apollo: Sequence performance, engagement rates, reply rates
- Huntr: Job search metrics (applications per week, response rates)

**What we should build:**
- **Networking activity metrics:**
  - Touchpoints logged per week (are you doing the work?)
  - Response rate by outreach type (cold email vs. warm intro vs. LinkedIn)
  - Relationship pipeline conversion (Identified > Connected > Engaged > Advocate)
  - Average time in each relationship stage
- **Network health dashboard:**
  - Total contacts by stage
  - Contacts going stale (need attention)
  - Coverage at target companies (how many contacts at each)
  - Warm intro availability per target company
- **Outreach effectiveness:**
  - Which email templates get responses
  - Best day/time for outreach
  - Which intro sources convert best
- **Priority: MEDIUM** — Analytics inform strategy. Not needed for MVP but critical for iteration.

---

## Recommended Build Priority

### Phase 1 — Foundation (Must Have)
1. **Contact model** with enrichment fields and relationship stage
2. **Relationship pipeline** (Identified > Connected > Engaged > Warm > Advocate > Dormant)
3. **Touchpoint logging** (manual + Gmail auto-capture)
4. **Relationship health scoring** (recency, frequency, reciprocity)
5. **Task/reminder system** with auto-generation from staleness + sequences
6. **Warm intro path finding** (mutual connections, alumni overlap)

### Phase 2 — Intelligence (Should Have)
7. **Contact enrichment** from LinkedIn data
8. **Company contact map** (all your contacts at target companies)
9. **Follow-up sequence templates** with AI draft generation
10. **Daily networking digest** (tasks due, contacts going stale, opportunities)

### Phase 3 — Optimization (Nice to Have)
11. **Email open/click tracking**
12. **Networking analytics dashboard**
13. **Job change alerts** for contacts
14. **Cadence recommendations** by relationship stage
15. **Outreach A/B insights** (what messaging works)

---

## Key Insight: What Job-Seeker Tools Get Wrong

Huntr and Teal treat contacts as an appendage to applications. They store contact info but don't help you **work the relationship**. The real value is in sales CRM patterns:

1. **Relationships are the pipeline, not applications.** A strong network produces opportunities. Applications are a downstream artifact.
2. **Automation must feel personal.** At the executive level, a mass-mail-merge follow-up is career poison. AI should draft, human should review and personalize.
3. **Scoring drives behavior.** Without health scores, you don't know which relationships need investment. You end up over-nurturing easy contacts and neglecting high-value ones.
4. **Path finding is the killer feature.** Knowing that your former colleague's wife works at your target company... that's how executive jobs get filled. No job-seeker tool does this well.
5. **Company-level relationship mapping** — seeing "I have 3 contacts at Company X: one Advocate, one Connected, one Identified" changes your strategy entirely.

---

## Sources

- [Huntr Contact Tracker](https://huntr.co/product/contact-tracker)
- [Teal Networking CRM](https://www.tealhq.com/tool/networking-crm)
- [Teal Contacts Tracker](https://www.tealhq.com/tools/contacts-tracker)
- [HubSpot Free CRM](https://www.hubspot.com/products/crm)
- [HubSpot Deal Pipeline](https://www.hubspot.com/products/sales/deal-pipeline)
- [Streak CRM Features](https://www.streak.com/features)
- [Folk CRM Contact Enrichment](https://www.folk.app/products/contact-enrichment)
- [Folk CRM Review](https://www.breakcold.com/blog/folk-crm-review)
- [Clay.com Platform](https://www.clay.com/)
- [Clay Data Enrichment Guide](https://www.smarte.pro/blog/clay-data-enrichment)
- [Apollo.io Sales Platform](https://www.apollo.io/)
- [Apollo Enrichment Overview](https://knowledge.apollo.io/hc/en-us/articles/33699917233293-Enrichment-Overview)
- [Apollo Sequences Overview](https://knowledge.apollo.io/hc/en-us/articles/4409237165837-Sequences-Overview)
- [LinkedIn Sales Navigator](https://business.linkedin.com/sales-solutions/sales-navigator)
- [Sales Navigator Lead Scoring Guide](https://www.breakcold.com/how-to/how-to-use-linkedin-sales-navigator-for-lead-scoring)
- [Nimble CRM for Personal Networking](https://www.nimble.com/blog/crms-for-personal-networking-building-stronger-connections/)
