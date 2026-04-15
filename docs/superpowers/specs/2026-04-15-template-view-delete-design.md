# Template View/Delete/Swap — Design Spec

**Date:** 2026-04-15
**Workstream:** WS1 — Resume Builder
**Status:** Approved

---

## Overview

Add template management to the platform: a gallery tab on the Resumes page for browsing and deleting templates, a slide-out panel in the Resume Editor for swapping templates, a safe delete flow with recipe reassignment, and a default template for new users.

## Key Concepts

- **Templates** are reusable .docx layout shells. They define formatting for section types (jobs, skills, education, summary, etc.) and data flows in dynamically.
- **Recipes** map data (bullets, career history, skills) to a template. Swapping templates changes the visual layout without touching the data.
- Templates are created by uploading/parsing a resume. The parsing flow extracts both the template (layout) and data (bullets, career history). Deleting a template only removes the layout shell... all parsed data stays.

## 1. Template Gallery Tab

**Location:** Resumes page gets two tabs — "My Resumes" (existing recipe list) | "Templates" (new).

**Layout:** Card grid (3 columns on desktop, responsive).

**Each card shows:**
- Real thumbnail from `GET /api/resume/templates/<id>/thumbnail`
- Template name
- Recipe count ("3 recipes using this")
- Upload date
- Active/inactive badge (inactive cards slightly dimmed)
- Default badge if `is_default = true`
- Actions: View (download .docx), Delete (triggers reassignment modal)

**No upload button** — templates come from the resume parsing flow.

**No filtering/search** — 14 templates doesn't warrant it. Easy to add later if count grows.

## 2. Delete Flow

**Trigger:** Delete action on a template card.

**Zero-recipe delete:** Simple confirmation — "Are you sure? This removes the template layout. All parsed data stays." Single Delete button.

**Has-recipe delete:** Modal with recipe reassignment:
- Header: "Delete Template: {name}"
- Warning: "This template has {N} recipes using it"
- List of affected recipes, each with a dropdown to reassign to a different template
- Bulk dropdown at top: "Assign all to: {template}"
- Two action buttons:
  - "Delete Template + Reassign Recipes" (primary) — deletes template, updates each recipe's `template_id`
  - "Delete Template + Delete Recipes" (destructive/red) — deletes template and all linked recipes, data stays
- Default template (`is_default = true`) cannot be deleted — delete button hidden/disabled with tooltip

## 3. Editor Template Swap

**Location:** Existing template section in the Resume Editor.

**Current state:** Empty image placeholder.

**New behavior:**
- Show real thumbnail of current template (from `/templates/<id>/thumbnail`)
- Template name + "Change" button below thumbnail
- "Change" opens a slide-out panel from the right
- Panel contents: all active templates as small cards with thumbnails, current template highlighted with blue border
- Click a template to select, then "Apply Template" to confirm
- On apply: `PUT /api/resume/recipes/<id>` with new `template_id`, editor refreshes
- Cancel or click outside closes panel

**No data remapping needed** — recipe content refs stay the same, only the layout shell changes.

## 4. Default Template

**Purpose:** New users can generate a resume without uploading their own first.

**Source:** A scrubbed empty .docx template based on the v32 resume layout, with all personal data removed (no names, contact info, bullet content, etc.). Just the formatting shell with placeholder section markers.

**Seed file:** The scrubbed .docx must be manually created and committed to `backend/seeds/default_template.docx`. This is a manual step — take the v32 layout, strip all content, leave only the structural formatting and placeholder sections.

**Behavior:**
- Flagged with `is_default = true` in `resume_templates`
- Shows "Default" badge on gallery card
- Cannot be deleted (delete button hidden/disabled)
- App startup checks if a default template exists — if not, loads from seed file

**DB change:** Add `is_default BOOLEAN DEFAULT FALSE` column to `resume_templates`.

## 5. Files to Create/Modify

### Frontend (new components)
- `frontend/src/pages/resumes/TemplateGallery.tsx` — card grid component for Templates tab
- `frontend/src/pages/resumes/DeleteTemplateModal.tsx` — delete confirmation with recipe reassignment
- `frontend/src/pages/resumes/TemplateSwapPanel.tsx` — slide-out panel for editor

### Frontend (modify)
- `frontend/src/pages/resumes/Resumes.tsx` — add tab navigation ("My Resumes" | "Templates")
- `frontend/src/pages/resumes/ResumeEditor.tsx` — replace empty image with real thumbnail + wire up swap panel

### Backend (modify)
- `backend/routes/resume.py` — extend `DELETE /api/resume/templates/<id>` to accept `{ "reassign_to": { recipe_id: new_template_id }, ... }` or `{ "delete_recipes": true }`. Return 409 with affected recipe list if recipes exist and no strategy provided.

### Database
- New migration: add `is_default BOOLEAN DEFAULT FALSE` to `resume_templates`

### Seed (manual step)
- `backend/seeds/default_template.docx` — scrubbed empty .docx based on v32 layout, no personal data. Must be manually created before the seed logic can load it.
- App startup or migration: if no template has `is_default = true`, load from seed file and insert

## 6. API Contract

### Extended DELETE /api/resume/templates/<id>

**Request body (optional):**
```json
{
  "reassign_to": { "5": 2, "8": 2 },
  "delete_recipes": false
}
```
- `reassign_to`: map of recipe_id -> new_template_id
- `delete_recipes`: if true, delete all linked recipes instead of reassigning

**Responses:**
- `200` — template deleted, recipes reassigned/deleted per request
- `409` — template has linked recipes, no strategy provided. Body: `{ "error": "...", "affected_recipes": [{ "id": 5, "name": "..." }, ...] }`
- `403` — cannot delete default template
- `404` — template not found

### No new endpoints needed
- `GET /api/resume/templates` — already returns list with recipe counts
- `GET /api/resume/templates/<id>/thumbnail` — already returns PNG
- `PUT /api/resume/recipes/<id>` — already supports updating `template_id`
