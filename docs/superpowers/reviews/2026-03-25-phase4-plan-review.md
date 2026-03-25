# Phase 4 Plan Review -- 2026-03-25

**Reviewer:** Code Review Agent
**Plan:** `code/docs/superpowers/plans/2026-03-25-resume-builder-phase4.md`
**Spec:** `code/docs/superpowers/specs/2026-03-25-resume-builder-phase4-design.md`

---

## Verdict: GOOD with 5 issues to fix before build

The plan is thorough, well-structured (12 tasks, ~45 steps), and covers all 10 spec sections. Build order is correct. The code follows existing patterns (route_inference, Flask Blueprint, React Query). Five issues need attention before handing to a coding agent.

---

## 1. Spec Coverage -- PASS

All 10 spec sections map to plan tasks:

| Spec Section | Plan Task(s) | Covered? |
|---|---|---|
| 1. AI Review Endpoint | Task 5 | Yes |
| 2. AI Generate-Slot | Task 6 | Yes |
| 3. Best-Picks | Task 7 | Yes |
| 4. ATS Score in Builder | Task 4 | Yes |
| 5. General-Purpose Parser | Tasks 1-2 | Yes |
| 6. Template Browser | Task 8 | Yes |
| 7. E2E Testing | Tasks 11-12 | Yes |
| 8. DB Changes | Task 3 | Yes |
| 9. File Inventory | File Structure table | Yes |
| 10. Build Order | Task ordering | Yes |

---

## 2. Issues Found

### CRITICAL: File path inconsistency between spec and plan

The spec lists new backend files under `backend/utils/` (e.g., `backend/utils/resume_parser.py`), but the plan creates them at `code/utils/resume_parser.py`. The existing `templatize_resume.py` and `generate_resume.py` already live at `code/utils/`, NOT `code/backend/utils/`. The plan is correct; the spec's file inventory (Section 9) has wrong paths for the two new utility files. The `code/backend/` directory holds routes and ai_providers, not utils.

**Action:** Update spec Section 9 "New Files" to use `utils/resume_parser.py` and `utils/template_builder.py` (no `backend/` prefix). The plan already has this right.

### CRITICAL: Thumbnail runs in Docker but spec says "Windows host"

The spec says thumbnail generation "runs on Windows host, not in Docker," but the plan adds the thumbnail endpoint to `backend/routes/resume.py` which runs inside the Docker container. The Pillow-based fallback (structural preview, no real docx rendering) works fine in Docker, but the `docx2pdf` COM-based path and `wkhtmltoimage` path will NOT work in the Linux container.

**Action:** The plan's approach (Pillow structural thumbnail inside Docker) is the pragmatic choice. Update the spec to remove the "runs on Windows host" language and acknowledge the endpoint runs in Docker with the pure-Python fallback. If high-fidelity thumbnails are needed later, add a separate `local_code/` script.

### IMPORTANT: Plan adds 3 test files not in spec

The plan creates `code/tests/test_resume_parser.py`, `code/tests/test_template_builder.py`, and `code/tests/test_ai_endpoints.py`. These are not in the spec's file inventory. This is a beneficial deviation (more tests is good), but the spec should be updated to match.

**Action:** Add the 3 test files to spec Section 9.

### IMPORTANT: Plan adds `ai_providers/base.py` and `claude_provider.py` modifications not in spec

The plan's modified files table lists changes to `code/backend/ai_providers/base.py` and `code/backend/ai_providers/claude_provider.py` for new abstract methods (review, generate-slot, best-picks). The spec's modified files list (Section 9) omits these. Since all 4 AI endpoints need AI handler methods, this is a real gap in the spec.

**Action:** Add both files to spec Section 9 modified files list. Also add `code/frontend/src/api/client.ts` which the spec also omits but the plan correctly includes.

### SUGGESTION: E2E test against ~90 .docx files may timeout or overwhelm

The docx file count across Imports/Archived/Originals is substantial. Each file goes through upload + parse + templatize + generate + compare. With the general-purpose parser doing paragraph-by-paragraph analysis, this could be slow.

**Action:** The plan already handles this well (Task 11 Step 2 says "test with single resume first," Task 12 triages by priority: V32/V31/BEST first). No change needed, but consider adding a `--limit N` flag to the E2E script for faster iteration.

---

## 3. Build Order -- PASS

Dependencies are correctly ordered:
- Parser (T1) + Builder (T2) before everything else (foundation)
- Migration (T3) before Template Browser (T8) (needs parser_version column)
- ATS Score (T4) before AI endpoints (T5-7) (proves route_inference wiring pattern first)
- E2E script (T11) after all features built, final validation (T12) last

No circular dependencies. No missing prerequisites.

---

## 4. Test Commands -- PASS with caveat

- `cd code && python -m pytest tests/test_resume_parser.py -v` -- correct, matches existing test structure
- `cd code && docker compose up -d --build backend frontend` -- correct rebuild pattern
- `curl` commands for endpoint testing -- these are blocked by context-mode hook; the plan should use `python -c "import requests; ..."` or the E2E script instead. Minor issue since the coding agent will adapt.

---

## 5. Existing Pattern Conformance -- PASS

- **route_inference:** Plan uses the exact `route_inference(task, context, python_fallback, ai_handler)` pattern visible at line 18 of the existing module.
- **Flask Blueprint:** `@bp.route(...)` pattern matches existing `resume.py`.
- **React Query:** Plan uses `useQuery`/`useMutation` with `@tanstack/react-query`, matching `BulletBrowser.tsx` and `Applications.tsx` patterns.
- **API client:** Plan adds functions to `client.ts` using the existing `api.get<T>()` / `fetch` patterns.
- **Phase 4 stubs:** Lines 136-137 of `ResumeEditor.tsx` have `onAiReview={() => {/* Phase 4 */}}` and `onAtsScore={() => {/* Phase 4 */}}` -- plan correctly wires these.
- **Migration pattern:** Uses existing `DO $$ BEGIN ... END $$` idempotent pattern from migration 030.

---

## 6. Missing Imports / Undefined References -- PASS

Checked all plan code blocks:
- `resume_parser.py` imports: `re`, `pathlib.Path`, `docx.Document`, `docx.shared.Pt` -- all available in the Docker container (python-docx is already a dependency).
- `template_builder.py`: imports `resume_parser.parse_resume_structure` -- created in Task 1 before Task 2 uses it.
- `PIL.Image` for thumbnails -- Pillow needs to be added to `requirements.txt`. The plan does not explicitly mention this.

**Action:** Add a step to Task 3 to add `Pillow` to `code/backend/requirements.txt` (or wherever the Docker image's pip dependencies are listed).

---

## 7. Task Size Assessment -- PASS

No tasks need splitting. Largest tasks:
- Task 1 (Parser): 6 steps, well-scoped (one file + tests)
- Task 2 (Template Builder): 5 steps, well-scoped (one file + tests)
- Task 8 (Template Browser): 4 steps, manageable (2 new components + tab integration)

All tasks are single-session sized for a coding agent.

---

## Summary of Required Actions

| # | Severity | Action |
|---|----------|--------|
| 1 | CRITICAL | Fix spec Section 9: utility file paths should be `utils/` not `backend/utils/` |
| 2 | CRITICAL | Fix spec Section 6: thumbnail runs in Docker with Pillow fallback, not on Windows host |
| 3 | IMPORTANT | Add 3 test files to spec Section 9 |
| 4 | IMPORTANT | Add `ai_providers/base.py`, `claude_provider.py`, `api/client.ts` to spec Section 9 modified files |
| 5 | SUGGESTION | Add `Pillow` to Docker requirements.txt in Task 3 |
| 6 | SUGGESTION | Add `--limit N` flag to E2E script for faster iteration |
