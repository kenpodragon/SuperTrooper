# LinkedIn Content Sync — Extension Passive Capture + Headless Scraping

> Component doc for automated LinkedIn content archival. Parent: `0_APPLICATION_REQUIREMENTS.md` Section 18.
> Related: `14_BROWSER_PLUGIN.md` (extension), `15_INTEGRATIONS.md` (scheduler)

---

## Overview

Two complementary strategies keep LinkedIn content archived and up-to-date without manual scraper runs:

1. **Extension Passive Capture** — the Chrome extension silently captures LinkedIn content as the user browses normally
2. **Headless Scheduled Scraping** — the backend runs the existing scraper code on a schedule using cookies captured by the extension

Both feed into the same DB tables (`scraped_posts`, `scraped_comments`, `scraped_messages`, `scraped_media`) and the same import endpoints (`/api/import/linkedin-*`).

---

## Part A: Extension Passive Capture

### A.1 Content Scripts on linkedin.com

New content scripts (separate from the job-board content script) that activate on LinkedIn pages:

| URL Pattern | What to Capture | DB Target |
|-------------|----------------|-----------|
| `*://*.linkedin.com/in/*/recent-activity/*` | Posts from activity feed (text, URN, timestamp, engagement counts) | `scraped_posts` |
| `*://*.linkedin.com/in/*/recent-activity/*` | Comments from activity feed (text, URN, parent post URN) | `scraped_comments` |
| `*://*.linkedin.com/messaging/*` | Conversations list + message bodies | `scraped_messages` |
| `*://*.linkedin.com/sales/ssi*` | SSI score, component scores, date | `linkedin_ssi_scores` (new table) |
| `*://*.linkedin.com/feed/*` | Own posts that appear in main feed | `scraped_posts` |

**Content script behavior:**
- Runs at `document_idle` on matching URLs
- Uses MutationObserver to detect dynamically loaded content (LinkedIn is SPA)
- Extracts structured data from DOM (post text, URNs from `data-urn` attributes, timestamps)
- Batches captured items (flush every 10 items or 30 seconds, whichever comes first)
- Sends batches to background service worker via `chrome.runtime.sendMessage`
- Background worker forwards to backend API

**Manifest changes needed:**
```json
{
  "content_scripts": [
    {
      "matches": ["*://*.linkedin.com/*"],
      "js": ["linkedin_capture.js"],
      "run_at": "document_idle",
      "exclude_matches": [
        "*://*.linkedin.com/jobs/*",
        "*://*.linkedin.com/in/*/overlay/*"
      ]
    }
  ]
}
```

New permission needed: `"*://*.linkedin.com/*"` in `host_permissions`.

### A.2 Session/Cookie Capture

The extension captures LinkedIn session cookies for headless scraper use:

**What to capture:**
- `li_at` cookie (primary auth token)
- `JSESSIONID` cookie (CSRF token)
- `li_mc` cookie (member cookie)

**How:**
- Extension uses `chrome.cookies.get()` API (requires `cookies` permission)
- Triggered on: (a) first linkedin.com page load after extension install, (b) periodic refresh every 4 hours via alarm, (c) manual "Refresh Session" button in Settings
- Validates cookie by making a lightweight API call (e.g., `/voyager/api/me`) to confirm session is active
- Sends validated cookies to backend: `POST /api/linkedin/session`

**Security:**
- Backend encrypts cookie blob with Fernet (symmetric key from env var `LINKEDIN_COOKIE_KEY`)
- Stored in `linkedin_sessions` table (see Part C)
- Never logged, never returned in API responses (write-only from extension perspective)
- Auto-deleted after 30 days or on explicit logout

### A.3 Backend Sync Endpoints

New endpoints in `routes/linkedin_import.py`:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/import/linkedin-posts-live` | Receive passively captured posts from extension |
| POST | `/api/import/linkedin-comments-live` | Receive passively captured comments |
| POST | `/api/import/linkedin-messages-live` | Receive passively captured messages |
| POST | `/api/import/linkedin-ssi` | Receive SSI score snapshot |
| POST | `/api/linkedin/session` | Store encrypted session cookies |
| GET | `/api/linkedin/session/status` | Check session validity (expired/active/missing) |
| DELETE | `/api/linkedin/session` | Revoke stored session |

All `-live` endpoints accept the same schema as the existing bulk import endpoints but with smaller batches. They perform the same dedup logic (URN check).

### A.4 Incremental Detection

Before sending data to the backend, the extension checks what is already captured:

**Option A (preferred): Backend dedup** — Extension sends everything, backend skips existing URNs. Simpler extension code, slightly more network traffic.

**Option B: Extension-side dedup** — Extension caches known URNs in `chrome.storage.local` (synced from backend on startup). Reduces API calls but adds complexity.

Recommendation: Start with Option A. The backend already has URN uniqueness constraints. Move to Option B only if network overhead becomes noticeable.

---

## Part B: Headless Scheduled Scraping

### B.1 Cookie-Based Authentication

The scraper modules (`code/utils/linkedin_scraper/`) already use Playwright with a Chrome user data directory for auth. For headless mode, we inject cookies instead:

**Flow:**
1. Backend reads encrypted cookies from `linkedin_sessions` table
2. Decrypts with Fernet key
3. Creates a new Playwright browser context (headless)
4. Injects cookies via `context.add_cookies([...])`
5. Navigates to LinkedIn... session is authenticated
6. Runs scraper modules as normal

**Code change:** Add a `--headless` and `--cookies-from-db` flag to the scraper CLI. When set:
- Skip Chrome launch/CDP connection
- Create headless Chromium context
- Load cookies from DB (via direct psql or backend API call)
- Run modules against this context

### B.2 Playwright Headless Mode

Configuration for headless scraping:

```python
browser = await p.chromium.launch(
    headless=True,
    args=[
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ]
)
context = await browser.new_context(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
    viewport={"width": 1920, "height": 1080},
    locale="en-US",
)
# Inject cookies
await context.add_cookies(decrypted_cookies)
```

Anti-detection measures:
- Realistic user agent string
- Standard viewport size
- Random delays between actions (already in scraper base)
- navigator.webdriver property patched via `init_script`
- Rate limiting: max 1 scrape job per 6 hours

### B.3 Scheduler Integration

Add scraping jobs to the existing `SimpleScheduler` in `code/backend/scheduler.py`:

```python
scheduler.add_job(
    name="linkedin_content_sync",
    func=run_linkedin_scraper,  # async wrapper
    interval_minutes=360,       # every 6 hours
    enabled=False,              # user must opt-in via Settings
)

scheduler.add_job(
    name="linkedin_cookie_check",
    func=check_cookie_validity,
    interval_minutes=240,       # every 4 hours
    enabled=True,
)
```

The `run_linkedin_scraper` function:
1. Checks if valid session exists in `linkedin_sessions`
2. If expired, creates a notification asking user to re-login
3. If valid, runs the scraper in headless mode with DB cookies
4. Captures output, logs results to `scraper_runs` table (new)
5. Updates `linkedin_sessions.last_used_at`

### B.4 Cookie Refresh Flow

Cookies expire. The system handles this gracefully:

**Extension side:**
- Alarm fires every 4 hours
- Extension calls `chrome.cookies.get()` for `li_at` on `.linkedin.com`
- If cookie exists and hasn't changed, no action
- If cookie changed, POST new cookie to backend
- If cookie missing (user logged out), POST status update to backend

**Backend side:**
- `linkedin_cookie_check` job validates stored cookies every 4 hours
- Validation: make a lightweight request to LinkedIn API with stored cookies
- If 401/403: mark session as expired, create notification
- If 200: update `last_validated_at`

**User notification:**
- When cookies expire: badge notification in extension + backend notification
- Notification text: "LinkedIn session expired. Visit linkedin.com to refresh."
- Clicking notification opens linkedin.com in a new tab (extension re-captures cookies on page load)

### B.5 Graceful Degradation

| Scenario | Behavior |
|----------|----------|
| Cookies expired | Skip scheduled scrape, notify user, retry after next cookie refresh |
| LinkedIn rate-limits (429) | Back off exponentially (1h, 2h, 4h), notify user if 3 consecutive failures |
| Scraper crash | Log error, retry once after 5 min, then skip until next scheduled run |
| Extension not installed | No cookies available, headless scraping disabled, manual scraper still works |
| LinkedIn DOM changes | Scraper module throws parse errors, logged to `scraper_runs`, user notified to update |

---

## Part C: Architecture

### C.1 New DB Tables

#### `linkedin_sessions`
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| cookie_blob | bytea | Fernet-encrypted JSON of all LinkedIn cookies |
| captured_at | timestamptz | When extension sent the cookies |
| expires_at | timestamptz | Earliest expiry of captured cookies |
| last_validated_at | timestamptz | Last successful validation |
| last_used_at | timestamptz | Last time headless scraper used these cookies |
| status | text | `active`, `expired`, `revoked` |
| user_agent | text | UA string used during capture (for headless matching) |

#### `linkedin_ssi_scores`
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| score | integer | Overall SSI score (0-100) |
| establish_brand | integer | Component 1 |
| find_right_people | integer | Component 2 |
| engage_insights | integer | Component 3 |
| build_relationships | integer | Component 4 |
| industry_rank | text | e.g., "Top 5%" |
| network_rank | text | e.g., "Top 10%" |
| captured_at | timestamptz | |

#### `scraper_runs`
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| run_type | text | `manual`, `scheduled`, `extension_passive` |
| modules_run | text[] | e.g., `{posts, comments}` |
| started_at | timestamptz | |
| finished_at | timestamptz | |
| status | text | `success`, `partial`, `failed` |
| items_captured | jsonb | e.g., `{"posts": 12, "comments": 45}` |
| errors | text[] | Error messages if any |
| cookie_session_id | integer FK | Which linkedin_session was used (null for manual) |

### C.2 Data Pipeline

```
Extension Content Script
    |
    v (chrome.runtime.sendMessage)
Background Service Worker
    |
    v (POST /api/import/linkedin-*-live)
Backend API (linkedin_import.py)
    |
    v (INSERT with URN dedup)
PostgreSQL (scraped_posts, scraped_comments, scraped_messages)
    |
    v (existing embedding pipeline)
pgvector embeddings (for semantic search)
```

```
Scheduler (every 6h)
    |
    v (check linkedin_sessions)
Scraper Job (headless Playwright)
    |
    v (same scraper modules)
JSONL output -> Backend import endpoints -> DB
```

### C.3 Extension Changes Summary

**New files:**
- `src/content/linkedinCapture.ts` — content script for LinkedIn passive capture
- `src/background/linkedinSync.ts` — background worker for cookie capture + batch forwarding
- `src/popup/components/LinkedInSync.tsx` — settings UI for sync status

**Modified files:**
- `manifest.json` — add LinkedIn content script entry, add `cookies` permission, add `*://*.linkedin.com/*` to host_permissions
- `src/popup/components/Settings.tsx` — add LinkedIn sync toggle, session status display
- `src/background/index.ts` — register LinkedIn sync message handlers
- `src/shared/types.ts` — add LinkedIn capture message types

### C.4 Frontend UI (Settings Page)

The extension Settings panel gets a new "LinkedIn Sync" section:

- **Session Status**: Green dot = active, yellow = expiring soon (<24h), red = expired
- **Last Sync**: timestamp of last successful data capture (passive or scheduled)
- **Passive Capture**: toggle on/off (default: off, user must opt-in)
- **Scheduled Scraping**: toggle on/off (default: off)
- **Scrape Frequency**: dropdown (every 6h, 12h, 24h)
- **Cookie Status**: "Valid until {date}" or "Expired — click to refresh"
- **Manual Refresh**: button to trigger immediate cookie re-capture
- **Sync History**: collapsible list of recent `scraper_runs` with item counts

---

## Migration Plan

### Phase 1: Cookie Infrastructure
1. Create `linkedin_sessions` table migration
2. Add `POST/GET/DELETE /api/linkedin/session` endpoints
3. Add cookie capture to extension (new permission, background worker)
4. Add cookie validation job to scheduler

### Phase 2: Passive Capture
1. Build `linkedinCapture.ts` content script
2. Add `-live` import endpoints
3. Wire extension background worker to batch and forward
4. Add `scraped_runs` table + logging

### Phase 3: Headless Scraping
1. Copy scraper to `code/utils/linkedin_scraper/` (Task 12 — done)
2. Add `--headless --cookies-from-db` mode to CLI
3. Add `linkedin_content_sync` job to scheduler
4. Build Settings UI for sync controls

### Phase 4: SSI Tracking
1. Create `linkedin_ssi_scores` table
2. Add SSI capture to content script
3. Add `/api/import/linkedin-ssi` endpoint
4. Add SSI trend chart to LinkedIn Hub frontend

---

## Security Considerations

- LinkedIn cookies are sensitive credentials... treat them like passwords
- Fernet encryption at rest, key in env var (not in code or DB)
- No cookie data in logs, API responses, or error messages
- Auto-expire stored sessions after 30 days
- User must explicitly opt-in to both passive capture and scheduled scraping
- Rate limiting on all scraping (manual or scheduled) to avoid LinkedIn account restrictions
- Extension uses minimal permissions (only `cookies` for `.linkedin.com`, not broad cookie access)

---

## Dependencies

| Component | Path | Status |
|-----------|------|--------|
| Scraper modules | `code/utils/linkedin_scraper/` | Copied from local_code (Task 12) |
| Scraper base (progress, logging) | `code/utils/linkedin_scraper/base.py` | Copied |
| Backend scheduler | `code/backend/scheduler.py` | Exists, needs new jobs |
| Extension | `code/extension/` | Exists, needs new content script + permissions |
| Import endpoints | `code/backend/routes/linkedin_import.py` | Exists, needs `-live` variants |
| LinkedIn Hub routes | `code/backend/routes/linkedin.py` | Exists, needs session endpoints |
| Fernet (cryptography lib) | `requirements.txt` | Needs adding |

---

## Verification

1. **Cookie capture**: Install extension, visit linkedin.com, verify `linkedin_sessions` row created with `active` status
2. **Passive capture**: Visit own activity page, verify new posts appear in `scraped_posts` within 30 seconds
3. **Dedup**: Visit same page again, verify no duplicate rows
4. **Headless scraping**: Run CLI with `--headless --cookies-from-db`, verify items captured
5. **Cookie expiry**: Manually expire cookie in DB, verify notification created and scraper skips gracefully
6. **Scheduler**: Enable scheduled scraping in Settings, wait for next run, verify `scraper_runs` entry
7. **SSI**: Visit linkedin.com/sales/ssi, verify score captured in `linkedin_ssi_scores`
