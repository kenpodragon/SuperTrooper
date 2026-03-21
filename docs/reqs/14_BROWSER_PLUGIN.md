# 14. Browser Plugin — SuperTroopers Chrome Extension

**Component of:** [0_APPLICATION_REQUIREMENTS.md](0_APPLICATION_REQUIREMENTS.md) Section 14
**Status:** Not Started
**Created:** 2026-03-20

---

## 0. Overview

### What It Is

A Chrome extension (Manifest V3) that augments the user's web browsing with job search capabilities backed by the SuperTroopers platform. The plugin connects exclusively to the LOCAL backend... no cloud services, no external APIs, no telemetry. Everything runs on the user's machine.

### Architecture

```
[Chrome Extension]
    |
    |-- Content Scripts (injected into job board / ATS pages)
    |-- Background Service Worker (message routing, API calls)
    |-- Popup UI (React, dark theme)
    |
    v
[localhost:8055]  Flask REST API  (105 endpoints)
[localhost:8056]  MCP SSE Server  (42 tools)
    |
    v
[PostgreSQL]  33 tables  (career data, applications, contacts, companies, recipes, etc.)
```

### Key Principle: Thin Client

The plugin is a **thin client**. It detects context (what page the user is on, what job listing they're viewing), sends that context to the backend, and displays the results. All intelligence... gap analysis, resume generation, voice checking, recipe customization... happens on the backend. The plugin never runs AI, never stores career data long-term, never phones home.

### Backend Endpoints Used

| Category | REST API (localhost:8055) | MCP Tools (localhost:8056) |
|----------|--------------------------|---------------------------|
| Jobs | POST/GET/PATCH/DELETE /api/saved-jobs, POST /api/saved-jobs/{id}/apply | save_job, list_saved_jobs, update_saved_job |
| Gap Analysis | POST /api/gap-analysis, GET/POST/PATCH/DELETE /api/gap-analyses | match_jd, save_gap_analysis, get_gap_analysis |
| Resume | POST /api/resume/generate, GET/POST/PUT/DELETE /api/resume/recipes | generate_resume, get_resume_data, list_recipes, get_recipe, create_recipe |
| Career Data | GET /api/career-history, GET /api/bullets, GET /api/skills, GET /api/education, GET /api/certifications | get_career_history, search_bullets, get_skills, get_candidate_profile |
| Profile | GET /api/resume-header, GET /api/summary-variants | get_summary_variant, update_header |
| Applications | GET/POST/PATCH /api/applications | search_applications, add_application, update_application |
| Companies | GET /api/search/companies | search_companies, get_company_dossier |
| Contacts | GET /api/contacts, GET /api/outreach, GET /api/referrals | search_contacts, network_check |
| Voice | GET /api/voice-rules | get_voice_rules, check_voice |
| Analytics | GET /api/analytics/* | get_analytics |
| Health | GET /api/health | — |

---

## 1. Job Capture

Save job listings from any major job board or ATS career page to SuperTroopers with one click.

- [ ] **14.1.1** Detect job listing pages on major job boards (Indeed, LinkedIn, Glassdoor) by URL pattern matching
- [ ] **14.1.2** Detect job listing pages on ATS career sites (Workday, Greenhouse, Lever, iCIMS, etc.) by URL pattern matching
- [ ] **14.1.3** Auto-extract job details from the page DOM: title, company, location, salary range, JD full text, source URL
- [ ] **14.1.4** Inject a "Save to SuperTroopers" button on detected job listing pages, positioned consistently near the job title or apply button
- [ ] **14.1.5** On click, POST extracted job data to `POST /api/saved-jobs` with status "saved"
- [ ] **14.1.6** Show save confirmation inline (button changes to checkmark + "Saved") without page reload
- [ ] **14.1.7** If the job URL already exists in saved_jobs, show "Already Saved" state on the button instead
- [ ] **14.1.8** Support manual save via popup: paste a URL, plugin fetches the page and extracts what it can
- [ ] **14.1.9** Maintain a bundled `siteConfig.json` mapping URL patterns to DOM extraction selectors per job board / ATS, updatable on extension release
- [ ] **14.1.10** Handle SPA navigation (LinkedIn, Glassdoor) by listening to URL changes via `webNavigation` and re-checking for job listing context

**Backend:** `POST /api/saved-jobs`, `save_job` MCP tool
**Tables:** `saved_jobs` (url, title, company, source, jd_text, jd_url, fit_score, status, notes)

---

## 2. Match / Fit Injection

When viewing a job listing, automatically assess fit against the user's career data and display results inline.

- [ ] **14.2.1** After detecting a job listing (same detection as 14.1), auto-send the JD text to the backend for gap analysis
- [ ] **14.2.2** Call `POST /api/gap-analysis` with the extracted JD text
- [ ] **14.2.3** Inject a match score overlay on the job listing page showing overall fit percentage (0-100%)
- [ ] **14.2.4** Color-code the score: green (>75%), yellow (50-75%), red (<50%)
- [ ] **14.2.5** Expandable overlay showing three categories: Strong Matches, Partial Matches, Gaps... each with specific skills/requirements listed
- [ ] **14.2.6** Cache gap analysis results in `chrome.storage.local` keyed by job URL to avoid re-running on page revisit (TTL: 24 hours)
- [ ] **14.2.7** "Refresh" button on the overlay to force re-analysis (bypasses cache)
- [ ] **14.2.8** If the job is already saved, persist the gap analysis to the backend via `POST /api/gap-analyses` and link to the saved_job record
- [ ] **14.2.9** Show a "Why this score?" tooltip explaining what skills/experience map to what requirements
- [ ] **14.2.10** Overlay must not obstruct the page's native apply button or key content

**Backend:** `POST /api/gap-analysis`, `match_jd` MCP tool, `save_gap_analysis` MCP tool
**Tables:** `gap_analyses` (saved_job_id, jd_text, strong_matches, partial_matches, gaps, fit_score, recommendations)

---

## 3. AI-Automated Resume & Cover Letter Generation

One-click generation of tailored resume and cover letter from any job listing page, powered entirely by the backend.

- [ ] **14.3.1** "Generate Materials" button injected on job listing pages (alongside or below the Save button)
- [ ] **14.3.2** On click, send JD text + job metadata to backend to trigger the full pipeline: gap analysis -> recipe selection/customization -> resume generation -> voice check
- [ ] **14.3.3** Show generation progress in a slide-out panel or modal: "Analyzing job...", "Selecting recipe...", "Generating resume...", "Checking voice...", "Done"
- [ ] **14.3.4** Backend generates .docx resume via `POST /api/resume/recipes/{id}/generate` (recipe-based) or `POST /api/resume/generate` (spec-based)
- [ ] **14.3.5** Backend generates cover letter text, plugin renders it and offers download as .docx
- [ ] **14.3.6** All generated text passes through `check_voice` on the backend before delivery to the plugin
- [ ] **14.3.7** Plugin receives file download URLs and offers "Download Resume" / "Download Cover Letter" buttons
- [ ] **14.3.8** Show the match score alongside generated materials so the user can see how well the tailored resume addresses gaps
- [ ] **14.3.9** Option to preview the generated resume content inline (rendered text, not full .docx layout) before downloading
- [ ] **14.3.10** Auto-save the job to `saved_jobs` if not already saved, and create a `generated_materials` record linking the output to the application
- [ ] **14.3.11** "Regenerate" button to re-run with a different recipe or adjusted parameters
- [ ] **14.3.12** Track generation history: which recipes were used, when, for which jobs

**Backend:** `POST /api/resume/generate`, `POST /api/resume/recipes/{id}/generate`, `generate_resume` MCP tool, `check_voice` MCP tool, `list_recipes` / `get_recipe` MCP tools
**Tables:** `generated_materials` (application_id, type, recipe_id, file_path, generated_at), `saved_jobs`, `gap_analyses`

---

## 4. Auto-Apply (Automated Form Filling)

On ATS application pages, auto-fill form fields from the user's profile data stored in SuperTroopers.

- [ ] **14.4.1** Detect ATS application forms by URL pattern matching against `siteConfig.json`
- [ ] **14.4.2** Fetch candidate profile data from backend: `GET /api/resume-header` (name, email, phone, location), `GET /api/education`, `GET /api/certifications`, `GET /api/career-history`, `GET /api/skills`
- [ ] **14.4.3** Cache profile data in `chrome.storage.local` with a configurable TTL (default 1 hour) to reduce backend calls
- [ ] **14.4.4** Map ATS form fields to candidate data using per-platform selector configs in `siteConfig.json`
- [ ] **14.4.5** Fire synthetic DOM events in the correct sequence to satisfy React/Angular/Vue form validation: `focus -> mousedown -> mouseup -> click -> keydown -> keypress -> textInput -> input -> keyup -> change -> blur`
- [ ] **14.4.6** Use a `pageScript.js` injected into the page's JS context (not extension sandbox) to fire native DOM events that bypass framework synthetic event checks
- [ ] **14.4.7** Handle standard fields: first name, last name, email, phone, address, city, state, zip, country
- [ ] **14.4.8** Handle work history fields: employer name, title, start/end dates, description (multi-entry)
- [ ] **14.4.9** Handle education fields: school, degree, major, graduation date (multi-entry)
- [ ] **14.4.10** Handle file upload fields: attach the most recently generated resume .docx or .pdf to the resume upload input
- [ ] **14.4.11** Handle social/link fields: LinkedIn URL, GitHub URL, portfolio URL from candidate profile
- [ ] **14.4.12** Handle work authorization and sponsorship questions from user settings
- [ ] **14.4.13** Handle EEO/demographic fields (disability, veteran, gender, ethnicity) ONLY if the user has explicitly opted in and configured values in settings
- [ ] **14.4.14** Handle salary expectation fields from user preferences + backend `get_salary_data`
- [ ] **14.4.15** Highlight all auto-filled fields with a subtle green border so the user can visually verify what was filled
- [ ] **14.4.16** Show a summary overlay: "Filled X of Y fields. Z fields need your attention." with links to unfilled fields
- [ ] **14.4.17** User MUST review and explicitly click a "Confirm & Submit" control before any form submission occurs... the plugin never auto-submits
- [ ] **14.4.18** Handle iframe-embedded application forms (`all_frames: true` for content script on ATS URLs only)
- [ ] **14.4.19** Detect "application submitted" confirmation pages to auto-confirm successful submission
- [ ] **14.4.20** Support multi-page application flows: maintain fill state across page navigations within the same ATS domain

**Backend:** `GET /api/resume-header`, `GET /api/career-history`, `GET /api/education`, `GET /api/certifications`, `GET /api/skills`, `get_candidate_profile` MCP tool, `get_salary_data` MCP tool
**Tables:** `resume_header`, `career_history`, `education`, `certifications`, `skills`

---

## 5. Application Tracking

Automatically create and update application records in the backend after applying, and surface pipeline status in the plugin.

- [ ] **14.5.1** After successful form submission detection (14.4.19), auto-create an application record via `POST /api/applications` with status "applied", linked to the saved_job if one exists
- [ ] **14.5.2** If materials were generated (section 3), link the `generated_materials` record to the new application
- [ ] **14.5.3** Badge on the extension icon showing active application count (applied + interviewing stages)
- [ ] **14.5.4** Badge updates on a timer (every 30 minutes) by polling `GET /api/analytics/summary`
- [ ] **14.5.5** Quick-view in popup: list of recent applications with status chips (saved, applied, interviewing, offered, rejected)
- [ ] **14.5.6** Click an application in the popup to see details: company, role, date applied, materials used, gap analysis score, status history
- [ ] **14.5.7** Status update from popup: user can manually change status (e.g., mark "interviewing" or "rejected") via `PATCH /api/applications/{id}`
- [ ] **14.5.8** Link to frontend dashboard for full pipeline view: open `localhost:5175/applications` in a new tab
- [ ] **14.5.9** Track "applied via plugin" vs "applied manually" as a source field on the application record
- [ ] **14.5.10** Popup shows a mini funnel: Saved -> Applied -> Interviewing -> Offered with counts at each stage

**Backend:** `POST /api/applications`, `PATCH /api/applications/{id}`, `GET /api/analytics/summary`, `add_application` MCP tool, `update_application` MCP tool, `search_applications` MCP tool, `get_analytics` MCP tool
**Tables:** `applications` (company, role, status, source, saved_job_id, gap_analysis_id), `application_status_history`, `generated_materials`

---

## 6. Networking Overlay

Show the user's existing contacts and network connections when viewing job listings or company pages.

- [ ] **14.6.1** On job listing pages, after detecting the company name, query backend: `GET /api/search/contacts?company={name}` to find known contacts at that company
- [ ] **14.6.2** On company career pages (e.g., company.com/careers), extract company name and run the same contact lookup
- [ ] **14.6.3** Inject a "Your Network" card on the page showing contact cards for known people at the company
- [ ] **14.6.4** Contact cards show: name, title, relationship strength, last contact date, referral status
- [ ] **14.6.5** Query `GET /api/referrals?company={name}` to show if any referral is active at this company
- [ ] **14.6.6** "No contacts yet" state with a "Find connections" action that opens the company in the frontend networking view
- [ ] **14.6.7** On LinkedIn company pages, show an overlay with contacts from the backend who work at that company
- [ ] **14.6.8** On LinkedIn profile pages, check if the person exists in the contacts table and show their record
- [ ] **14.6.9** Company dossier snippet: if a dossier exists in the backend, show a condensed version (industry, size, tech stack, culture notes) via `GET /api/search/companies?name={name}`
- [ ] **14.6.10** "Research this company" button that triggers `get_company_dossier` and opens results in the frontend

**Backend:** `GET /api/contacts`, `GET /api/search/contacts`, `GET /api/referrals`, `GET /api/search/companies`, `search_contacts` MCP tool, `network_check` MCP tool, `get_company_dossier` MCP tool
**Tables:** `contacts` (name, company_id, title, relationship_strength, last_contact), `referrals`, `companies`

---

## 7. Outreach Automation

Draft personalized outreach messages using the backend's voice rules and contact data.

- [ ] **14.7.1** From a contact card (section 6), "Draft Outreach" button opens a message composer in the popup
- [ ] **14.7.2** Message types: LinkedIn connection request, LinkedIn message, email
- [ ] **14.7.3** Backend generates draft using contact context + voice rules: `POST /api/outreach` with contact_id, channel, and context (job title, company, shared connections)
- [ ] **14.7.4** All generated outreach text passes through `check_voice` before presenting to user
- [ ] **14.7.5** User edits and approves the draft in the popup before any action is taken
- [ ] **14.7.6** For email drafts: copy to clipboard or open in Gmail compose (via mailto: link or Gmail MCP if connected)
- [ ] **14.7.7** For LinkedIn drafts: copy to clipboard with instructions to paste in LinkedIn messaging
- [ ] **14.7.8** Record the outreach event: `POST /api/outreach` saves message, channel, sent_at, contact_id, application_id
- [ ] **14.7.9** Follow-up reminders: if an outreach message was sent N days ago with no response, show a badge/notification in the popup
- [ ] **14.7.10** Schedule follow-ups: user sets a "follow up in X days" when sending, plugin shows reminder via `chrome.alarms`
- [ ] **14.7.11** View outreach history per contact in the popup: all messages sent/received, dates, channels

**Backend:** `POST /api/outreach`, `GET /api/outreach`, `check_voice` MCP tool, `get_voice_rules` MCP tool, `log_follow_up` MCP tool, `get_stale_applications` MCP tool
**Tables:** `outreach_messages` (contact_id, application_id, channel, direction, subject, body, sent_at, response_received), `contacts`

---

## 8. Response Tracking

Monitor and unify all networking touchpoints per company and contact.

- [ ] **14.8.1** Poll backend for email responses related to outreach: `GET /api/search/emails?contact={name}` on a schedule (every 2 hours, configurable)
- [ ] **14.8.2** When a response is detected, update the outreach record: `PATCH /api/outreach/{id}` with `response_received: true`
- [ ] **14.8.3** Auto-update the contact's `last_contact` date when a response is detected
- [ ] **14.8.4** Notification badge on the plugin icon when new responses are detected
- [ ] **14.8.5** Unified touchpoint timeline in the popup per contact: outreach sent, response received, follow-up sent, referral requested, interview scheduled
- [ ] **14.8.6** Unified touchpoint timeline per company: all contacts, all outreach, all applications, all interviews
- [ ] **14.8.7** "Stale outreach" indicator: highlight contacts where outreach was sent >7 days ago with no response
- [ ] **14.8.8** Quick actions from timeline: "Send follow-up", "Update status", "Add note"

**Backend:** `GET /api/search/emails`, `PATCH /api/outreach/{id}`, `GET /api/outreach`, `search_emails` MCP tool, `get_stale_applications` MCP tool
**Tables:** `outreach_messages`, `contacts`, `emails`

---

## 9. ATS Platform Support

Priority tiers for application form auto-fill support, informed by market share and usage frequency.

### Tier 1: Must-Have (launch blockers)

These platforms cover ~80% of enterprise job applications.

| # | Platform | URL Pattern | Notes |
|---|----------|-------------|-------|
| 1 | Workday | `*.myworkdayjobs.com` | Largest enterprise ATS. Multi-page flows. |
| 2 | Greenhouse | `boards.greenhouse.io`, `boards.eu.greenhouse.io`, `job-boards.greenhouse.io` | Popular with tech companies. Embedded forms common. |
| 3 | Lever | `jobs.lever.co` | Popular with startups and mid-market. |
| 4 | iCIMS | `*.icims.com/jobs` | Large enterprise footprint. |
| 5 | Taleo | `*.taleo.net` | Legacy Oracle ATS, still widely used. |
| 6 | LinkedIn EasyApply | `linkedin.com/jobs` | Inline application within LinkedIn. |
| 7 | Indeed SmartApply | `smartapply.indeed.com` | Indeed's inline application flow. |
| 8 | SuccessFactors | `*.successfactors.com` | SAP's ATS, large enterprise. |
| 9 | SmartRecruiters | `jobs.smartrecruiters.com` | Growing mid-market. |
| 10 | ADP | `recruiting.adp.com`, `workforcenow.adp.com` | HR/payroll giant's ATS. |

### Tier 2: Should-Have (post-launch priority)

| # | Platform | URL Pattern |
|---|----------|-------------|
| 11 | BambooHR | `*.bamboohr.com/jobs` |
| 12 | Jobvite | `jobs.jobvite.com` |
| 13 | AshbyHQ | `jobs.ashbyhq.com` |
| 14 | BreezyHR | `*.breezy.hr` |
| 15 | JazzHR | `*.applytojob.com` |
| 16 | Workable | `apply.workable.com` |
| 17 | Recruitee | `*.recruitee.com` |
| 18 | Rippling | `*.rippling-ats.com` |
| 19 | OracleCloud | `*.oraclecloud.com` |
| 20 | Paylocity | `*.paylocity.com/recruiting` |

### Tier 3: Nice-to-Have (opportunistic)

| # | Platform | URL Pattern |
|---|----------|-------------|
| 21 | Avature | `*.avature.net` |
| 22 | BrassRing | `*/TGnewUI/Search/home/Home` |
| 23 | Comeet | `*.comeet.com` |
| 24 | DayforceHCM | `jobs.dayforcehcm.com` |
| 25 | Eightfold | `*.eightfold.ai/careers` |
| 26 | FreshTeam | `*.freshteam.com` |
| 27 | Homerun | Embedded only |
| 28 | JobScore | `careers.jobscore.com` |
| 29 | PhenomPeople | Embedded only |
| 30 | PinpointHQ | `*.pinpointhq.com` |
| 31 | Polymer | `jobs.polymer.co` |
| 32 | Teamtailor | Embedded only |
| 33 | TriNetHire | `app.trinethire.com` |
| 34 | Ultipro | `*.ultipro.com/JobBoard` |
| 35 | TalNet | `*.tal.net` |

### Tier 4: Company-Specific (if needed)

| # | Platform | URL Pattern |
|---|----------|-------------|
| 36 | Amazon | `*.amazon.jobs` |
| 37 | Apple | `jobs.apple.com` |
| 38 | Google | `google.com/about/careers/applications/apply` |
| 39 | Meta | `facebookcareers.com` |
| 40 | Netflix | `explore.jobs.netflix.net` |
| 41 | Tesla | `*.tesla.com/careers` |
| 42 | Uber | `*.uber.com/careers/apply` |
| 43 | ByteDance | `jobs.bytedance.com` |
| 44 | IBM | `careers.ibm.com` |
| 45 | Roblox | `jobs.roblox.com` |
| 46 | Waymo | `waymo.com/joinus` |

### Job Board Detection (listing pages, not application forms)

| Board | URL Pattern |
|-------|-------------|
| Indeed | `*.indeed.com` job listing pages |
| LinkedIn | `*.linkedin.com/jobs/*` |
| Glassdoor | `*.glassdoor.com/job-listing/*` |
| Handshake | `*.joinhandshake.com/stu/jobs/*` |
| WelcomeToTheJungle | `app.welcometothejungle.com/dashboard/jobs*` |
| ZipRecruiter | `*.ziprecruiter.com/jobs/*` |
| Dice | `*.dice.com/job-detail/*` |
| BuiltIn | `*.builtin.com/job/*` |

---

## 10. Technical Architecture

### 10.1 Manifest V3

- [ ] **14.10.1** Manifest V3 with `manifest_version: 3`
- [ ] **14.10.2** Minimum Chrome version: 116 (stable MV3 service worker support)
- [ ] **14.10.3** Service worker as background script (not persistent background page)
- [ ] **14.10.4** No use of `chrome.scripting.executeScript` for content injection... use declarative content scripts in manifest

### 10.2 Content Script Injection Strategy

- [ ] **14.10.5** Content scripts injected ONLY on matched URL patterns... NOT `*://*/*` (unlike competitive approaches). Use specific matches for job boards and ATS platforms.
- [ ] **14.10.6** `siteConfig.json` bundled with the extension containing: URL patterns, DOM selectors for job extraction, form field mappings per ATS, confirmation page selectors
- [ ] **14.10.7** Content script runs at `document_idle` (after page load) to avoid interfering with page rendering
- [ ] **14.10.8** `all_frames: true` ONLY for ATS application URLs (for iframe-embedded forms), NOT for all URLs
- [ ] **14.10.9** `pageScript.js` injected into the page's JS context only on ATS application pages where form filling requires native DOM events
- [ ] **14.10.10** Shadow DOM for all injected UI elements (save buttons, overlays, contact cards) to prevent CSS conflicts with the host page

### 10.3 Background Service Worker

- [ ] **14.10.11** All API calls to localhost:8055 and localhost:8056 routed through the background service worker (not from content scripts directly) to respect CORS and keep API logic centralized
- [ ] **14.10.12** Connection health check on service worker startup: `GET /api/health` to verify backend is running
- [ ] **14.10.13** If backend is unreachable, show "Backend Offline" state in popup with instructions to start Docker
- [ ] **14.10.14** Retry logic: exponential backoff (1s, 2s, 4s, 8s, max 30s) for failed API calls
- [ ] **14.10.15** Alarm-based polling: badge count update (every 30 min), response tracking (every 2 hours), profile cache refresh (every 1 hour)

### 10.4 Message Passing

```
Content Script (job page)
    -- chrome.runtime.sendMessage({type: "SAVE_JOB", data: {...}}) -->
Background Service Worker
    -- fetch("http://localhost:8055/api/saved-jobs", {method: "POST", body: ...}) -->
Flask API
    -- response -->
Background Service Worker
    -- chrome.tabs.sendMessage(tabId, {type: "JOB_SAVED", data: {...}}) -->
Content Script (updates injected UI)
```

Message types:

| Type | Direction | Purpose |
|------|-----------|---------|
| `SAVE_JOB` | content -> background | Save job listing to backend |
| `JOB_SAVED` | background -> content | Confirm save, update injected button |
| `RUN_GAP_ANALYSIS` | content -> background | Trigger gap analysis for current JD |
| `GAP_RESULT` | background -> content | Return gap analysis result for overlay |
| `GENERATE_MATERIALS` | content -> background | Trigger resume + cover letter generation |
| `GENERATION_PROGRESS` | background -> content | Progress updates during generation |
| `GENERATION_COMPLETE` | background -> content | Files ready for download |
| `GET_PROFILE_DATA` | content -> background | Request candidate data for form fill |
| `PROFILE_DATA` | background -> content | Return profile data for autofill |
| `FILL_FORM` | content -> pageScript | Trigger form filling with profile data |
| `FORM_FILLED` | pageScript -> content | Report fill results |
| `CHECK_CONTACTS` | content -> background | Query contacts at a company |
| `CONTACTS_RESULT` | background -> content | Return contact cards for overlay |
| `HEALTH_CHECK` | popup -> background | Check backend connectivity |
| `HEALTH_STATUS` | background -> popup | Return health + pipeline summary |
| `GET_PIPELINE` | popup -> background | Request application pipeline data |
| `PIPELINE_DATA` | background -> popup | Return pipeline counts + recent apps |

### 10.5 Storage Strategy

| Store | Purpose | TTL |
|-------|---------|-----|
| `chrome.storage.local` | Profile data cache (resume header, career history, education, skills) | 1 hour |
| `chrome.storage.local` | Gap analysis cache (keyed by job URL) | 24 hours |
| `chrome.storage.local` | ATS fill state (for multi-page forms, keyed by domain + session) | 30 minutes |
| `chrome.storage.local` | User preferences (EEO opt-in, theme, notification settings) | Persistent |
| `chrome.storage.local` | Last known pipeline counts (for badge) | 30 minutes |
| Backend DB | All persistent data: jobs, applications, contacts, career data, generated materials | Permanent |

No use of `unlimitedStorage` permission. Profile data cache is small (<1 MB). If cache exceeds 5 MB, LRU eviction of gap analysis cache entries.

### 10.6 Permissions (Minimal)

```json
{
  "permissions": [
    "activeTab",
    "storage",
    "alarms",
    "tabs",
    "webNavigation"
  ],
  "host_permissions": [
    "http://localhost:8055/*",
    "http://localhost:8056/*"
  ]
}
```

**Not requested:**
- `cookies` — not needed, no auth tokens from other domains
- `webRequest` — not needed, no HTTP interception
- `unlimitedStorage` — not needed, cache is bounded
- `*://*/*` — not needed, content scripts target specific URL patterns only
- `offscreen` — not needed unless future features require it

Content script URL patterns are declared per job board / ATS in the manifest `content_scripts` section, NOT as a blanket `*://*/*`.

### 10.7 Build & Tooling

- [ ] **14.10.16** TypeScript for all extension code
- [ ] **14.10.17** Bundler: Vite or webpack with separate entry points for content script, background worker, popup, pageScript
- [ ] **14.10.18** React for popup UI (consistent with the main frontend)
- [ ] **14.10.19** Tailwind CSS for popup styling
- [ ] **14.10.20** Hot reload in dev mode for popup and content scripts
- [ ] **14.10.21** Source maps in dev, stripped in production builds
- [ ] **14.10.22** `siteConfig.json` as a separate importable module, not inlined into content script bundle

---

## 11. UI/UX Design

### 11.1 Popup

- [ ] **14.11.1** Dark theme: background `#1a1a2e`, surface `#16213e`, text `#e0e0e0`
- [ ] **14.11.2** Accent color: terminal green `#00FF41` for interactive elements, badges, progress bars, active states
- [ ] **14.11.3** Secondary accent: `#0a7e3a` for hover states and borders
- [ ] **14.11.4** Fixed width: 400px. Variable height with max 600px and internal scroll.
- [ ] **14.11.5** Header: SuperTroopers logo + connection status indicator (green dot = connected, red dot = offline)
- [ ] **14.11.6** Navigation tabs: Dashboard | Applications | Saved Jobs | Networking
- [ ] **14.11.7** Dashboard tab: mini funnel chart, recent activity feed, quick actions (search jobs, generate resume)
- [ ] **14.11.8** Applications tab: scrollable list with status chips, click to expand details
- [ ] **14.11.9** Saved Jobs tab: list with fit scores, "Generate Materials" and "Apply" quick actions
- [ ] **14.11.10** Networking tab: recent outreach, follow-up reminders, contact search
- [ ] **14.11.11** Footer: link to full frontend dashboard, settings gear icon
- [ ] **14.11.12** Monospace font for scores and stats (e.g., `JetBrains Mono` or `Fira Code`). Sans-serif for body text (`Inter`).

### 11.2 Injected Page Elements

- [ ] **14.11.13** Save button: pill-shaped, dark background with green border, SuperTroopers icon + "Save" text. Transforms to "Saved ✓" on click.
- [ ] **14.11.14** Match score badge: circular, 48px, color-coded, positioned near job title. Click to expand full analysis overlay.
- [ ] **14.11.15** Full analysis overlay: slide-in panel from right edge, 320px wide, dark theme, showing Strong/Partial/Gap lists
- [ ] **14.11.16** Contact cards: compact horizontal cards (avatar placeholder, name, title, last contact), stacked vertically
- [ ] **14.11.17** Generation progress modal: centered overlay, semi-transparent backdrop, step indicators with green checkmarks
- [ ] **14.11.18** Auto-fill indicator: thin green top-border on filled fields, summary toast at top of page
- [ ] **14.11.19** All injected elements use Shadow DOM to isolate styles from the host page
- [ ] **14.11.20** All injected elements include a small "ST" watermark so the user knows what's injected by SuperTroopers vs native

### 11.3 Accessibility

- [ ] **14.11.21** All interactive elements keyboard-navigable (Tab, Enter, Escape to close overlays)
- [ ] **14.11.22** ARIA labels on all injected buttons and overlays
- [ ] **14.11.23** Color is never the sole indicator... always paired with text or icons (scores show number + color)
- [ ] **14.11.24** Minimum contrast ratio 4.5:1 for all text (green on dark meets this)
- [ ] **14.11.25** Respect `prefers-reduced-motion` for animations
- [ ] **14.11.26** Screen reader announcements for async operations (job saved, generation complete)

---

## 12. Privacy & Security

### 12.1 Data Locality

- [ ] **14.12.1** All network requests go ONLY to `localhost:8055` and `localhost:8056`. No external endpoints. No exceptions.
- [ ] **14.12.2** No telemetry, no analytics, no error reporting to external services (no Sentry, no PostHog, no Axiom)
- [ ] **14.12.3** No data sent to any cloud service. The extension is fully offline-capable (minus the local backend).
- [ ] **14.12.4** Extension does not read cookies from any domain
- [ ] **14.12.5** Extension does not intercept or monitor HTTP traffic on other domains

### 12.2 Data Handling

- [ ] **14.12.6** JD text extracted from job pages is sent only to the local backend for gap analysis and generation... never stored in chrome.storage beyond the 24-hour gap analysis cache
- [ ] **14.12.7** EEO/demographic data (disability, veteran, gender, ethnicity) is NEVER auto-filled unless the user explicitly enables it in extension settings and has configured values
- [ ] **14.12.8** Passwords are never read, stored, or auto-filled. Skip any field with password-related labels.
- [ ] **14.12.9** Credit card and financial fields are never read or auto-filled
- [ ] **14.12.10** All `chrome.storage.local` data can be cleared from extension settings ("Clear Cache" button)

### 12.3 Permissions Justification

| Permission | Why Needed | What It Does NOT Do |
|------------|-----------|---------------------|
| `activeTab` | Read page content on the active tab when user clicks the extension or interacts with injected buttons | Does not grant persistent access to all tabs |
| `storage` | Cache profile data and gap analyses locally | Does not access other extensions' storage |
| `alarms` | Schedule badge updates and follow-up reminders | Does not run code when browser is closed |
| `tabs` | Send messages to content scripts in specific tabs | Does not read tab URLs without activeTab |
| `webNavigation` | Detect SPA navigation (URL changes without page reload) on job boards | Does not intercept or modify navigation |
| `localhost:8055/*` | API calls to the local SuperTroopers backend | Does not access any other host |
| `localhost:8056/*` | MCP SSE connection to the local SuperTroopers server | Does not access any other host |

### 12.4 User Controls

- [ ] **14.12.11** Settings page in popup with toggles for each feature: job detection, auto-analysis, form filling, contact overlay, outreach, response tracking
- [ ] **14.12.12** EEO data sharing: explicit opt-in toggle, defaults to OFF
- [ ] **14.12.13** "Pause Extension" toggle: disables all content script injection and background polling without uninstalling
- [ ] **14.12.14** "Clear All Data" button: wipes chrome.storage.local completely
- [ ] **14.12.15** Per-site disable: right-click context menu "Disable SuperTroopers on this site"

---

## 13. Phased Delivery

### Phase 0: Foundation

**Goal:** Working Chrome extension scaffold that connects to the local backend and shows basic status.
**Independently valuable:** User can confirm backend connectivity and see pipeline summary without opening the frontend.

- [x] **14.13.1** Chrome extension project scaffold: Manifest V3, TypeScript, Vite/webpack, React popup
- [x] **14.13.2** Background service worker with health check: `GET /api/health` on startup and on alarm (every 5 minutes)
- [x] **14.13.3** Popup UI shell: dark theme, connection status indicator, navigation tabs (Dashboard placeholder)
- [x] **14.13.4** Dashboard tab: pipeline summary from `GET /api/analytics/summary` (counts by status)
- [x] **14.13.5** Extension icon with badge showing total active applications count
- [x] **14.13.6** "Backend Offline" state with Docker start instructions
- [x] **14.13.7** Settings page: backend URL configuration (default `localhost:8055`), feature toggles (all off initially)
- [x] **14.13.8** Message passing infrastructure: content script <-> background <-> popup communication layer
- [x] **14.13.9** `siteConfig.json` scaffold with URL patterns for top 5 job boards (Indeed, LinkedIn, Glassdoor, ZipRecruiter, Dice)
- [x] **14.13.10** Content script loader: injects on matched URLs, sends page context to background, receives responses
- [x] **14.13.11** Dev tooling: hot reload, source maps, `chrome://extensions` load unpacked workflow documented

**Deliverable:** Installable .crx / unpacked extension. Opens popup, shows green/red connection dot, displays pipeline counts.

### Phase 1: Job Capture + Match

**Goal:** Save jobs from any major job board and see instant fit analysis.
**Independently valuable:** User can browse job boards naturally and save interesting jobs + see match scores without switching to the SuperTroopers frontend.

- [ ] **14.13.12** Job listing detection on Indeed, LinkedIn, Glassdoor (URL pattern + DOM selectors in siteConfig)
- [ ] **14.13.13** "Save to SuperTroopers" button injection on detected job pages
- [ ] **14.13.14** Job data extraction: title, company, location, salary, JD text, URL
- [ ] **14.13.15** Save to backend: `POST /api/saved-jobs`
- [ ] **14.13.16** Duplicate detection: check URL before saving, show "Already Saved" state
- [ ] **14.13.17** Gap analysis trigger: auto-send JD text to `POST /api/gap-analysis` after detection
- [ ] **14.13.18** Match score overlay: circular badge on the page with fit percentage
- [ ] **14.13.19** Expanded analysis panel: strong matches, partial matches, gaps
- [ ] **14.13.20** Gap analysis caching in chrome.storage.local (24h TTL)
- [ ] **14.13.21** Saved Jobs tab in popup: list of saved jobs with scores
- [ ] **14.13.22** Handle SPA navigation on LinkedIn and Glassdoor (webNavigation listener)
- [ ] **14.13.23** Add job board detection for ZipRecruiter, Dice, BuiltIn, Handshake

**Deliverable:** Browse Indeed/LinkedIn/Glassdoor, see green save buttons and match scores on every listing. Click to save. View saved jobs in popup.

### Phase 2: AI Materials + Auto-Apply

**Goal:** Generate tailored resume and cover letter from any job page, and auto-fill ATS application forms.
**Independently valuable:** User can generate and download application materials without leaving the job board, and auto-fill applications instead of manually typing everything.

- [ ] **14.13.24** "Generate Materials" button on job listing pages
- [ ] **14.13.25** Generation pipeline: content script sends JD -> background calls gap analysis -> recipe selection -> generate_resume -> check_voice -> return files
- [ ] **14.13.26** Progress overlay with step indicators
- [ ] **14.13.27** Download buttons for generated .docx resume and cover letter
- [ ] **14.13.28** Preview panel showing generated resume content inline
- [ ] **14.13.29** ATS form detection for Tier 1 platforms: Workday, Greenhouse, Lever, iCIMS, Taleo
- [ ] **14.13.30** Profile data fetch and cache from backend
- [ ] **14.13.31** Standard field auto-fill: name, email, phone, location
- [ ] **14.13.32** Work history and education field auto-fill
- [ ] **14.13.33** File upload handling: attach generated resume to upload fields
- [ ] **14.13.34** `pageScript.js` for native DOM event firing on React/Angular ATS forms
- [ ] **14.13.35** Fill summary overlay: "Filled X of Y fields"
- [ ] **14.13.36** Green border highlighting on filled fields
- [ ] **14.13.37** Add ATS support: LinkedIn EasyApply, Indeed SmartApply, SuccessFactors, SmartRecruiters, ADP

**Deliverable:** Generate tailored resume from any job page. Auto-fill Workday, Greenhouse, Lever, iCIMS, Taleo forms. Download materials.

### Phase 3: Application Tracking

**Goal:** Automatically track all applications and surface pipeline status in the plugin.
**Independently valuable:** User has a real-time view of their application pipeline without switching to the frontend.

- [ ] **14.13.38** Submission detection: recognize "thank you" / confirmation pages on ATS platforms
- [ ] **14.13.39** Auto-create application record on confirmed submission: `POST /api/applications`
- [ ] **14.13.40** Link generated materials and gap analysis to the application record
- [ ] **14.13.41** Badge count update: poll `GET /api/analytics/summary` every 30 minutes
- [ ] **14.13.42** Applications tab in popup: scrollable list with status chips
- [ ] **14.13.43** Click-to-expand application details in popup
- [ ] **14.13.44** Manual status update from popup: dropdown to change status
- [ ] **14.13.45** Mini funnel visualization in Dashboard tab
- [ ] **14.13.46** "Applied via plugin" source tracking
- [ ] **14.13.47** Link to frontend dashboard from popup
- [ ] **14.13.48** Multi-page ATS flow support: maintain fill state across pages
- [ ] **14.13.49** Add Tier 2 ATS support: BambooHR, Jobvite, AshbyHQ, BreezyHR, JazzHR, Workable, Recruitee, Rippling, OracleCloud, Paylocity

**Deliverable:** Applications automatically tracked after submission. Badge shows counts. Popup shows full pipeline. Tier 2 ATS platforms supported.

### Phase 4: Networking + Outreach

**Goal:** Surface network connections on job pages and automate personalized outreach.
**Independently valuable:** User sees their network context while browsing jobs and can draft/track outreach without context-switching.

- [ ] **14.13.50** Contact lookup on job listing pages: query backend by company name
- [ ] **14.13.51** Contact card injection on job and company pages
- [ ] **14.13.52** Company dossier snippet overlay
- [ ] **14.13.53** LinkedIn page detection: company pages and profile pages
- [ ] **14.13.54** Contact record matching on LinkedIn profiles
- [ ] **14.13.55** Networking tab in popup: recent outreach, follow-up reminders
- [ ] **14.13.56** Outreach composer in popup: LinkedIn message, email drafts
- [ ] **14.13.57** Voice-checked outreach generation via backend
- [ ] **14.13.58** Outreach recording: save to `outreach_messages` table
- [ ] **14.13.59** Follow-up scheduling via `chrome.alarms`
- [ ] **14.13.60** Follow-up reminder notifications in popup
- [ ] **14.13.61** Response tracking: poll backend for email responses
- [ ] **14.13.62** Touchpoint timeline per contact in popup
- [ ] **14.13.63** Touchpoint timeline per company in popup
- [ ] **14.13.64** Stale outreach indicators
- [ ] **14.13.65** Add Tier 3 + Tier 4 ATS support as time permits

**Deliverable:** Full networking overlay on job pages. Outreach drafting and tracking. Response monitoring. Complete ATS coverage.

---

## Appendix A: New Backend Endpoints Needed

The following endpoints do not currently exist and will need to be added to support the browser plugin:

| Endpoint | Method | Purpose | Phase |
|----------|--------|---------|-------|
| `/api/plugin/health` | GET | Plugin-specific health check returning backend version, feature flags, ATS config version | 0 |
| `/api/plugin/profile-bundle` | GET | Single endpoint returning resume_header + career_history + education + certifications + skills in one payload (reduces round trips for form fill) | 2 |
| `/api/plugin/generate-materials` | POST | Accepts JD text + job metadata, runs full pipeline (gap analysis -> recipe -> generate -> voice check), returns file URLs + match score. Orchestration endpoint. | 2 |
| `/api/plugin/ats-config` | GET | Returns current siteConfig version hash. Plugin checks on startup to see if bundled config needs update. | 2 |
| `/api/saved-jobs/check-url` | GET | Check if a URL already exists in saved_jobs. Returns boolean + job_id if exists. | 1 |

## Appendix B: siteConfig.json Structure

```json
{
  "version": "1.0.0",
  "boards": {
    "indeed": {
      "urlPatterns": ["*://*.indeed.com/viewjob*", "*://*.indeed.com/m/basecamp/viewjob*"],
      "extractors": {
        "title": { "selector": "h1.jobsearch-JobInfoHeader-title", "attribute": "textContent" },
        "company": { "selector": "[data-company-name]", "attribute": "textContent" },
        "location": { "selector": "[data-testid='job-location']", "attribute": "textContent" },
        "salary": { "selector": "#salaryInfoAndJobType", "attribute": "textContent" },
        "description": { "selector": "#jobDescriptionText", "attribute": "innerHTML" }
      }
    }
  },
  "ats": {
    "workday": {
      "urlPatterns": ["*://*.myworkdayjobs.com/*/job/*"],
      "formSelectors": {
        "firstName": { "xpath": "//input[@data-automation-id='legalNameSection_firstName']" },
        "lastName": { "xpath": "//input[@data-automation-id='legalNameSection_lastName']" },
        "email": { "xpath": "//input[@data-automation-id='email']" }
      },
      "submitButton": { "xpath": "//button[@data-automation-id='bottom-navigation-next-button']" },
      "confirmationPage": { "xpath": "//div[contains(@class, 'thankYouMessage')]" },
      "multiPage": true,
      "iframeEmbed": false
    }
  },
  "fieldCategories": {
    "personal": ["firstName", "lastName", "fullName", "email", "phone", "address", "city", "state", "zip", "country"],
    "work": ["employer", "title", "startDate", "endDate", "description", "currentlyWorking"],
    "education": ["school", "degree", "major", "graduationDate"],
    "documents": ["resume", "coverLetter"],
    "links": ["linkedin", "github", "portfolio", "website"],
    "authorization": ["workAuth", "sponsorship", "over18"],
    "eeo": ["disability", "veteran", "gender", "ethnicity"]
  },
  "excludedFields": ["password", "choosePassword", "retypePassword", "creditCard", "ssn"],
  "excludedUrls": ["*://accounts.google.com/*", "*://*.recaptcha.net/*", "*://www.youtube.com/*"]
}
```

## Appendix C: Extension File Structure

```
supertroopers-extension/
├── manifest.json
├── package.json
├── tsconfig.json
├── vite.config.ts
├── src/
│   ├── background/
│   │   ├── index.ts              # Service worker entry
│   │   ├── api.ts                # Backend API client (localhost:8055)
│   │   ├── messages.ts           # Message handler routing
│   │   ├── alarms.ts             # Scheduled tasks
│   │   └── cache.ts              # Chrome storage cache manager
│   ├── content/
│   │   ├── index.ts              # Content script entry
│   │   ├── detector.ts           # Job board / ATS page detection
│   │   ├── extractor.ts          # Job data extraction from DOM
│   │   ├── injector.ts           # UI injection (save button, overlays, cards)
│   │   ├── filler.ts             # Form field filling logic
│   │   └── shadow.ts             # Shadow DOM component factory
│   ├── pageScript/
│   │   └── index.ts              # Page-context script for native DOM events
│   ├── popup/
│   │   ├── index.tsx             # React popup entry
│   │   ├── App.tsx               # Main popup app
│   │   ├── components/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Applications.tsx
│   │   │   ├── SavedJobs.tsx
│   │   │   ├── Networking.tsx
│   │   │   ├── Settings.tsx
│   │   │   ├── PipelineFunnel.tsx
│   │   │   ├── MatchScore.tsx
│   │   │   └── OutreachComposer.tsx
│   │   └── hooks/
│   │       ├── useBackend.ts     # API communication hook
│   │       └── usePipeline.ts    # Pipeline data hook
│   ├── shared/
│   │   ├── types.ts              # Shared TypeScript types
│   │   ├── messages.ts           # Message type constants
│   │   └── config.ts             # Default config values
│   └── config/
│       └── siteConfig.json       # ATS + job board configuration
├── assets/
│   ├── icons/                    # Extension icons (16, 32, 48, 128px)
│   └── logo.svg
├── css/
│   └── content.css               # Styles for injected elements
└── dist/                         # Build output (unpacked extension)
```
