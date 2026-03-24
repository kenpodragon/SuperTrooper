# Bullet Browser Redesign — Design Spec

**Date:** 2026-03-24
**Status:** Approved
**Scope:** FE-7 from TODO.md

---

## Overview

A two-panel career content manager replacing the current recipe-focused Resumes page. Browse jobs on the left, manage synopses and bullets on the right. Plain text editing with optional AI-powered analysis, generation, and quality scoring. All AI features are opt-in via a toggle.

## Architecture

### Two-Panel Layout

- **Left panel (340px):** Job list with search, expand/collapse per job, inline view/edit for job details
- **Right panel (flex):** Synopsis section at top, bullet list below with filter/sort/AI toolbar

### Data Model Changes

Single migration adding columns to existing tables:

**bullets table:**

| Column | Type | Purpose |
|--------|------|---------|
| `display_order` | integer, default 0 | Drag-reorder position within a job |
| `ai_analysis` | JSONB, nullable | Persistent analysis results (strength, STAR, feedback, suggested skills) |
| `ai_analyzed_at` | timestamp, nullable | When last analyzed |
| `content_hash` | text, nullable | Hash of bullet text for staleness detection. Auto-updated via DB trigger on text change. |
| `is_default` | boolean, default false | For synopsis variants: which is the default. Enforced by partial unique index. |
| `updated_at` | timestamp, default now() | Auto-updated via DB trigger on any row change. Used for sort-by-newest. |

**Constraint:** `CREATE UNIQUE INDEX ON bullets (career_history_id) WHERE type = 'synopsis' AND is_default = TRUE;` — ensures only one default synopsis per job.

**Trigger:** `BEFORE UPDATE` trigger sets `content_hash = md5(NEW.text)` and `updated_at = NOW()` on every bullet edit.

**career_history table:**

| Column | Type | Purpose |
|--------|------|---------|
| `metadata` | JSONB, default '{}' | Custom key-value pairs (department, team size, tech stack, etc.) |
| `start_date_raw` | text, nullable | What user typed ("Mar 2022", "2022", etc.) |
| `end_date_raw` | text, nullable | What user typed ("Present", "Dec 2024", etc.) |
| `start_date_iso` | date, nullable | Parsed ISO date for recipe formatting |
| `end_date_iso` | date, nullable | Parsed ISO date (null = present/ongoing) |

**Backfill:** Set `content_hash` for all existing bullets. Copy existing date columns to raw/iso fields.

### Synopsis as Bullet Type

Synopsis variants are bullets with `type = 'synopsis'` linked to the same `career_history_id`. One is marked `is_default = true`. This keeps everything in one table, searchable, and the recipe system can reference synopses the same way it references bullets.

### Tags are Skills

Bullet tags are not a separate system. They map to the `skills` table by **case-insensitive name match**. The `bullets.tags` column remains `TEXT[]` for flexibility (users can type any tag). The "Update Skills" action (`POST /api/skills/sync-from-tags`) scans all bullet tags, finds tags that don't match any existing skill name, and creates new skill records for them. If a skill is renamed in the skills matrix, existing bullet tags are NOT auto-renamed (they're free text). One-way soft sync: bullet tags can exist even if the user hasn't added the skill to their profile. Removing a skill from profile doesn't remove the tag from bullets.

---

## Left Panel: Job List

### Collapsed State (default)
- Job title (bold) + company name
- Bullet count badge
- Expand arrow (triangular)

### Expanded State (view mode)
- Details grid: title, company, location, from date, to date, custom metadata fields
- "Edit" button to switch to edit mode
- "+ Add field" link for custom key-value pairs

### Edit Mode
- All fields become text inputs
- Smart date input for from/to dates (see below)
- Custom metadata: key + value inputs with + button to add more
- Save / Cancel buttons
- "Editing" label replaces "Details" label

### Smart Date Input
- Text field accepting any format: "2022", "Mar 2022", "03/2022", "March 15, 2022", "Present"
- Real-time parsing: shows resolved ISO date beside the input as you type
- Small calendar icon opens native date picker as fallback
- Auto-calculates and displays duration between from/to dates (e.g., "2 yrs 9 mos")
- Stores both raw text and parsed ISO date
- ISO date used by recipe generator for format-specific output (MMM YYYY, MM/YYYY, etc.)

### Supported Date Formats
| Input | Parsed ISO | Precision |
|-------|-----------|-----------|
| `2022` | 2022-01-01 | year only |
| `Mar 2022` | 2022-03-01 | month + year |
| `03/2022` | 2022-03-01 | month + year |
| `March 15, 2022` | 2022-03-15 | full date |
| `2022-03-15` | 2022-03-15 | ISO passthrough |
| `Present` | null | ongoing |

---

## Right Panel: Synopsis Section

### Layout
- Blue-accented section at top of right panel
- Variant tabs: "Default (star)", "Technical", "Leadership", etc. (user-named)
- Active variant's text shown in editable block
- Action buttons: Edit, Wordsmith (AI), Set Default, + New Variant, Generate (AI)

### Behavior
- Click a variant tab to view it
- "Set Default" marks the current variant as the one used by recipes
- "New Variant" creates a blank synopsis for this job
- "Generate" (AI) opens instruction modal: "Generate a synopsis focusing on..."
- Synopses are stored as bullets with `type = 'synopsis'`

---

## Right Panel: Bullet List

### Toolbar
- Filter text input (searches bullet text)
- Type dropdown (All types, Achievement, Leadership, Technical, etc.)
- Sort dropdown (Order, Strength, Newest)
- AI toggle button (on/off, default off)
- "Analyze All" button (grayed out when nothing is stale)
- "+ Add Bullet" button

### Bullet Card (view mode)
- Drag handle (left edge) for reorder
- Bullet text (plain text)
- Skill tags (colored badges)
- Strength badge (green=strong, yellow=moderate, red=weak) — only shown if analyzed
- AI feedback inline (italic text below bullet, e.g., "No metrics — what improvements did you drive?")
- Stale indicator: if bullet text changed since last analysis, show "needs re-analysis" badge
- Action buttons:
  - Edit (always)
  - Clone (always) — creates exact copy
  - Delete (always)
  - Wordsmith (AI only) — with optional instruction field
  - Generate Variant (AI only) — with instruction field
  - Strengthen (AI only, on weak bullets)

### Bullet Card (edit mode)
- Inline textarea replaces text display
- Save / Cancel buttons
- On save: run duplicate check before committing

### Adding a Bullet
- Click "+ Add Bullet" inserts a blank inline card at the bottom of the list
- Type text, save
- If AI is on, newly saved bullets auto-run through analysis

---

## AI Integration

### Toggle & Analyze All

- AI toggle in toolbar, default OFF
- When OFF: no analysis badges shown, no AI action buttons, duplicate check uses Python fuzzy matching only
- When ON: analysis badges appear (if data exists from prior runs), AI action buttons visible on each bullet
- "Analyze All" button: runs batch analysis on all bullets (or only stale ones if some are current)
- Progress indicator during analysis: "Analyzing bullet 12 of 48... 2m 30s elapsed"
- Results stored in `bullets.ai_analysis` JSONB per bullet
- Button grayed out when all bullets are current (no stale content hashes)

### AI Analysis JSONB Structure

```json
{
  "strength": "strong",
  "star_check": {
    "has_situation": true,
    "has_task": true,
    "has_action": true,
    "has_result": true
  },
  "feedback": "Strong bullet with clear metrics. Consider adding team context.",
  "suggested_skills": ["Microservices", "DevOps", "Cloud Architecture"],
  "content_hash_at_analysis": "abc123def456"
}
```

### Per-Bullet AI Actions

| Action | Instruction Field | Result |
|--------|-------------------|--------|
| Wordsmith | Optional ("make it more concise") | Updates bullet text in-place |
| Generate Variant | Required ("focus on leadership angle") | Creates new bullet linked to same job |
| Strengthen | Optional ("add scale/impact metrics") | Updates bullet text in-place |

All AI-generated/modified bullets auto-run through analysis on creation.

### Top-Level AI Actions

| Action | Instruction Field | Result |
|--------|-------------------|--------|
| Generate New Bullet | Required ("create bullet about cloud migration") | New bullet added to list + auto-analyzed |
| Analyze All | None | Batch analysis of all stale bullets |

### Duplicate Detection

Runs on every bullet save (not during analysis). Two tiers:

**Without AI (always runs):**
- Python `difflib.SequenceMatcher` or similar
- Ratio > 0.7 flags as similar
- Searches within-job AND cross-job
- Fast, always available

**With AI (when toggle is on):**
- Sends bullet text + top candidates from fuzzy match to AI
- Semantic similarity judgment with nuanced reasoning
- Richer feedback on why bullets are similar

**Result:** Non-blocking caution popup:
> "This bullet is similar to 2 bullets in this job and 1 bullet in your DataVersion CTO role [clickable links]. Continue saving?"

User can always proceed — it's advisory, not blocking.

---

## Backend Endpoints

### Existing (needs modification)
- `GET /api/bullets` — **add `career_history_id` filter param** to load bullets for a selected job efficiently
- `GET/POST/PATCH/DELETE /api/bullets/{id}` — full CRUD. **PATCH must recalculate `content_hash`** (or rely on DB trigger)
- `GET/POST/PATCH/DELETE /api/career-history` — full CRUD. **PATCH needs to accept new columns:** `metadata`, `start_date_raw`, `end_date_raw`, `start_date_iso`, `end_date_iso`

### New Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/bullets/{id}/clone` | Clone bullet (copy with new ID, same job) |
| `POST` | `/api/bullets/reorder` | Update display_order for drag-drop. Accepts `{career_history_id, items: [{id, order}]}` — scoped to one job. |
| `POST` | `/api/bullets/analyze` | Batch AI analysis. Accepts `{career_history_id}` or `{all: true}`. Uses SSE (server-sent events) to stream progress: `{current, total, bullet_id, status}`. Saves partial results — if interrupted, completed bullets retain their analysis. |
| `POST` | `/api/bullets/{id}/analyze` | Single bullet AI analysis |
| `POST` | `/api/bullets/generate` | AI generate new bullet with instruction text + career_history_id |
| `POST` | `/api/bullets/{id}/wordsmith` | AI polish with optional instruction |
| `POST` | `/api/bullets/{id}/variant` | AI generate variant with instruction |
| `POST` | `/api/bullets/{id}/check-duplicates` | Duplicate detection. Returns `{within_job: [...], cross_job: [...]}` with bullet text, job title, and similarity score. Cross-job uses pgvector cosine distance on `embedding` column when available, falls back to `difflib.SequenceMatcher`. |
| `GET` | `/api/bullets/stale-count` | Count of bullets needing re-analysis (for Analyze All button state). Optional `?career_history_id=` filter. |
| `POST` | `/api/skills/sync-from-tags` | "Update Skills" action — scans all bullet tags, creates missing skill records, returns summary of new skills added. |

---

## Frontend Components

| Component | Purpose |
|-----------|---------|
| `BulletBrowser` | Main page container, two-panel layout, AI toggle state |
| `JobList` | Left panel — search input, scrollable job list |
| `JobCard` | Single job — collapsed/expanded/edit modes |
| `SmartDateInput` | Reusable date text input + parser + calendar fallback + duration calc |
| `SynopsisEditor` | Right panel top — variant tabs, text editor, AI actions |
| `BulletList` | Right panel bottom — toolbar, filter/sort, bullet cards |
| `BulletCard` | Single bullet — view/edit modes, skill tags, strength badge, actions |
| `BulletEditInline` | Inline editing textarea (replaces BulletCard content) |
| `AiToolbar` | AI toggle + Analyze All button + progress bar |
| `AiInstructionModal` | Popup with instruction text field for generate/wordsmith/variant |
| `DuplicateWarning` | Caution popup on save showing similar bullets with links |

---

## Migration SQL (029_bullet_browser.sql)

```sql
-- Bullet Browser schema additions
ALTER TABLE bullets
  ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS ai_analysis JSONB,
  ADD COLUMN IF NOT EXISTS ai_analyzed_at TIMESTAMP,
  ADD COLUMN IF NOT EXISTS content_hash TEXT,
  ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE;

ALTER TABLE career_history
  ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS start_date_raw TEXT,
  ADD COLUMN IF NOT EXISTS end_date_raw TEXT,
  ADD COLUMN IF NOT EXISTS start_date_iso DATE,
  ADD COLUMN IF NOT EXISTS end_date_iso DATE;

-- Index for stale bullet detection
CREATE INDEX IF NOT EXISTS idx_bullets_content_hash ON bullets (content_hash);
CREATE INDEX IF NOT EXISTS idx_bullets_display_order ON bullets (career_history_id, display_order);

-- Partial unique index: only one default synopsis per job
CREATE UNIQUE INDEX IF NOT EXISTS idx_bullets_one_default_synopsis
  ON bullets (career_history_id)
  WHERE type = 'synopsis' AND is_default = TRUE;

-- updated_at column + trigger
ALTER TABLE bullets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

CREATE OR REPLACE FUNCTION bullets_update_trigger() RETURNS trigger AS $$
BEGIN
  NEW.content_hash := md5(NEW.text);
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_bullets_update ON bullets;
CREATE TRIGGER trg_bullets_update BEFORE UPDATE ON bullets
  FOR EACH ROW EXECUTE FUNCTION bullets_update_trigger();

-- Backfill content hashes for existing bullets
UPDATE bullets SET content_hash = md5(text) WHERE content_hash IS NULL AND text IS NOT NULL;

-- Backfill dates from existing columns (if start_date/end_date exist)
UPDATE career_history SET
  start_date_raw = COALESCE(start_date::text, ''),
  start_date_iso = start_date,
  end_date_raw = CASE WHEN end_date IS NULL THEN 'Present' ELSE end_date::text END,
  end_date_iso = end_date
WHERE start_date_raw IS NULL;
```

---

## Empty States

| Scenario | Display |
|----------|---------|
| No job selected | Right panel shows centered message: "Select a job from the left to view its bullets" |
| Job has zero bullets | Bullet area shows: "No bullets yet. Click + Add Bullet to create one." |
| Job has no synopsis | Synopsis area shows: "No synopsis. Click + New Variant to add one." |
| Zero career history | Left panel shows: "No jobs found. Import a resume or add a job manually." with + Add Job button |
| AI analysis fails mid-batch | Partial results saved. Error banner: "Analysis stopped at bullet 12/48: [error]. Completed bullets kept their results. Retry?" |
| AI action fails (wordsmith, generate) | Inline error in modal: "AI unavailable. Try again or edit manually." Original text preserved. |

---

## Visual Reference

Mockups created during brainstorming session are in `.superpowers/brainstorm/` — see `layout-v2.html` for the final approved layout showing:
- Left panel with expanded job in view mode and edit mode (with smart date picker)
- Right panel with synopsis variants and bullet list with strength badges
- AI analysis results inline on weak/duplicate bullets
