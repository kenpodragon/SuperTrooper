# KB Cleanup Wizard — Design Spec

**Date:** 2026-03-29
**Status:** Approved
**Scope:** AI-assisted deduplication, merge, and cleanup across all Knowledge Base entity types

---

## Overview

A sequential wizard that walks users through AI-assisted deduplication of their entire Knowledge Base after bulk imports. Accessible via an AI toggle on the KB page. When AI is ON, a "Clean Up Knowledge Base" button launches a full-screen modal wizard that processes each entity type in order, with three confirmation stages per entity.

This is primarily a post-import cleanup tool. Users will run it after bulk resume imports, LinkedIn data loads, or other large corpus ingestion. It is rerunnable... each run scans current state and finds new duplicates.

---

## Entry Point

- **AI toggle switch** on the KB page header (top-right area), labeled "AI Assist"
- Toggle OFF: no dedup button visible, no AI features active on KB page
- Toggle ON: "Clean Up Knowledge Base" button appears
- Toggle state persists to user settings across sessions
- Clicking the button launches the wizard as a full-screen modal overlay

---

## Wizard Structure

### Entity Processing Order

The wizard processes entities in this fixed order:

1. **Career History** — employer dedup, then role dedup under merged employers
2. **Bullets** — duplicate bullet merge within each role (cascade from step 1)
3. **Skills** — duplicate skill merge
4. **Education** — duplicate entry merge
5. **Certifications** — duplicate entry merge
6. **Summaries** — role_type cleanup, content splitting, then content dedup
7. **Languages** — dedup (skip if empty)
8. **References** — dedup (skip if empty)

**Rationale for order:** Career History must come first because employer/role merges cascade into Bullets. Bullets must come second to dedup the newly-pooled bullet sets. Summaries come after bullets because summary splitting may create new bullet entries. All other entities are independent.

### Progress Indicator

- Top bar showing all 8 entity types as steps
- Current step highlighted, completed steps checked, future steps grayed
- Within each step, a sub-indicator for the current stage (auto-merge / review / delete)

### Skip Logic

If AI finds zero items for all three stages of an entity, auto-skip with a brief inline message: "Skills: No duplicates found" with a checkmark. User doesn't have to click through empty steps.

### Cancel Behavior

- Cancel exits the wizard at any point
- Merges/deletes already confirmed in previous steps are committed (they execute per-step, not at the end)
- Anything in the current unconfirmed step is untouched

---

## Three Sub-Stages Per Entity

Each entity step walks through three stages in order:

### Stage 1: Auto-Merge (Green)

- **What:** AI-identified obvious duplicates (exact text match, trivial variations like "Microsoft" vs "Microsoft Corp")
- **Display:** List of merge groups. Each group shows all members with the AI-chosen "winner" bolded
- **User actions:**
  - **Confirm All** — accept all auto-merges and proceed
  - **Expand any group** — override the winner selection
  - **Pull group to Review** — demote a group to Stage 2 if unsure
- **Execution:** Confirmed merges execute immediately in a single DB transaction

### Stage 2: Needs Review (Yellow)

- **What:** AI thinks these might be duplicates but confidence is low... similar but not obvious
- **Display:** Side-by-side cards for each candidate pair/group, with differences highlighted
- **User actions per group:**
  - **Merge** — pick which record to keep (winner), others absorbed
  - **Not Duplicates** — leave all records as-is
  - **Move to Delete** — demote to Stage 3
- **Execution:** Confirmed merges execute after user finishes all review items

### Stage 3: Junk / Delete (Red)

- **What:** Items AI flagged as misclassified, garbled, or unusable
- **Display:** Each item shown with its content and AI's reason for flagging
- **User actions per item:**
  - **Delete** — remove from DB
  - **Reclassify** — move to correct entity type (e.g., bullet-like summary moved to bullets table). AI suggests target entity and career_history link if possible.
  - **Keep** — leave as-is, AI was wrong
- **Execution:** Confirmed deletes/reclassifications execute after user finishes all items

---

## Entity-Specific Logic

### 1. Career History

**Two-phase dedup within this step:**

**Phase A: Employer Merge**
- `career_history` has an `employer` text column (no separate employers table). AI groups rows by fuzzy employer name match, considering date overlap as a signal.
- Examples: "Microsoft Corp" / "Microsoft Corporation" / "MSFT", "Amazon" / "Amazon.com" / "Amazon Web Services"
- Merge normalizes the employer name across all matching career_history rows to a single canonical name (user picks or AI suggests the best one)

**Phase B: Role Merge (within each employer)**
- AI groups roles by similar title + overlapping dates
- Examples: "Sr. Director, Engineering" and "Senior Director of Engineering" at same employer with same timeframe
- Merge pools all bullets from merged roles under the surviving role record

**Foreign key handling:**
- `bullets.career_history_id` repointed to surviving career_history record
- `references.career_history_id` repointed to surviving career_history record
- Resume recipe slot references (`table: "bullets", id: X`) remain valid because bullet records are repointed, not deleted

### 2. Bullets

- Inherits any newly-pooled bullets from Career History merges in step 1
- AI uses semantic similarity (not just text matching) to find duplicates
  - "Led team of 12 engineers" and "Managed a 12-person engineering team" should surface as candidates
- Merge keeps the stronger bullet (more specific metrics, better voice, more detail)
- Junk stage catches parsing artifacts, incomplete fragments, garbled text

### 3. Skills

- AI groups by: exact name match (case-insensitive), abbreviation expansion ("JS" = "JavaScript"), synonyms ("Project Management" = "PM" = "Project Mgmt")
- Merge keeps the most complete record (one with category, proficiency, last_used_year filled in)
- Junk: entries that are clearly not skills (parsing artifacts, sentence fragments)

### 4. Education

- AI groups by: institution + degree similarity, date overlap
- "University of Phoenix" vs "Univ. of Phoenix" vs "U of Phoenix"
- Same degree at same school = merge, keep the one with more fields populated (location, type, field)

### 5. Certifications

- AI groups by: cert name similarity, issuer match
- "PMP" vs "Project Management Professional" = same cert
- "CSM" vs "Certified ScrumMaster" = same cert
- Merge keeps the record with `is_active` set if one has it and the other doesn't

### 6. Summaries

Summaries have three special operations beyond standard dedup:

**6a. Role Type Cleanup**
- Present all unique `role_type` values currently in the DB
- AI suggests meaningful categories based on summary content (CTO, VP Engineering, Director, PM, etc.)
- User assigns each role_type to a meaningful category, merges role_types that should be the same
- This happens first so duplicates are easier to spot once grouped by real role types

**6b. Content Splitting**
- AI analyzes each summary entry for mixed content (summary paragraph with bullet content jammed in)
- For mixed entries: AI extracts the summary portion (keeps as summary), splits out bullet-like fragments
- Extracted bullets moved to the bullets table, linked to the matching `career_history_id` if AI can determine the right job, or unlinked if it can't
- User reviews the splits before they execute

**6c. Content Dedup (standard 3-stage)**
- After splitting, remaining summaries go through the normal auto-merge / review / delete flow
- Junk stage catches entries that are entirely bullet content (no real summary to extract)
- Target: a small set of polished summaries (5-15), each tied to a meaningful role_type

### 7. Languages

- Standard 3-stage flow
- If no entries exist, auto-skip: "Languages: No entries found — nothing to clean"
- When populated (after future imports), dedup by language name similarity

### 8. References

- Standard 3-stage flow
- If no entries exist, auto-skip: "References: No entries found — nothing to clean"
- When populated, dedup by name + company + relationship similarity

---

## Backend Architecture

### API Endpoints

**Scan endpoint:**
```
POST /api/kb/dedup/scan
Body: { entity_type: "career_history" | "bullets" | "skills" | ... }
Response: {
  auto_merge: [ { group_id, winner_id, members: [...], reason } ],
  needs_review: [ { group_id, members: [...], similarity_score, reason } ],
  junk: [ { id, content_preview, reason, suggested_reclassify?: { target_table, career_history_id? } } ]
}
```

**Apply endpoint:**
```
POST /api/kb/dedup/apply
Body: {
  entity_type: "career_history",
  merges: [ { winner_id, loser_ids: [...] } ],
  deletes: [ id, id, ... ],
  reclassifications: [ { id, target_table, career_history_id? } ]
}
Response: { merged: N, deleted: N, reclassified: N, errors: [] }
```

**Summary-specific endpoints:**
```
POST /api/kb/dedup/summaries/role-types
Body: { reassignments: { old_role_type: new_role_type, ... } }

POST /api/kb/dedup/summaries/split
Body: { splits: [ { id, keep_summary_text: "...", extract_bullets: ["...", "..."], career_history_id? } ] }
```

### AI Integration

- Backend builds prompts per entity type with the full list of entries
- For large sets (bullets at 890+), batch into chunks to stay within context limits
- AI returns merge groups with confidence scores:
  - High confidence (>0.85) → auto_merge bucket
  - Medium confidence (0.5-0.85) → needs_review bucket
  - Flagged as junk/misclassified → junk bucket
- Uses the existing AI provider infrastructure (Claude via CLI adapter)
- Summary splitting gets a dedicated prompt: "separate the summary content from the bullet content in this text"

### Merge Execution

- All merges within a confirmation step execute in a single DB transaction
- Foreign keys repointed before deleting the losing record
- Reclassified items inserted into target table before removing from source table
- On error: transaction rolls back, user sees error message, can retry

---

## Frontend Components

### New Components

- `KbDedupWizard.tsx` — full-screen modal, wizard state machine, progress bar
- `DedupStepAutoMerge.tsx` — Stage 1: green auto-merge confirmation list
- `DedupStepReview.tsx` — Stage 2: yellow side-by-side review cards with diff highlighting
- `DedupStepJunk.tsx` — Stage 3: red junk/delete/reclassify list
- `SummaryRoleTypeEditor.tsx` — Summary-specific role_type reassignment UI
- `SummarySplitReview.tsx` — Summary-specific content split review UI
- `AiToggle.tsx` — reusable AI on/off toggle switch (shared across KB pages)

### Modified Components

- `KnowledgeBase.tsx` — add AI toggle + "Clean Up Knowledge Base" button to header

### State Management

- Wizard state managed locally in `KbDedupWizard.tsx` (not global state)
- Current entity step, current sub-stage, scan results, user decisions all in component state
- Each step fetches scan results on mount via `/api/kb/dedup/scan`
- Confirmed actions posted to `/api/kb/dedup/apply` before advancing to next step

---

## Data Safety

- No data is deleted or modified until the user explicitly confirms at each stage
- Each confirmation step executes in a DB transaction (atomic rollback on error)
- The wizard is interruptible... confirmed steps are committed, unconfirmed work is discarded on cancel
- Existing MergeDuplicatesModal.tsx in Bullets page remains functional (this wizard is a superset, not a replacement... we may deprecate the old modal later)
