# Backend API / MCP Route Audit — 2026-04-15

## Scope

Full audit of backend routes, MCP tools, and frontend API calls to identify dead code, missing wiring, duplicated logic, and consistency issues.

## Inventory

| Layer | Count | Source |
|-------|-------|--------|
| Backend route blueprints | 42 files | `code/backend/routes/` |
| Backend API endpoints | ~494 routes | `@bp.route()` decorators |
| MCP tool files | 23 files | `code/backend/mcp_tools_*.py` |
| MCP tools registered | ~138 tools | `@mcp.tool()` + `register_*()` |
| Frontend API exports | 59 functions | `frontend/src/api/client.ts` |
| Frontend pages | 18 directories | `frontend/src/pages/` |

---

## Finding 1: Routes and MCP Tools Are Fully Independent

**Status:** By design, not a bug.

Both backend routes (serving the React UI) and MCP tools (serving AI agents) make direct `db.query()` calls. Zero MCP tools call Flask routes. Zero routes call MCP tools. There are only 3 files in `backend/services/` (`bls_fetcher.py`, `calendar_intelligence.py`, `email_intelligence.py`).

**Impact:** Logic changes must be made in both places. A query fix in `routes/pipeline.py` doesn't propagate to `mcp_tools_pipeline.py`.

**Recommendation:** Accept for now. Shared service extraction is a large refactoring effort better suited as a dedicated workstream. The `services/` directory provides the pattern if/when needed.

---

## Finding 2: Unused Typed API Exports in client.ts

Three API object exports in `client.ts` are defined but **never imported by any component**. The corresponding pages use raw `api.get()`/`api.post()` calls instead:

| client.ts export | Page that should use it | What page does instead |
|------------------|------------------------|----------------------|
| `companies` (line 214) | `pages/settings/Companies.tsx` | `api.get<Company[]>('/companies?limit=100')` |
| `mockInterviews` (line 435) | `pages/mock-interviews/MockInterviews.tsx` | `api.get('/mock-interviews')`, `api.post(...)`, `api.patch(...)` |
| `marketIntel` (line 492) | `pages/market/MarketIntel.tsx` | `api.get('/market-intelligence...')` |

**Impact:** Low. Everything works. The duplication means URL changes need updating in two places (client.ts export + inline page call).

**Options:**
- **A) Delete unused exports** — pages work fine with inline calls. Reduces dead code.
- **B) Refactor pages to import typed exports** — better consistency, single source of URL patterns.

**Recommendation:** Option A (delete) for now. These exports have `any` types anyway, so they don't provide much type safety benefit. If/when these pages get proper typing, recreate the exports with real types.

---

## Finding 3: Direct `fetch()` Bypasses in Page Components

9 places use `fetch()` directly instead of the `api.*` client:

### Legitimate bypasses (FormData / binary):
| File | URL | Reason |
|------|-----|--------|
| `ImportResumesModal.tsx:101` | `${API_BASE}/onboard/upload` | FormData upload |
| `Contacts.tsx:497` | `${API_BASE}/contacts/import/csv` | FormData upload |
| `LinkedInHub.tsx:1166` | `${API_BASE}/import/linkedin-zip` | FormData upload |
| `ResumeEditor.tsx:121` | `${base}/resume/recipes/${id}/generate` | Binary .docx download |
| `Resumes.tsx:144` | `${BASE}/resume/recipes/${id}/generate` | Binary .docx download |
| `TemplatePicker.tsx:23` | `templateThumbnailUrl(id)` | Image fetch (uses helper) |
| `templates.upload` (client.ts:259) | `${BASE}/resume/templates/upload` | FormData in typed export |

### Should be centralized in client.ts:
| File | URL | Fix |
|------|-----|-----|
| `JobCard.tsx:196` | `${API_BASE}/career-history/${id}/with-options` | Add to `careerHistory` export |
| `JobList.tsx:248` | `${API_BASE}/company/${employer}` | Add to `companies` export |
| `MergeDuplicatesModal.tsx:238` | `api.post('/career-history/merge-companies', ...)` | Uses raw api (low-priority) |

**Impact:** Low. All bypasses use `API_BASE` correctly (the ImportResumesModal fix from last session).

**Recommendation:** Add career-history and company endpoints to client.ts typed exports when touching those files next.

---

## Finding 4: Route File / MCP Tool Coverage Matrix

### Route files WITH MCP tool equivalent (23 pairs):
aging, campaign, contacts, crm, fresh_jobs, knowledge, linkedin, market_intelligence, materials, mock_interviews, notifications, offers, onboard, pipeline (covers applications + saved_jobs + gap_analysis), references, reporting, resume (covered by resume_gen), resume_tailoring, search (covered by search_intel), skills_development, workflows, networking (covers path_finding + linkedin_import), google (covers google_oauth)

### Route files WITHOUT MCP equivalent (19):
`activity`, `analytics`, `batch`, `bullet_ops`, `calendar_intelligence`, `career`, `content`, `email_intelligence`, `integrations`, `interview_extras`, `jd_fetch`, `kb_dedup`, `market_intelligence_fetch`, `profile`, `saved_jobs` (covered by pipeline MCP), `search`, `settings`

**Impact:** None. These routes serve the frontend UI. MCP tools are for AI agent workflows. Not every UI endpoint needs an MCP equivalent.

---

## Finding 5: Frontend Pages vs Backend Route Coverage

All 18 frontend page directories have corresponding backend routes:

| Frontend Page | Backend Route(s) |
|--------------|-----------------|
| analytics | analytics.py, reporting.py |
| applications | pipeline.py, aging.py |
| bullets | career.py, bullet_ops.py, knowledge.py |
| contacts | contacts.py, crm.py |
| dashboard | analytics.py, pipeline.py (aggregates) |
| fresh-jobs | fresh_jobs.py |
| interviews | interview_extras.py |
| jobs | saved_jobs.py |
| knowledge-base | knowledge.py, onboard.py, kb_dedup.py |
| linkedin | linkedin.py, linkedin_import.py |
| market | market_intelligence.py, market_intelligence_fetch.py |
| mock-interviews | mock_interviews.py |
| networking | crm.py, path_finding.py |
| notifications | notifications.py |
| profile | profile.py, career.py |
| resume-builder | resume.py, resume_tailoring.py |
| resumes | resume.py |
| settings | settings.py, integrations.py, google_oauth.py |

**No missing wiring detected.** Every frontend page has working backend routes.

---

## Finding 6: All 42 Blueprints Properly Registered

`routes/__init__.py` lists all 42 blueprints in `ALL_BLUEPRINTS`. No orphaned files. No unregistered routes. Route file count matches blueprint import count exactly.

---

## Summary of Actionable Items

### Do Now (low effort):
- [x] Audit complete, report written

### Do When Touching These Files:
- [ ] Delete or wire up `companies`, `mockInterviews`, `marketIntel` exports in client.ts
- [ ] Add `careerHistory.getWithOptions()` and `companies.getByEmployer()` to client.ts
- [ ] Standardize ResumeEditor.tsx and Resumes.tsx generate calls (both use `fetch()` with slightly different base URL variables)

### Future Workstream (if maintenance burden grows):
- [ ] Extract shared services for the highest-duplication domains (pipeline, knowledge, resume) so route + MCP changes propagate automatically
- [ ] Add proper TypeScript types to the `any`-typed exports (mockInterviews, freshJobs, notifications, etc.)

---

## Architecture Decision Record

**Decision:** Routes and MCP tools will continue to operate independently with direct DB access. No shared service layer refactoring at this time.

**Rationale:** The platform is single-user, locally hosted. The duplication between routes and MCP tools is manageable. A shared service layer would add complexity without proportional benefit until the codebase grows further or a second developer joins. The nascent `services/` directory (3 files) provides the pattern when ready.

**Revisit when:** Bug fixes start needing parallel changes in both route and MCP files regularly, or when preparing for open-source/multi-user deployment.
