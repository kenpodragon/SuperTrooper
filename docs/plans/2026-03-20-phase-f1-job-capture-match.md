# Phase F1: Job Capture + Match Scoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a user visits a job listing on any supported job board, inject a "Save to SuperTroopers" button and a match score overlay. Saved jobs appear in the popup's Jobs tab with fit scores. Gap analysis results are cached locally and persisted to the backend when linked to a saved job.

**Spec:** `code/docs/reqs/14_BROWSER_PLUGIN.md` — Section 1 (14.1.1–14.1.10) + Section 2 (14.2.1–14.2.10)

**Depends on (all complete from F0):**
- Content script detection + extraction (`detector.ts`, `siteConfig.json`)
- Shadow DOM injection factory (`shadow.ts`)
- Background API client (`api.ts`) + message router (`messages.ts`)
- Message types: `SAVE_JOB`, `RUN_GAP_ANALYSIS`, `CHECK_JOB_URL`, `PAGE_CONTEXT` (defined, handlers stubbed)
- Popup shell with 4 tabs (Jobs tab is placeholder)

---

## CRITICAL: Architecture Decisions

### Data Flow — Save Job
```
Content Script                    Background Worker              Backend
─────────────                    ─────────────────              ───────
User clicks Save button
  → extractJobData()
  → sendMessage(SAVE_JOB, data) ──→ POST /api/saved-jobs ────→ INSERT saved_jobs
                                 ←── {id, status} ←──────────── response
  ← update button "Saved ✓"
```

### Data Flow — Gap Analysis
```
Content Script                    Background Worker              Backend
─────────────                    ─────────────────              ───────
Job listing detected
  → extractJobData()
  → sendMessage(RUN_GAP_ANALYSIS) ─→ check cache (chrome.storage.local)
                                     if cached & fresh → return cached
                                     else → POST /api/gap-analysis ──→ match_jd
                                          ←── {fit_score, strong, partial, gaps}
                                     → cache result (24h TTL)
  ← inject score badge + panel    ←── gap analysis result
```

### Caching Strategy
- **Key:** URL of the job listing (normalized — strip tracking params)
- **Storage:** `chrome.storage.local` (10MB limit, plenty for gap results)
- **TTL:** 24 hours
- **Invalidation:** "Refresh" button on overlay, or manual clear from popup
- **Persist:** When a job is saved AND has a cached gap analysis, also POST to `/api/gap-analyses` and link to `saved_job_id`

### Injection Rules
- Save button: inject near the job title or apply button (board-specific positioning from siteConfig)
- Score badge: floating circular overlay, bottom-right of viewport (doesn't obstruct apply button)
- Analysis panel: expandable from the badge, dark theme matching extension

### Duplicate Detection
- Before showing "Save" button, send `CHECK_JOB_URL` to background
- Background does `GET /api/saved-jobs?url={encoded_url}`
- If exists → button shows "Already Saved" (green checkmark, disabled)

---

## File Changes Summary

### New Files
```
code/extension/src/content/
├── saveButton.ts              # Save button injection + click handler
├── scoreOverlay.ts            # Match score badge + expandable panel
└── jobCapture.ts              # Orchestrator: detect → check dupe → inject button + score

code/extension/src/popup/components/
└── SavedJobs.tsx              # Jobs tab: saved jobs list with scores + actions

code/extension/src/background/
└── gapCache.ts                # Gap analysis cache (chrome.storage.local, 24h TTL)
```

### Modified Files
```
code/extension/src/content/index.ts        # Wire up jobCapture on detection
code/extension/src/background/messages.ts  # Implement SAVE_JOB, RUN_GAP_ANALYSIS, CHECK_JOB_URL handlers
code/extension/src/background/api.ts       # Add saveJob, checkJobUrl, runGapAnalysis API methods
code/extension/src/shared/types.ts         # Add SavedJob, GapAnalysis, ScoreOverlay types
code/extension/src/shared/messages.ts      # Add message payload types for new handlers
code/extension/src/popup/App.tsx           # Wire SavedJobs component into Jobs tab
code/extension/src/config/siteConfig.json  # Add injection anchor selectors + ZipRecruiter/Dice/BuiltIn/Handshake
code/extension/src/content/shadow.ts       # Add score badge + panel component templates
```

### Backend (minor)
```
code/backend/routes/saved_jobs.py          # Add GET /api/saved-jobs?url= for duplicate check
```

---

## Task 1: TypeScript Types + Message Payloads

**Files:** Modify `src/shared/types.ts`, `src/shared/messages.ts`

- [ ] **Step 1: Add SavedJob type to types.ts**

```typescript
export interface SavedJob {
  id: number;
  url: string;
  title: string;
  company: string;
  location: string | null;
  salary_range: string | null;
  jd_text: string | null;
  source: string;        // "indeed" | "linkedin" | "glassdoor" | "ziprecruiter" | "dice" | "builtin" | "handshake"
  fit_score: number | null;
  status: string;        // "saved" | "applied" | "interviewing" | "offered" | "rejected" | "withdrawn"
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface GapAnalysisResult {
  fit_score: number;
  strong_matches: string[];
  partial_matches: string[];
  gaps: string[];
  recommendations: string[];
  cached_at?: number;     // timestamp for TTL
  job_url: string;
}

export interface JobExtraction {
  title: string;
  company: string;
  location: string | null;
  salary: string | null;
  description: string;
  url: string;
  source: string;
}
```

- [ ] **Step 2: Add message payload types to messages.ts**

```typescript
// Add to MessageType enum (or const object)
export const MSG = {
  // ... existing
  SAVE_JOB: 'SAVE_JOB',
  CHECK_JOB_URL: 'CHECK_JOB_URL',
  RUN_GAP_ANALYSIS: 'RUN_GAP_ANALYSIS',
  GET_SAVED_JOBS: 'GET_SAVED_JOBS',
  REFRESH_GAP_ANALYSIS: 'REFRESH_GAP_ANALYSIS',
} as const;

// Payload types
export interface SaveJobPayload {
  job: JobExtraction;
}

export interface SaveJobResponse {
  saved_job: SavedJob;
  already_existed: boolean;
}

export interface CheckJobUrlPayload {
  url: string;
}

export interface CheckJobUrlResponse {
  exists: boolean;
  saved_job?: SavedJob;
}

export interface GapAnalysisPayload {
  jd_text: string;
  job_url: string;
  force_refresh?: boolean;
  saved_job_id?: number;
}

export interface GapAnalysisResponse {
  result: GapAnalysisResult;
  from_cache: boolean;
}

export interface GetSavedJobsResponse {
  jobs: SavedJob[];
}
```

---

## Task 2: Gap Analysis Cache

**Files:** Create `src/background/gapCache.ts`

- [ ] **Step 1: Implement cache with 24h TTL**

```typescript
const CACHE_PREFIX = 'gap_';
const TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

function normalizeUrl(url: string): string {
  // Strip tracking params (utm_*, fbclid, etc.)
  const u = new URL(url);
  const strip = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'fbclid', 'gclid'];
  strip.forEach(p => u.searchParams.delete(p));
  return u.toString();
}

export async function getCachedGap(url: string): Promise<GapAnalysisResult | null> {
  const key = CACHE_PREFIX + normalizeUrl(url);
  const result = await chrome.storage.local.get(key);
  if (!result[key]) return null;
  const cached = result[key] as GapAnalysisResult;
  if (Date.now() - (cached.cached_at || 0) > TTL_MS) {
    await chrome.storage.local.remove(key);
    return null;
  }
  return cached;
}

export async function setCachedGap(url: string, result: GapAnalysisResult): Promise<void> {
  const key = CACHE_PREFIX + normalizeUrl(url);
  result.cached_at = Date.now();
  result.job_url = url;
  await chrome.storage.local.set({ [key]: result });
}

export async function clearCachedGap(url: string): Promise<void> {
  const key = CACHE_PREFIX + normalizeUrl(url);
  await chrome.storage.local.remove(key);
}

export async function clearAllGapCache(): Promise<void> {
  const all = await chrome.storage.local.get(null);
  const gapKeys = Object.keys(all).filter(k => k.startsWith(CACHE_PREFIX));
  await chrome.storage.local.remove(gapKeys);
}
```

---

## Task 3: Background API Methods

**Files:** Modify `src/background/api.ts`

- [ ] **Step 1: Add saved jobs API methods**

```typescript
export async function saveJob(job: JobExtraction): Promise<SavedJob> {
  return apiPost('/api/saved-jobs', {
    url: job.url,
    title: job.title,
    company: job.company,
    location: job.location,
    salary_range: job.salary,
    jd_text: job.description,
    source: job.source,
    status: 'saved',
  });
}

export async function checkJobUrl(url: string): Promise<{ exists: boolean; saved_job?: SavedJob }> {
  const jobs = await apiGet(`/api/saved-jobs?url=${encodeURIComponent(url)}`);
  if (jobs && jobs.length > 0) {
    return { exists: true, saved_job: jobs[0] };
  }
  return { exists: false };
}

export async function getSavedJobs(): Promise<SavedJob[]> {
  return apiGet('/api/saved-jobs');
}
```

- [ ] **Step 2: Add gap analysis API methods**

```typescript
export async function runGapAnalysis(jdText: string): Promise<GapAnalysisResult> {
  const response = await apiPost('/api/gap-analysis', { jd_text: jdText });
  return {
    fit_score: response.fit_score ?? response.score ?? 0,
    strong_matches: response.strong_matches ?? [],
    partial_matches: response.partial_matches ?? [],
    gaps: response.gaps ?? [],
    recommendations: response.recommendations ?? [],
    job_url: '',
  };
}

export async function persistGapAnalysis(savedJobId: number, result: GapAnalysisResult): Promise<void> {
  await apiPost('/api/gap-analyses', {
    saved_job_id: savedJobId,
    jd_text: '',  // already stored on saved_job
    strong_matches: result.strong_matches,
    partial_matches: result.partial_matches,
    gaps: result.gaps,
    fit_score: result.fit_score,
    recommendations: result.recommendations,
  });
}
```

---

## Task 4: Background Message Handlers

**Files:** Modify `src/background/messages.ts`

- [ ] **Step 1: Implement SAVE_JOB handler**

Replace the stub with:
```typescript
case MSG.SAVE_JOB: {
  const { job } = message.data as SaveJobPayload;
  // Check duplicate first
  const dupeCheck = await checkJobUrl(job.url);
  if (dupeCheck.exists) {
    return { saved_job: dupeCheck.saved_job, already_existed: true };
  }
  const savedJob = await saveJob(job);
  // If we have a cached gap analysis, persist it linked to the new saved_job
  const cachedGap = await getCachedGap(job.url);
  if (cachedGap) {
    await persistGapAnalysis(savedJob.id, cachedGap);
  }
  return { saved_job: savedJob, already_existed: false };
}
```

- [ ] **Step 2: Implement RUN_GAP_ANALYSIS handler**

```typescript
case MSG.RUN_GAP_ANALYSIS: {
  const { jd_text, job_url, force_refresh, saved_job_id } = message.data as GapAnalysisPayload;
  // Check cache unless force refresh
  if (!force_refresh) {
    const cached = await getCachedGap(job_url);
    if (cached) {
      return { result: cached, from_cache: true };
    }
  }
  // Run analysis
  const result = await runGapAnalysis(jd_text);
  result.job_url = job_url;
  // Cache it
  await setCachedGap(job_url, result);
  // If linked to a saved job, persist to backend
  if (saved_job_id) {
    await persistGapAnalysis(saved_job_id, result);
  }
  return { result, from_cache: false };
}
```

- [ ] **Step 3: Implement CHECK_JOB_URL handler**

```typescript
case MSG.CHECK_JOB_URL: {
  const { url } = message.data as CheckJobUrlPayload;
  const check = await checkJobUrl(url);
  return { exists: check.exists, saved_job: check.saved_job };
}
```

- [ ] **Step 4: Implement GET_SAVED_JOBS handler**

```typescript
case MSG.GET_SAVED_JOBS: {
  const jobs = await getSavedJobs();
  return { jobs };
}
```

---

## Task 5: Backend — Duplicate Check + AI Routing Pattern

**Files:** Modify `code/backend/routes/saved_jobs.py`, `code/backend/routes/search.py`, Create `code/backend/ai_providers/router.py`

- [ ] **Step 1: Add URL filter to GET /api/saved-jobs**

The existing `GET /api/saved-jobs` endpoint needs to accept an optional `?url=` query param. If provided, filter by exact URL match. This enables the duplicate check from the extension without a new endpoint.

```python
# In saved_jobs.py list_saved_jobs():
url_filter = request.args.get('url')
if url_filter:
    clauses.append("sj.url = %s")
    params.append(url_filter)
```

- [ ] **Step 2: Build reusable AI routing utility**

Create `code/backend/ai_providers/router.py` — the central AI routing utility:

```python
"""AI routing: check provider availability, route inference through AI or fall back to Python."""
from ai_providers import get_provider, list_providers

def ai_available() -> bool:
    """Check if any AI provider is configured and healthy."""
    providers = list_providers()
    for p in providers:
        if p.get("available"):
            return True
    return False

def route_inference(task: str, context: dict, python_fallback: callable, ai_handler: callable = None):
    """Route an inference task through AI if available, otherwise Python fallback.

    Args:
        task: Description of the inference task (for logging)
        context: Data needed for the inference (JD text, etc.)
        python_fallback: Callable that does rule-based Python processing
        ai_handler: Callable that does AI-enhanced processing (optional)

    Returns:
        Result from whichever handler ran, plus metadata about which path was taken.
    """
    used_ai = False
    if ai_handler and ai_available():
        try:
            result = ai_handler(context)
            used_ai = True
        except Exception:
            # AI failed, fall back to Python
            result = python_fallback(context)
    else:
        result = python_fallback(context)

    result["_analysis_mode"] = "ai" if used_ai else "rule_based"
    return result
```

- [ ] **Step 3: Retrofit POST /api/gap-analysis with AI routing**

Update `search.py` gap_analysis() to use the router:
- Extract the existing keyword-matching logic into a `_python_gap_analysis(context)` function
- Create an `_ai_gap_analysis(context)` function that calls the AI provider for semantic matching
- Call `route_inference()` to pick the right one
- Response includes `"analysis_mode": "ai" | "rule_based"` so the extension knows what it got

- [ ] **Step 4: Normalize gap analysis response shape**

Both Python and AI paths must return the same shape so the extension doesn't need to branch:
```python
{
    "fit_score": float,           # 0-100
    "strong_matches": [str, ...], # skills/requirements with strong evidence
    "partial_matches": [str, ...],# skills with partial evidence
    "gaps": [str, ...],           # requirements with no evidence
    "recommendations": [str, ...],# suggestions for addressing gaps
    "jd_keywords": [str, ...],    # extracted keywords
    "analysis_mode": str,         # "ai" | "rule_based"
}
```

The Python fallback maps its existing output to this shape:
- `matched_bullets` + `matched_skills` → `strong_matches` (items with direct keyword matches)
- `coverage_pct` → `fit_score`
- `gaps` → `gaps`
- Generate basic `recommendations` from gaps (e.g., "Consider highlighting experience with {gap}")

- [ ] **Step 5: Rebuild Docker container**

```bash
cd code && docker compose up -d --build supertroopers-app
```

---

## Task 6: Save Button Injection

**Files:** Create `src/content/saveButton.ts`

- [ ] **Step 1: Create save button component**

```typescript
import { createShadowContainer } from './shadow';
import { sendMessage } from '../shared/messages';
import { MSG } from '../shared/messages';
import type { JobExtraction } from '../shared/types';

type ButtonState = 'save' | 'saving' | 'saved' | 'already_saved' | 'error';

export function injectSaveButton(anchor: Element, job: JobExtraction): void {
  const container = createShadowContainer('st-save-btn');
  const shadow = container.shadowRoot!;

  const btn = document.createElement('button');
  btn.className = 'st-btn st-btn-save';
  setState('save');

  shadow.appendChild(btn);

  // Check if already saved
  sendMessage({ type: MSG.CHECK_JOB_URL, data: { url: job.url } })
    .then((resp) => {
      if (resp?.exists) setState('already_saved');
    })
    .catch(() => {}); // offline = show save button anyway

  btn.addEventListener('click', async () => {
    if (btn.dataset.state === 'saved' || btn.dataset.state === 'already_saved') return;
    setState('saving');
    try {
      const resp = await sendMessage({ type: MSG.SAVE_JOB, data: { job } });
      setState(resp.already_existed ? 'already_saved' : 'saved');
    } catch {
      setState('error');
      setTimeout(() => setState('save'), 3000);
    }
  });

  function setState(state: ButtonState) {
    btn.dataset.state = state;
    const labels: Record<ButtonState, string> = {
      save: '⬡ Save to SuperTroopers',
      saving: '⬡ Saving...',
      saved: '✓ Saved',
      already_saved: '✓ Already Saved',
      error: '✗ Error — Retry?',
    };
    btn.textContent = labels[state];
    btn.disabled = state === 'saving' || state === 'saved' || state === 'already_saved';
    btn.classList.toggle('st-btn-disabled', btn.disabled);
    btn.classList.toggle('st-btn-success', state === 'saved' || state === 'already_saved');
    btn.classList.toggle('st-btn-error', state === 'error');
  }

  // Insert near anchor
  anchor.parentElement?.insertBefore(container, anchor.nextSibling);
}
```

- [ ] **Step 2: Add CSS to shadow.ts for button states**

Add to the shadow DOM stylesheet:
```css
.st-btn-save {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  margin: 8px 0;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid #00FF41;
  border-radius: 6px;
  background: rgba(0, 255, 65, 0.1);
  color: #00FF41;
  transition: all 0.2s;
}
.st-btn-save:hover:not(.st-btn-disabled) {
  background: rgba(0, 255, 65, 0.25);
}
.st-btn-disabled { opacity: 0.7; cursor: default; }
.st-btn-success { border-color: #00FF41; color: #00FF41; background: rgba(0, 255, 65, 0.15); }
.st-btn-error { border-color: #ff4444; color: #ff4444; background: rgba(255, 68, 68, 0.1); }
```

---

## Task 7: Score Overlay Injection

**Files:** Create `src/content/scoreOverlay.ts`

- [ ] **Step 1: Create score badge (floating circle)**

```typescript
import { createShadowContainer } from './shadow';
import type { GapAnalysisResult } from '../shared/types';

export function injectScoreOverlay(result: GapAnalysisResult): { update: (r: GapAnalysisResult) => void; remove: () => void } {
  const container = createShadowContainer('st-score-overlay');
  const shadow = container.shadowRoot!;

  // Position: fixed bottom-right, above any cookie banners
  container.style.cssText = 'position:fixed; bottom:80px; right:20px; z-index:2147483646;';

  const badge = document.createElement('div');
  badge.className = 'st-score-badge';

  const panel = document.createElement('div');
  panel.className = 'st-score-panel st-hidden';

  shadow.appendChild(badge);
  shadow.appendChild(panel);
  document.body.appendChild(container);

  badge.addEventListener('click', () => panel.classList.toggle('st-hidden'));

  function update(r: GapAnalysisResult) {
    const score = Math.round(r.fit_score);
    const color = score >= 75 ? '#00FF41' : score >= 50 ? '#FFD700' : '#ff4444';

    badge.innerHTML = `
      <svg viewBox="0 0 80 80" width="64" height="64">
        <circle cx="40" cy="40" r="36" fill="#1a1a2e" stroke="${color}" stroke-width="3"/>
        <text x="40" y="36" text-anchor="middle" fill="${color}" font-size="22" font-weight="bold">${score}</text>
        <text x="40" y="52" text-anchor="middle" fill="#e0e0e0" font-size="9">FIT</text>
      </svg>
    `;

    panel.innerHTML = `
      <div class="st-panel-header">
        <span class="st-panel-title">Match Analysis</span>
        <button class="st-panel-close">✕</button>
      </div>
      <div class="st-panel-section st-strong">
        <div class="st-section-label">Strong Matches (${r.strong_matches.length})</div>
        ${r.strong_matches.map(s => `<div class="st-match-item">✓ ${s}</div>`).join('')}
      </div>
      <div class="st-panel-section st-partial">
        <div class="st-section-label">Partial Matches (${r.partial_matches.length})</div>
        ${r.partial_matches.map(s => `<div class="st-match-item">◐ ${s}</div>`).join('')}
      </div>
      <div class="st-panel-section st-gaps">
        <div class="st-section-label">Gaps (${r.gaps.length})</div>
        ${r.gaps.map(s => `<div class="st-match-item">✗ ${s}</div>`).join('')}
      </div>
      ${r.recommendations.length ? `
      <div class="st-panel-section st-recs">
        <div class="st-section-label">Recommendations</div>
        ${r.recommendations.map(s => `<div class="st-match-item">→ ${s}</div>`).join('')}
      </div>` : ''}
      <button class="st-btn st-btn-refresh">↻ Refresh Analysis</button>
    `;

    // Wire close button
    panel.querySelector('.st-panel-close')?.addEventListener('click', (e) => {
      e.stopPropagation();
      panel.classList.add('st-hidden');
    });

    // Wire refresh button
    panel.querySelector('.st-btn-refresh')?.addEventListener('click', () => {
      // Dispatch custom event for jobCapture to handle
      container.dispatchEvent(new CustomEvent('st-refresh-gap'));
    });
  }

  update(result);

  return {
    update,
    remove: () => container.remove(),
  };
}
```

- [ ] **Step 2: Add score overlay CSS to shadow.ts**

```css
.st-score-badge { cursor: pointer; filter: drop-shadow(0 2px 8px rgba(0,0,0,0.5)); }
.st-score-badge:hover { transform: scale(1.1); transition: transform 0.2s; }
.st-score-panel {
  position: absolute; bottom: 72px; right: 0; width: 320px;
  background: #1a1a2e; border: 1px solid #00FF41; border-radius: 8px;
  padding: 12px; font-family: system-ui, sans-serif; color: #e0e0e0;
  max-height: 400px; overflow-y: auto;
  box-shadow: 0 4px 24px rgba(0,0,0,0.6);
}
.st-hidden { display: none; }
.st-panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.st-panel-title { font-size: 14px; font-weight: 700; color: #00FF41; }
.st-panel-close { background: none; border: none; color: #e0e0e0; cursor: pointer; font-size: 16px; }
.st-section-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin: 8px 0 4px; }
.st-strong .st-section-label { color: #00FF41; }
.st-partial .st-section-label { color: #FFD700; }
.st-gaps .st-section-label { color: #ff4444; }
.st-recs .st-section-label { color: #88aaff; }
.st-match-item { font-size: 12px; padding: 2px 0; line-height: 1.4; }
.st-btn-refresh {
  width: 100%; margin-top: 8px; padding: 6px; font-size: 12px;
  background: rgba(0,255,65,0.1); border: 1px solid #00FF41;
  color: #00FF41; border-radius: 4px; cursor: pointer;
}
.st-btn-refresh:hover { background: rgba(0,255,65,0.25); }
```

---

## Task 8: Job Capture Orchestrator

**Files:** Create `src/content/jobCapture.ts`, modify `src/content/index.ts`

- [ ] **Step 1: Create jobCapture.ts — the orchestrator**

This ties together detection → extraction → button injection → gap analysis → score overlay:

```typescript
import { extractJobData, getPageType } from './detector';
import { injectSaveButton } from './saveButton';
import { injectScoreOverlay } from './scoreOverlay';
import { sendMessage } from '../shared/messages';
import { MSG } from '../shared/messages';
import type { JobExtraction, GapAnalysisResult } from '../shared/types';
import siteConfig from '../config/siteConfig.json';

let currentOverlay: { update: (r: GapAnalysisResult) => void; remove: () => void } | null = null;
let lastProcessedUrl: string | null = null;

export async function processJobPage(): Promise<void> {
  const pageType = getPageType();
  if (pageType !== 'job_listing') return;

  // Avoid re-processing same URL (SPA nav can re-trigger)
  if (lastProcessedUrl === window.location.href) return;
  lastProcessedUrl = window.location.href;

  // Clean up previous overlay
  currentOverlay?.remove();
  currentOverlay = null;

  // Extract job data
  const job = extractJobData();
  if (!job || !job.title) return;

  // Find injection anchor from siteConfig
  const anchor = findInjectionAnchor();
  if (anchor) {
    injectSaveButton(anchor, job);
  }

  // Run gap analysis (async, non-blocking for button)
  if (job.description && job.description.length > 50) {
    try {
      const resp = await sendMessage({
        type: MSG.RUN_GAP_ANALYSIS,
        data: { jd_text: job.description, job_url: job.url },
      });
      if (resp?.result) {
        const overlay = injectScoreOverlay(resp.result);
        currentOverlay = overlay;

        // Handle refresh requests
        document.querySelector('st-score-overlay')?.addEventListener('st-refresh-gap', async () => {
          const refreshResp = await sendMessage({
            type: MSG.RUN_GAP_ANALYSIS,
            data: { jd_text: job.description, job_url: job.url, force_refresh: true },
          });
          if (refreshResp?.result) overlay.update(refreshResp.result);
        });
      }
    } catch {
      // Backend offline — no score overlay, button still works when online
    }
  }
}

function findInjectionAnchor(): Element | null {
  const hostname = window.location.hostname;
  // Try siteConfig-defined selectors for each board
  for (const [board, config] of Object.entries(siteConfig)) {
    if (hostname.includes(config.hostname || board)) {
      const anchor = document.querySelector(config.saveButtonAnchor || config.selectors?.title || 'h1');
      if (anchor) return anchor;
    }
  }
  // Fallback: first h1 on page
  return document.querySelector('h1');
}

// Re-process on SPA navigation
export function resetProcessedUrl(): void {
  lastProcessedUrl = null;
}
```

- [ ] **Step 2: Wire jobCapture into content/index.ts**

Update the content script entry point to call `processJobPage()` on initial load and on SPA navigation (the MutationObserver from F0 already watches for URL changes — hook `processJobPage` into that callback and call `resetProcessedUrl()` on URL change).

---

## Task 9: siteConfig Updates

**Files:** Modify `src/config/siteConfig.json`

- [ ] **Step 1: Add saveButtonAnchor selectors for each board**

For each job board config, add a `saveButtonAnchor` field — the CSS selector for where to inject the Save button. This should be near the job title or apply button.

```json
{
  "indeed": {
    "saveButtonAnchor": ".jobsearch-JobInfoHeader-title-container, .jcs-JobTitle"
  },
  "linkedin": {
    "saveButtonAnchor": ".job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title"
  },
  "glassdoor": {
    "saveButtonAnchor": "[data-test='jobTitle'], .css-1j389vi"
  }
}
```

- [ ] **Step 2: Add ZipRecruiter, Dice, BuiltIn, Handshake configs**

```json
{
  "ziprecruiter": {
    "hostname": "ziprecruiter.com",
    "patterns": ["/jobs/", "/job/"],
    "selectors": {
      "title": "h1.job_title, h1[class*='JobTitle']",
      "company": "a.company_name, [class*='CompanyName']",
      "location": "span.location, [class*='Location']",
      "salary": "[class*='Salary'], [class*='salary']",
      "description": ".job_description, [class*='Description']"
    },
    "saveButtonAnchor": "h1.job_title, h1[class*='JobTitle']"
  },
  "dice": {
    "hostname": "dice.com",
    "patterns": ["/job-detail/"],
    "selectors": {
      "title": "h1[data-cy='jobTitle'], h1.jobTitle",
      "company": "a[data-cy='companyNameLink'], .companyName",
      "location": "li.location, [data-cy='location']",
      "salary": "[data-cy='salary']",
      "description": ".job-description, #jobDescription"
    },
    "saveButtonAnchor": "h1[data-cy='jobTitle'], h1.jobTitle"
  },
  "builtin": {
    "hostname": "builtin.com",
    "patterns": ["/job/"],
    "selectors": {
      "title": "h1",
      "company": "[class*='company-name'], .company-info a",
      "location": "[class*='job-location']",
      "salary": "[class*='salary']",
      "description": "[class*='job-description'], .job-description"
    },
    "saveButtonAnchor": "h1"
  },
  "handshake": {
    "hostname": "joinhandshake.com",
    "patterns": ["/stu/jobs/", "/emp/jobs/"],
    "selectors": {
      "title": "h1",
      "company": "[class*='employer-name'], a[href*='employers']",
      "location": "[class*='location']",
      "salary": "[class*='salary']",
      "description": "[class*='description'], .job-description"
    },
    "saveButtonAnchor": "h1"
  }
}
```

---

## Task 10: Saved Jobs Tab in Popup

**Files:** Create `src/popup/components/SavedJobs.tsx`, modify `src/popup/App.tsx`

- [ ] **Step 1: Create SavedJobs component**

```typescript
import { useState, useEffect } from 'react';
import { sendMessage, MSG } from '../../shared/messages';
import type { SavedJob } from '../../shared/types';

export function SavedJobs() {
  const [jobs, setJobs] = useState<SavedJob[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    chrome.runtime.sendMessage({ type: MSG.GET_SAVED_JOBS })
      .then((resp) => { setJobs(resp?.jobs || []); })
      .catch(() => { setJobs([]); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-4 text-center text-gray-400">Loading...</div>;
  if (jobs.length === 0) return (
    <div className="p-4 text-center text-gray-400">
      <p className="text-lg mb-2">No saved jobs yet</p>
      <p className="text-sm">Visit a job listing and click "Save to SuperTroopers"</p>
    </div>
  );

  return (
    <div className="p-2 space-y-2 max-h-[400px] overflow-y-auto">
      {jobs.map(job => (
        <JobCard key={job.id} job={job} />
      ))}
    </div>
  );
}

function JobCard({ job }: { job: SavedJob }) {
  const score = job.fit_score;
  const scoreColor = !score ? 'text-gray-400' : score >= 75 ? 'text-green-400' : score >= 50 ? 'text-yellow-400' : 'text-red-400';

  return (
    <div className="bg-[#16213e] rounded-lg p-3 border border-[#2a2a4a] hover:border-[#00FF41]/30 transition">
      <div className="flex justify-between items-start">
        <div className="flex-1 min-w-0">
          <a
            href={job.url}
            target="_blank"
            rel="noopener"
            className="text-[#00FF41] text-sm font-semibold hover:underline truncate block"
          >
            {job.title}
          </a>
          <div className="text-gray-300 text-xs mt-0.5">{job.company}</div>
          {job.location && <div className="text-gray-500 text-xs">{job.location}</div>}
        </div>
        <div className="flex-shrink-0 ml-2 text-center">
          {score != null ? (
            <div className={`text-lg font-bold ${scoreColor}`}>{Math.round(score)}%</div>
          ) : (
            <div className="text-gray-500 text-xs">--</div>
          )}
          <div className="text-gray-500 text-[10px]">FIT</div>
        </div>
      </div>
      <div className="flex items-center gap-2 mt-2">
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#1a1a2e] text-gray-400 uppercase">{job.source}</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#1a1a2e] text-gray-400 uppercase">{job.status}</span>
        {job.salary_range && <span className="text-[10px] text-gray-500">{job.salary_range}</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire SavedJobs into App.tsx Jobs tab**

Replace the "Coming in Phase 1" placeholder in the Jobs tab case with `<SavedJobs />`.

---

## Task 11: Build + Test

- [ ] **Step 1: Build the extension**

```bash
cd code/extension && npm run build
```

Fix any TypeScript errors.

- [ ] **Step 2: Reload in Chrome**

Go to `chrome://extensions`, click "Reload" on SuperTroopers. Check the service worker console for errors.

- [ ] **Step 3: Test save flow on Indeed**

1. Go to indeed.com, search for a job, click into a listing
2. Verify "Save to SuperTroopers" button appears near the job title
3. Click it — should change to "Saved ✓"
4. Navigate away, come back — should show "Already Saved"
5. Check popup Jobs tab — job should appear in the list

- [ ] **Step 4: Test gap analysis flow**

1. On same job listing, verify score badge appears (bottom-right)
2. Click badge — panel expands with Strong Matches / Partial / Gaps
3. Click refresh — should re-run analysis
4. Navigate to another job — old overlay removed, new one appears
5. Revisit first job — should load from cache (instant)

- [ ] **Step 5: Test SPA navigation (LinkedIn)**

1. Go to LinkedIn jobs, click into a listing
2. Verify button + score overlay inject
3. Click a different job listing (SPA nav, no full page reload)
4. Verify old button/overlay removed, new ones injected

- [ ] **Step 6: Test offline resilience**

1. Stop Docker containers
2. Visit a job listing — button should still appear (save will fail with error state)
3. Score overlay should not appear (graceful degradation)
4. Start containers back up — save should work again

---

## Acceptance Criteria (maps to spec requirements)

| Req | Description | Task |
|-----|-------------|------|
| 14.1.1 | Detect job listings on Indeed, LinkedIn, Glassdoor | F0 (done) + Task 9 |
| 14.1.2 | Detect ATS career sites | Deferred to F2 |
| 14.1.3 | Auto-extract job details from DOM | F0 (done) |
| 14.1.4 | Inject Save button | Task 6 |
| 14.1.5 | POST to /api/saved-jobs | Tasks 3, 4 |
| 14.1.6 | Inline save confirmation | Task 6 |
| 14.1.7 | Already Saved state | Tasks 5, 6 |
| 14.1.8 | Manual save via popup | Deferred (nice-to-have) |
| 14.1.9 | siteConfig.json with selectors | F0 (done) + Task 9 |
| 14.1.10 | SPA navigation handling | F0 (done) + Task 8 |
| 14.2.1 | Auto-send JD for analysis | Task 8 |
| 14.2.2 | POST /api/gap-analysis | Task 3 |
| 14.2.3 | Score overlay | Task 7 |
| 14.2.4 | Color-coded score | Task 7 |
| 14.2.5 | Expandable analysis panel | Task 7 |
| 14.2.6 | Cache with 24h TTL | Task 2 |
| 14.2.7 | Refresh button | Task 7 |
| 14.2.8 | Persist gap analysis for saved jobs | Task 4 |
| 14.2.9 | "Why this score?" detail | Task 7 (panel shows full breakdown) |
| 14.2.10 | Don't obstruct apply button | Task 7 (positioned bottom-right) |

**Deferred to F2:**
- 14.1.2 — ATS career sites (Workday, Greenhouse, Lever, iCIMS)
- 14.1.8 — Manual save via popup URL paste
