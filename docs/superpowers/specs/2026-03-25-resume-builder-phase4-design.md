# Resume Builder Phase 4 — AI Endpoints, Template System, E2E Testing

**Date:** 2026-03-25
**Session:** 25
**Status:** Design

---

## Overview

Complete the Resume Builder with four AI endpoints, a general-purpose resume parser/templatizer, a template browser, and an end-to-end validation pipeline that proves any uploaded resume can be round-tripped through the system (parse → template → recipe → generate → match original).

---

## 1. AI Review Endpoint

**Route:** `POST /api/resume/recipes/<id>/ai-review`

**Purpose:** Score a resume recipe on general quality and fit against the user's target roles.

### Input

```json
{
  "jd_text": "optional specific JD for comparison"
}
```

Recipe content is resolved server-side from the recipe ID.

### Output

```json
{
  "generic": {
    "score": 78,
    "feedback": [
      {"section": "summary", "issue": "Too generic, lacks metrics", "severity": "high"},
      {"section": "experience.job_2", "issue": "Only 2 bullets, add 1-2 more", "severity": "medium"},
      {"section": "highlights", "issue": "Bullet 3 repeats Job 1 content", "severity": "low"}
    ],
    "strengths": ["Strong metrics in Job 1", "Good keyword coverage"]
  },
  "target_roles": [
    {
      "role": "CTO",
      "score": 82,
      "gaps": ["Missing board reporting experience"],
      "suggestions": ["Add bullet about board presentations from Intellicheck"]
    },
    {
      "role": "VP Engineering",
      "score": 75,
      "gaps": ["Weak on team scaling metrics"],
      "suggestions": ["Quantify team growth at L3Harris"]
    }
  ],
  "analysis_mode": "ai"
}
```

### Python Fallback (rule-based)

- Bullet count per job: <3 = warning, >8 = warning
- Metrics scan: regex for numbers, percentages, dollar amounts in each bullet
- Summary length: <50 chars = too short, >500 chars = too long
- Duplicate text detection across sections
- Total page estimate (paragraph count heuristic)
- Target role scoring: keyword overlap between resolved resume text and known role keywords
- Target roles pulled from `settings.preferences.target_roles`

### AI Handler

- Sends resolved recipe text + target roles to Claude
- Prompt includes voice rules context via `get_voice_rules`
- Returns structured JSON with scores, feedback, and per-role analysis
- Merges with Python fallback results (AI score averaged with rule-based)

### Frontend: AiReviewPanel

- Collapsible sidebar panel in the Resume Builder (right side)
- Score gauge at top (0-100, color-coded)
- Feedback list with severity badges (red/yellow/blue)
- Clickable feedback items scroll editor to the referenced section
- Target role cards below with individual scores and gap lists
- "Refresh" button to re-run analysis after edits

---

## 2. AI Generate-Slot Endpoint

**Route:** `POST /api/resume/recipes/<id>/ai-generate-slot`

**Purpose:** Generate content for a specific slot in the recipe (bullet, summary, highlight, job intro).

### Input

```json
{
  "slot_type": "bullet",
  "context": {
    "job_id": 5,
    "existing_bullets": ["bullet text 1", "bullet text 2"],
    "target_role": "CTO",
    "instructions": "emphasize cost savings"
  }
}
```

Supported `slot_type` values: `bullet`, `summary`, `highlight`, `job_intro`

### Output

```json
{
  "suggestions": [
    {
      "text": "Reduced infrastructure costs by $2.1M annually through cloud migration...",
      "confidence": 0.9,
      "source": "career_history + bullets"
    },
    {
      "text": "Led cross-functional team of 45 engineers delivering...",
      "confidence": 0.8,
      "source": "generated"
    }
  ],
  "analysis_mode": "ai"
}
```

### Python Fallback

- For bullets: pulls unused bullets from same career_history job that aren't already in the recipe
- For summaries: pulls from `summary_variants` table
- For highlights: pulls highest-metric bullets across all jobs
- For job intros: pulls `career_history.intro_text` if it exists
- No generation... only surfaces existing unused content

### AI Handler

- Sends job context, existing bullets, target role, user instructions to Claude
- Prompt includes relevant career_history entry, all bullets for that job, skill tags
- Voice rules applied to generation prompt
- Returns 2-5 suggestions ranked by confidence
- All generated content must pass `check_voice` before returning to frontend

### Frontend: AiGenerateModal

- Triggered by "AI Generate" button on empty slots or "+" button on sections
- Modal shows slot type context (which job, what's already there)
- Optional "Instructions" text field for user guidance
- Suggestions displayed as selectable cards with source badges
- User picks one, optionally edits inline, confirms to insert into recipe
- "Regenerate" button for new suggestions

---

## 3. Best-Picks Endpoint

**Route:** `POST /api/resume/recipes/<id>/best-picks`

**Purpose:** Rank all available bullets and jobs by relevance to a specific JD.

### Input

```json
{
  "jd_text": "full job description...",
  "application_id": 42,
  "limit": 10
}
```

One of `jd_text` or `application_id` required. `application_id` pulls JD from the application record.

### Output

```json
{
  "ranked_bullets": [
    {
      "bullet_id": 87,
      "text": "Drove $4.2M revenue...",
      "relevance": 0.95,
      "job": "L3Harris",
      "matched_keywords": ["revenue", "growth"]
    }
  ],
  "ranked_jobs": [
    {
      "career_history_id": 5,
      "company": "L3Harris",
      "title": "VP Engineering",
      "relevance": 0.92,
      "reason": "Defense industry match + leadership scope"
    }
  ],
  "suggested_skills": ["kubernetes", "cost optimization", "stakeholder management"],
  "analysis_mode": "ai"
}
```

### Python Fallback

- Extract top 50 JD keywords (same logic as existing ATS scorer)
- Score each bullet by keyword overlap (word boundary matching)
- Score each job by aggregate bullet relevance
- Suggest skills that appear in JD but not in recipe
- Pure keyword density... no semantic understanding

### AI Handler

- Sends JD + all available bullets + career history to Claude
- Prompt asks for semantic relevance scoring, not just keyword matching
- Returns ranked lists with reasoning
- Suggests skills to add based on JD requirements vs available skills

### Frontend: BestPicksPanel

- Accessible from content picker or dedicated "Best Picks for JD" button in toolbar
- JD input: paste text or select from linked application
- Ranked bullet list with relevance scores and keyword highlights
- Drag bullets from best-picks into the recipe editor
- "Smart Fill" button: auto-populate an empty recipe from best picks (creates full recipe draft)
- Ranked jobs section shows which employers to emphasize

---

## 4. ATS Score in Builder

**Route:** `POST /api/resume/recipes/<id>/ats-score`

**Purpose:** Run ATS scoring from within the builder, reusing existing logic.

### Flow

1. Resolve recipe to full text server-side
2. If `jd_text` or `application_id` provided, score against that JD
3. If neither provided, score against each target role's typical keywords (from profile)
4. Pass to existing ATS scoring logic (80% keyword match + 20% formatting)
5. AI enhancement via `route_inference` when available

### Input

```json
{
  "jd_text": "optional JD text",
  "application_id": null
}
```

### Output

Same shape as existing ATS scorer: `ats_score`, `keyword_matches`, `match_percentage`, `formatting_flags`. When AI is available, adds `suggestions` array with improvement recommendations; Python fallback omits this field.

### Frontend: AtsScoreModal

- Wires to existing `onAtsScore` stub in ResumeEditor.tsx
- Score gauge with color coding
- Keyword hit/miss checklist (green checkmark / red X)
- Formatting warnings list
- If recipe has `application_id`, auto-loads that JD
- Otherwise, paste JD text field
- "Re-score" button after edits

---

## 5. General-Purpose Resume Parser/Templatizer

**Purpose:** Take any .docx resume and produce a reusable template + recipe. This is the critical path for E2E testing and for onboarding any resume into the system.

### Current State

`utils/templatize_resume.py` handles V31/V32 layouts via hardcoded slot patterns. This needs to become a general-purpose parser.

### New Pipeline

**Step 1: Section Detection** (`utils/resume_parser.py`)

Parse the .docx paragraph by paragraph and classify each into a section type:

- `header` — name, contact info (typically first 1-3 paragraphs, larger font or centered)
- `headline` — professional title/tagline (often bold, single line after header)
- `summary` — professional summary paragraph(s) (after headline, before experience)
- `highlights` — bullet list of key achievements (often before experience)
- `keywords` — skill/keyword lists (comma-separated or tag-style)
- `experience` — job blocks: company/title/dates header + bullet list
- `education` — degree entries
- `certifications` — cert entries
- `additional` — anything else (additional experience, volunteer, publications, references)

Detection heuristics:
- Font size changes signal section boundaries
- Bold standalone lines are likely section headers ("PROFESSIONAL EXPERIENCE", "EDUCATION")
- Bullet characters (•, -, ▪) indicate list items
- Date patterns (2019-2023, Jan 2020 - Present) indicate job headers or education entries
- Contact info patterns (email, phone, LinkedIn URL) identify header block
- AI enhancement: when available, send ambiguous paragraphs to Claude for classification

**Step 2: Formatting Extraction** (`utils/template_builder.py`)

For each detected section, capture the formatting structure:
- Font family, size, color, bold/italic for each run
- Paragraph alignment, spacing (before/after), indent level
- List style (bullet character, numbering)
- Section header style vs content style
- Page breaks, column layouts if present

Output: `template_map` JSON with slot definitions and formatting metadata per slot.

**Step 3: Placeholder Template Generation**

- Replace content with `{{SLOT_NAME}}` placeholders (e.g., `{{HEADER_NAME}}`, `{{JOB_1_BULLET_1}}`)
- Preserve all formatting on the placeholder text
- Store the original .docx structure as the template blob
- Handle variable-length sections: job blocks get `{{JOB_N_BULLETS}}` array markers

**Step 4: Recipe Creation**

- Match extracted content against DB records:
  - Bullets: fuzzy match against `bullets` table (>90% similarity = ref, otherwise literal)
  - Jobs: match company + title against `career_history`
  - Skills: match against `skills` table
  - Education/Certs: match against `education`/`certifications` tables
- Unmatched content stored as `{"literal": "text"}` in recipe
- Create recipe with `recipe_version: 2` format

**Step 5: Validation**

- Generate .docx from created recipe + template
- Compare against original: text content match + structural match
- Report: match percentage, any unmapped sections, any formatting discrepancies

### AI Enhancement

When AI is available:
- Section detection uses Claude for ambiguous paragraphs
- Content matching uses semantic similarity (not just fuzzy text match)
- Can suggest which DB records best match extracted content

---

## 6. Template Browser

**Location:** Resumes page, new "Templates" tab alongside existing tabs.

### List View

- Card grid layout with visual thumbnail previews of each template
- Thumbnail: rendered first page of the placeholder .docx as an image
  - Generated server-side: convert .docx → PDF → PNG thumbnail (or use python-docx + reportlab/pdf2image)
  - Cached in `resume_templates.thumbnail` (bytea column) on first generation
- Card shows: thumbnail, template name, slot count, layout type, date created, recipe count (how many recipes use it)

### Detail View

- Click a card to see full template details
- Slot map visualization: section names, slot types, formatting metadata
- List of recipes that reference this template
- Read-only... no editing

### Actions

- **Upload:** "Upload Template" button → file picker → runs templatize pipeline → shows extraction preview (detected sections, slot count) → confirm to save
- **Delete:** Soft-delete with confirmation dialog. Warns if active recipes reference it. Prevents delete if recipes exist (must reassign or delete recipes first).
- **Regenerate Thumbnail:** Force re-render of the preview image

### Thumbnail Generation

**Route:** `GET /api/resume/templates/<id>/thumbnail`

Uses existing `preview_blob BYTEA` column from migration 030 (no new migration needed).

Pipeline (runs inside Docker container using pure-Python Pillow):
1. Load template .docx blob from DB, write to temp file
2. Convert to PNG via `python-docx` → render paragraphs to HTML → `imgkit`/`wkhtmltoimage`, OR use `docx2pdf` (Windows-only, uses COM/Word) → `pdf2image`
3. Resize to thumbnail (300x400px) via Pillow
4. Cache in `resume_templates.preview_blob` column
5. Return as `image/png`

**Fallback if no rendering tools available:** Generate a styled HTML representation of the template structure (section headers, slot counts, layout diagram) and render that as the preview. Pure Python, no external dependencies.

---

## 7. End-to-End Resume Testing

**Script:** `local_code/e2e_resume_test.py`

### Purpose

Prove the full pipeline works: any resume can be uploaded, parsed, templatized, stored as recipe, and regenerated with both content and layout fidelity.

### Flow

1. **Discover** all .docx resumes in `Imports/`, `Archived/Originals/`, `Originals/`
2. **For each resume:**
   a. Upload via `POST /api/onboard/upload` (parse → templatize → create recipe)
   b. Generate .docx from created recipe via `POST /api/resume/generate`
   c. Run Gate 1: Content fidelity check
   d. Run Gate 2: Layout fidelity check
   e. Record results

### Gate 1: Content Fidelity

- Extract text from both original and generated .docx
- Normalize whitespace, quotes (curly → straight), encoding
- Diff text content section by section
- **Pass:** >95% text match (allowing for normalization differences)

### Gate 2: Layout Fidelity

- **Structural comparison:**
  - Same number of paragraphs/sections in same order
  - Same number of jobs, bullets per job, section headers
  - Template slot mapping is complete (no unmapped paragraphs)
- **Formatting comparison:**
  - Bold/italic/underline runs match per paragraph
  - Font sizes match (within 0.5pt tolerance)
  - Paragraph alignment matches (left/center/right)
  - List styles match (bullet characters, indent levels)
- **Visual comparison (optional, if pdf2image available):**
  - Render both as PDF → PNG
  - Pixel-level diff with tolerance threshold
  - Side-by-side output for manual review

### Output

Summary table per resume:

| File | Recipe ID | Template ID | Content Match % | Layout Match % | Status | Issues |
|------|-----------|-------------|-----------------|----------------|--------|--------|
| V32_Base.docx | 12 | 3 | 98.2% | 96.5% | PASS | Quote normalization |
| V31_AI_Architect.docx | 13 | 4 | 97.1% | 94.8% | PASS | Minor spacing diff |

### Test Data Management

- Tag test recipes with `name LIKE 'E2E_TEST_%'` prefix
- Cleanup function to delete all E2E test data after validation
- Option to keep successful parses as real templates/recipes if desired

### Known Issues to Handle

- v1 recipes with literals won't round-trip perfectly (flag, don't fail)
- Synopsis from `career_history` ref returning dict instead of string (fix in resolver)
- Curly/straight quote normalization (expected, not a failure)

---

## 8. DB Changes

### New Columns

```sql
-- Track parser version for re-parsing (preview_blob already exists from migration 030)
ALTER TABLE resume_templates ADD COLUMN IF NOT EXISTS parser_version VARCHAR(10) DEFAULT '1.0';
```

### No New Tables

All data fits in existing schema: `resume_templates` (already has `preview_blob` from migration 030), `resume_recipes`, `resume_header`, `career_history`, `bullets`, `skills`, `education`, `certifications`.

---

## 9. File Inventory

### New Files

| File | Purpose |
|------|---------|
| `backend/utils/resume_parser.py` | General-purpose section detection from any .docx |
| `backend/utils/template_builder.py` | Formatting extraction + placeholder template generation |
| `frontend/src/pages/resume-builder/AiReviewPanel.tsx` | AI review sidebar panel |
| `frontend/src/pages/resume-builder/AiGenerateModal.tsx` | AI slot generation modal |
| `frontend/src/pages/resume-builder/BestPicksPanel.tsx` | JD-based ranking panel |
| `frontend/src/pages/resume-builder/AtsScoreModal.tsx` | ATS score modal |
| `frontend/src/pages/resumes/TemplatesBrowser.tsx` | Template list with thumbnails |
| `frontend/src/pages/resumes/TemplateDetail.tsx` | Template detail view |
| `local_code/e2e_resume_test.py` | End-to-end validation script |
| `db/migrations/031_template_parser_version.sql` | parser_version column (preview_blob already in 030) |

### Modified Files

| File | Changes |
|------|---------|
| `backend/routes/resume.py` | Add 4 AI endpoints + template thumbnail route |
| `backend/routes/onboard.py` | Wire new parser/templatizer into upload pipeline |
| `utils/templatize_resume.py` | Refactor to use new general-purpose parser |
| `utils/generate_resume.py` | Fix synopsis dict extraction, improve v2 resolution |
| `frontend/src/pages/resume-builder/ResumeEditor.tsx` | Wire AI review + ATS score callbacks |
| `frontend/src/pages/resume-builder/EditorToolbar.tsx` | Add best-picks + generate-slot buttons |
| `frontend/src/pages/resume-builder/ContentPickerModal.tsx` | Integrate best-picks results |
| `frontend/src/pages/resumes/Resumes.tsx` | Add Templates tab |

---

## 10. Build Order

1. **General-purpose parser** (`resume_parser.py` + `template_builder.py`) — foundation for everything
2. **Template thumbnail generation** (migration 031 + thumbnail route) — enables template browser
3. **Template browser** (frontend) — visual template management
4. **ATS Score in Builder** + `AtsScoreModal` — reuses existing logic, proves route_inference wiring pattern
5. **AI Review endpoint** + `AiReviewPanel` — quality + target role scoring
6. **AI Generate-Slot endpoint** + `AiGenerateModal` — content creation in editor
7. **Best-Picks endpoint** + `BestPicksPanel` — JD-targeted content selection
8. **E2E testing script** — final validation gate
9. **Run E2E against all originals** — prove it works
