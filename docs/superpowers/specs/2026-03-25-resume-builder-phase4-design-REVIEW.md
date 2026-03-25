# Design Review: Resume Builder Phase 4
**Reviewer:** Claude Opus 4.6 | **Date:** 2026-03-25 | **Verdict:** Good spec, 3 critical gaps to fix before build

---

## What's Done Well

- API contracts for all 4 AI endpoints are complete with input/output JSON shapes
- Python fallback logic for every endpoint is concrete and implementable
- Build order is logical (parser foundations first, AI features in value order, E2E last)
- Proper use of existing `route_inference` pattern throughout
- ResumeEditor.tsx already has `onAiReview` and `onAtsScore` stubs at lines 136-137, confirming the wiring points exist

---

## Critical Issues (Must Fix)

### C1: Thumbnail generation will not work in Docker

Section 6 proposes `docx2pdf` or `libreoffice --convert-to pdf` plus `pdf2image` (poppler). Neither `docx2pdf`, `libreoffice`, nor `poppler` are in `requirements.txt`, and more importantly, the Flask backend runs **inside a Docker container** (not native Windows). Installing LibreOffice in a Python Docker image bloats it by 500MB+ and is fragile. `docx2pdf` requires Microsoft Word installed (Windows COM automation) which is unavailable in Docker.

**Recommendation:** Either (a) run thumbnail generation as a **local_code Python script** outside Docker on the Windows host where Word/LibreOffice is available, or (b) use a pure-Python approach like rendering a simplified HTML preview from the template_map JSON (no .docx-to-image needed). Option (b) is more portable and avoids the dependency entirely. The spec should pick one and document it.

### C2: Migration number collision

The spec calls for `031_template_thumbnails.sql` adding a `thumbnail BYTEA` column. But migration `030_resume_builder.sql` already added `preview_blob BYTEA` to `resume_templates`. These appear to serve the same purpose. The spec should either reuse `preview_blob` (rename if needed) or explain how `thumbnail` differs from `preview_blob`.

### C3: ATS Score endpoint missing `suggestions` field contract

Section 4 says the output is "same shape as existing ATS scorer" and lists fields: `ats_score`, `keyword_matches`, `match_percentage`, `formatting_flags`, `suggestions`. But the existing ATS scorer in `resume_tailoring.py` returns `keyword_matches`, `match_percentage`, `formatting_flags`, `ats_score` -- there is no `suggestions` field in the Python fallback. Either add `suggestions` to the Python fallback or document that it only appears in the AI-enhanced response.

---

## Important Issues (Should Fix)

### I1: No error handling spec for AI endpoint failures

All four AI endpoints use `route_inference`, but the spec never describes what happens when Claude is unavailable or returns malformed JSON. The existing pattern falls back to Python, but the frontend components (AiReviewPanel, AiGenerateModal, BestPicksPanel) need to know: Do they show degraded results? A warning banner? The `analysis_mode` field in responses handles this partially, but the frontend sections don't mention it.

### I2: Best-Picks "Smart Fill" is underspecified

Section 3 mentions a "Smart Fill" button that "auto-populate[s] an empty recipe from best picks (creates full recipe draft)." This is a major feature buried in one sentence. It needs: Which recipe fields get populated? Does it create a new recipe or modify the current one? What template does it use? What happens if the recipe already has content?

### I3: `target_roles` source is ambiguous

Section 1 says target roles are "pulled from `settings.preferences.target_roles`." The codebase shows `target_roles` are queried from the DB in `linkedin.py` via `db.query(...)`, not from `settings.preferences`. The spec should clarify the exact table/query. If it's a JSON field inside `settings.preferences`, show the access pattern.

### I4: Section 5 parser has no fallback for non-.docx formats

The parser spec (Section 5) only handles `.docx`. But the onboard route already handles `.pdf` uploads (line 259: "Can't templatize without docx, so we'll skip those steps"). The spec should explicitly state that PDF-uploaded resumes skip the templatize pipeline, or describe a PDF-to-sections parser path.

### I5: Frontend file paths assume flat directory structure

The new file inventory puts `AiReviewPanel.tsx`, `AiGenerateModal.tsx`, etc. inside `pages/resume-builder/`. Verify that the existing 14 components follow this same convention. If some live in a `components/` subdirectory, the spec should match.

---

## Suggestions (Nice to Have)

### S1: Add rate limiting / debounce for AI endpoints

AI Review and ATS Score have "Refresh" / "Re-score" buttons. Without debounce, a user could spam Claude API calls. Consider a minimum interval (e.g., 5 seconds) or a loading state that disables the button.

### S2: Voice check integration for Generate-Slot

Section 2 says "All generated content must pass `check_voice` before returning to frontend." Good. But the other AI endpoints (Review, Best-Picks) also generate text in their suggestions. Should those also pass voice check?

### S3: E2E test should capture timing metrics

The E2E output table (Section 7) captures match percentages but not parse/generate duration. Adding timing would help identify slow templates and set performance baselines.

### S4: Consider caching Best-Picks results

If the same JD is scored against the same bullet set, the results won't change. A short-lived cache (keyed on JD hash + recipe ID) could avoid redundant AI calls.

---

## Dependency Checklist

| Dependency | Status | Action Needed |
|-----------|--------|---------------|
| `route_inference` pattern | Exists at `ai_providers/router.py:18` | None |
| `templatize_resume.py` | Exists, imported by onboard.py | Refactor per spec |
| `resume_tailoring.py` ATS scorer | Exists with matching shape | Add `suggestions` field or clarify |
| `ResumeEditor.tsx` stubs | `onAiReview`, `onAtsScore` stubs at L136-137 | Wire up; add `onBestPicks`, `onGenerateSlot` |
| `preview_blob` column | Already in 030_resume_builder.sql | Reconcile with proposed `thumbnail` column |
| `docx2pdf` / `pdf2image` / `poppler` | **NOT in requirements.txt** | Must add or choose alternative approach |
| `resume_parser.py` | Does not exist yet | Create per spec |
| `template_builder.py` | Does not exist yet | Create per spec |

---

## Build Order Assessment

The proposed build order is sound. One adjustment: move step 7 (ATS Score in Builder) to position 4 instead of 7. It reuses existing logic and is the simplest endpoint to wire. Getting it working early proves the `route_inference` integration pattern before tackling the harder AI endpoints. Revised order:

1. General-purpose parser (foundation)
2. Template thumbnails (migration + route)
3. Template browser (frontend)
4. **ATS Score in Builder** (simplest AI endpoint, proves the pattern)
5. AI Review endpoint + panel
6. AI Generate-Slot endpoint + modal
7. Best-Picks endpoint + panel
8. E2E testing script
9. Run E2E against all originals
