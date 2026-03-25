# Bullet Browser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-panel career content manager (Bullet Browser) with job editing, synopsis variants, bullet CRUD, AI analysis, and duplicate detection.

**Architecture:** Two-panel React page. Left panel: job list with expand/edit. Right panel: synopsis editor + bullet list with AI toolbar. Backend: Flask endpoints for new operations + DB migration for new columns. AI features use the existing Claude provider via the AI router.

**Tech Stack:** React + TypeScript + React Query + Tailwind (frontend), Flask + PostgreSQL (backend), pytest (tests)

**Spec:** `docs/superpowers/specs/2026-03-24-bullet-browser-design.md`

---

## File Structure

### Backend
- Create: `db/migrations/029_bullet_browser.sql` — schema additions
- Modify: `backend/routes/career.py` — add career_history_id filter to GET bullets, update PATCH career-history for new fields
- Create: `backend/routes/bullet_ops.py` — new blueprint for clone, reorder, duplicates, stale-count, AI operations
- Modify: `backend/app.py` — register new blueprint

### Frontend
- Create: `frontend/src/pages/bullets/BulletBrowser.tsx` — main two-panel page
- Create: `frontend/src/pages/bullets/JobList.tsx` — left panel job list
- Create: `frontend/src/pages/bullets/JobCard.tsx` — single job expand/edit
- Create: `frontend/src/pages/bullets/SmartDateInput.tsx` — date text input + parser
- Create: `frontend/src/pages/bullets/SynopsisEditor.tsx` — synopsis variant tabs + editor
- Create: `frontend/src/pages/bullets/BulletList.tsx` — bullet toolbar + card list
- Create: `frontend/src/pages/bullets/BulletCard.tsx` — single bullet view/edit
- Create: `frontend/src/pages/bullets/AiToolbar.tsx` — AI toggle + analyze all + progress
- Create: `frontend/src/pages/bullets/AiInstructionModal.tsx` — instruction field popup
- Create: `frontend/src/pages/bullets/DuplicateWarning.tsx` — caution popup on save
- Modify: `frontend/src/App.tsx` — add /bullets route
- Modify: `frontend/src/api/client.ts` — add bullet ops types

### Tests
- Create: `tests/test_bullet_browser.py` — backend endpoint tests

---

## Task 1: Database Migration

**Files:**
- Create: `code/db/migrations/029_bullet_browser.sql`

- [ ] **Step 1: Write migration SQL**

```sql
-- 029_bullet_browser.sql — Bullet Browser schema additions

-- Bullets table additions
ALTER TABLE bullets
  ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS ai_analysis JSONB,
  ADD COLUMN IF NOT EXISTS ai_analyzed_at TIMESTAMP,
  ADD COLUMN IF NOT EXISTS content_hash TEXT,
  ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Career history additions
ALTER TABLE career_history
  ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS start_date_raw TEXT,
  ADD COLUMN IF NOT EXISTS end_date_raw TEXT,
  ADD COLUMN IF NOT EXISTS start_date_iso DATE,
  ADD COLUMN IF NOT EXISTS end_date_iso DATE;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_bullets_content_hash ON bullets (content_hash);
CREATE INDEX IF NOT EXISTS idx_bullets_display_order ON bullets (career_history_id, display_order);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bullets_one_default_synopsis
  ON bullets (career_history_id)
  WHERE type = 'synopsis' AND is_default = TRUE;

-- Auto-update trigger for content_hash and updated_at
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

-- Backfill
UPDATE bullets SET content_hash = md5(text) WHERE content_hash IS NULL AND text IS NOT NULL;
UPDATE bullets SET updated_at = created_at WHERE updated_at IS NULL;

UPDATE career_history SET
  start_date_raw = COALESCE(start_date::text, ''),
  start_date_iso = start_date,
  end_date_raw = CASE WHEN end_date IS NULL THEN 'Present' ELSE end_date::text END,
  end_date_iso = end_date
WHERE start_date_raw IS NULL;
```

- [ ] **Step 2: Run migration**

```bash
PGPASSWORD=WUHD8fBisb57FS4Q3bdvfuvgnim9fL1c psql -h localhost -p 5555 -U supertroopers -d supertroopers -f code/db/migrations/029_bullet_browser.sql
```

Expected: ALTER TABLE, CREATE INDEX, CREATE FUNCTION, UPDATE statements succeed.

- [ ] **Step 3: Verify columns exist**

```bash
PGPASSWORD=WUHD8fBisb57FS4Q3bdvfuvgnim9fL1c psql -h localhost -p 5555 -U supertroopers -d supertroopers -c "\d bullets" | grep -E "display_order|ai_analysis|content_hash|is_default|updated_at"
```

Expected: All 6 new columns shown.

- [ ] **Step 4: Commit**

```bash
git add code/db/migrations/029_bullet_browser.sql
git commit -m "feat(db): migration 029 — bullet browser schema additions"
```

---

## Task 2: Backend — Update Existing Endpoints

**Files:**
- Modify: `code/backend/routes/career.py`

- [ ] **Step 1: Add `career_history_id` and `type` filters to GET /api/bullets**

In the `list_bullets()` function, add parameter handling:

```python
career_history_id = request.args.get("career_history_id", type=int)
if career_history_id:
    clauses.append("b.career_history_id = %s")
    params.append(career_history_id)

bullet_type = request.args.get("type")
if bullet_type:
    if bullet_type.startswith("!"):
        clauses.append("b.type != %s")
        params.append(bullet_type[1:])
    else:
        clauses.append("b.type = %s")
        params.append(bullet_type)
```

Also add `ORDER BY b.display_order, b.created_at` to the query.

SynopsisEditor uses `?career_history_id={id}&type=synopsis`. BulletList uses `?career_history_id={id}&type=!synopsis`.

- [ ] **Step 2: Update PATCH /api/career-history/{id} to handle new columns**

Add the new fields to the allowed update list: `metadata`, `start_date_raw`, `end_date_raw`, `start_date_iso`, `end_date_iso`. For JSONB metadata, use `%s::jsonb` in the SQL.

- [ ] **Step 3: Test endpoints manually**

```bash
# Test career_history_id filter
curl -s "http://localhost:8055/api/bullets?career_history_id=1&limit=5" | python -m json.tool | head -20

# Test career history PATCH with new fields
curl -s -X PATCH "http://localhost:8055/api/career-history/1" \
  -H "Content-Type: application/json" \
  -d '{"metadata": {"department": "Engineering"}, "start_date_raw": "Jan 2024", "start_date_iso": "2024-01-01"}'
```

- [ ] **Step 4: Commit**

```bash
git add code/backend/routes/career.py
git commit -m "feat(api): update career endpoints for bullet browser"
```

---

## Task 3: Backend — New Bullet Operations Blueprint

**Files:**
- Create: `code/backend/routes/bullet_ops.py`
- Modify: `code/backend/app.py` — register blueprint

- [ ] **Step 1: Create bullet_ops.py with clone, reorder, stale-count, check-duplicates**

```python
"""Routes for bullet browser operations: clone, reorder, duplicates, AI."""

import hashlib
from difflib import SequenceMatcher
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("bullet_ops", __name__)


@bp.route("/api/bullets/<int:bullet_id>/clone", methods=["POST"])
def clone_bullet(bullet_id):
    """Clone a bullet (copy with new ID, same job)."""
    original = db.query_one("SELECT * FROM bullets WHERE id = %s", (bullet_id,))
    if not original:
        return jsonify({"error": "Not found"}), 404

    clone = db.execute_returning(
        """
        INSERT INTO bullets (career_history_id, text, type, tags, role_suitability,
                             industry_suitability, star_situation, star_task, star_action,
                             star_result, metrics_json, detail_recall, display_order)
        SELECT career_history_id, text, type, tags, role_suitability,
               industry_suitability, star_situation, star_task, star_action,
               star_result, metrics_json, detail_recall,
               COALESCE((SELECT MAX(display_order) + 1 FROM bullets WHERE career_history_id = %s), 0)
        FROM bullets WHERE id = %s
        RETURNING id, career_history_id, text, type, tags, display_order
        """,
        (original["career_history_id"], bullet_id),
    )
    return jsonify(clone), 201


@bp.route("/api/bullets/reorder", methods=["POST"])
def reorder_bullets():
    """Update display_order for drag-drop. Body: {career_history_id, items: [{id, order}]}"""
    data = request.get_json(force=True)
    career_history_id = data.get("career_history_id")
    items = data.get("items", [])
    if not career_history_id or not items:
        return jsonify({"error": "career_history_id and items required"}), 400

    for item in items:
        db.execute(
            "UPDATE bullets SET display_order = %s WHERE id = %s AND career_history_id = %s",
            (item["order"], item["id"], career_history_id),
        )
    return jsonify({"updated": len(items)}), 200


@bp.route("/api/bullets/stale-count", methods=["GET"])
def stale_count():
    """Count bullets needing re-analysis."""
    career_history_id = request.args.get("career_history_id", type=int)
    clauses = ["ai_analysis IS NOT NULL"]
    params = []

    if career_history_id:
        clauses.append("career_history_id = %s")
        params.append(career_history_id)

    # Stale = content_hash differs from hash stored in ai_analysis
    total = db.query_one(
        f"""
        SELECT COUNT(*) as count FROM bullets
        WHERE {' AND '.join(clauses)}
          AND content_hash != (ai_analysis->>'content_hash_at_analysis')
        """,
        params,
    )
    # Also count never-analyzed bullets
    never = db.query_one(
        f"""
        SELECT COUNT(*) as count FROM bullets
        WHERE ai_analysis IS NULL AND text IS NOT NULL
          {'AND career_history_id = %s' if career_history_id else ''}
        """,
        params if career_history_id else [],
    )
    return jsonify({
        "stale": total["count"] if total else 0,
        "never_analyzed": never["count"] if never else 0,
    })


@bp.route("/api/bullets/<int:bullet_id>/check-duplicates", methods=["POST"])
def check_duplicates(bullet_id):
    """Check for duplicate/similar bullets within-job and cross-job.
    Body (optional): {ai_enabled: bool} — when true, uses AI for semantic similarity.
    """
    bullet = db.query_one("SELECT * FROM bullets WHERE id = %s", (bullet_id,))
    if not bullet:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(silent=True) or {}
    ai_enabled = data.get("ai_enabled", False)
    text = bullet["text"]
    career_history_id = bullet["career_history_id"]

    # Get all other bullets
    all_bullets = db.query(
        """
        SELECT b.id, b.text, b.career_history_id, ch.employer, ch.title
        FROM bullets b
        LEFT JOIN career_history ch ON b.career_history_id = ch.id
        WHERE b.id != %s AND b.text IS NOT NULL AND b.type != 'synopsis'
        """,
        (bullet_id,),
    )

    within_job = []
    cross_job = []

    # Tier 1: fuzzy matching (always runs)
    for other in all_bullets:
        ratio = SequenceMatcher(None, text.lower(), other["text"].lower()).ratio()
        if ratio < 0.7:
            continue

        match = {
            "id": other["id"],
            "text": other["text"][:120] + ("..." if len(other["text"]) > 120 else ""),
            "similarity": round(ratio, 2),
            "employer": other["employer"],
            "title": other["title"],
            "match_type": "fuzzy",
        }
        if other["career_history_id"] == career_history_id:
            within_job.append(match)
        else:
            cross_job.append(match)

    # Tier 2: AI semantic similarity (when enabled)
    if ai_enabled and (within_job or cross_job):
        candidates = within_job[:3] + cross_job[:5]
        candidate_texts = [f"- [{c['id']}] {c['text']}" for c in candidates]
        prompt = f"""Compare this bullet to the candidates below. For each, rate semantic similarity 0-100 and explain briefly.
Bullet: "{text}"
Candidates:
{chr(10).join(candidate_texts)}
Return JSON array: [{{"id": N, "similarity": 0-100, "reason": "..."}}]"""
        ai_result = route_ai_request(prompt, response_format="json")
        if ai_result:
            try:
                ai_matches = json.loads(ai_result) if isinstance(ai_result, str) else ai_result
                ai_map = {m["id"]: m for m in ai_matches}
                for lst in [within_job, cross_job]:
                    for match in lst:
                        if match["id"] in ai_map:
                            match["ai_similarity"] = ai_map[match["id"]].get("similarity")
                            match["ai_reason"] = ai_map[match["id"]].get("reason")
                            match["match_type"] = "ai"
            except (json.JSONDecodeError, TypeError):
                pass  # Fall back to fuzzy-only results

    within_job.sort(key=lambda x: x.get("ai_similarity", x["similarity"]), reverse=True)
    cross_job.sort(key=lambda x: x.get("ai_similarity", x["similarity"]), reverse=True)

    return jsonify({
        "within_job": within_job[:5],
        "cross_job": cross_job[:10],
        "has_duplicates": len(within_job) + len(cross_job) > 0,
    })
```

- [ ] **Step 2: Register blueprint in app.py**

Find the blueprint registration section in `code/backend/app.py` and add:

```python
from routes.bullet_ops import bp as bullet_ops_bp
app.register_blueprint(bullet_ops_bp)
```

- [ ] **Step 3: Test endpoints**

```bash
# Test clone
curl -s -X POST "http://localhost:8055/api/bullets/1/clone" | python -m json.tool

# Test stale count
curl -s "http://localhost:8055/api/bullets/stale-count" | python -m json.tool

# Test duplicate check
curl -s -X POST "http://localhost:8055/api/bullets/1/check-duplicates" | python -m json.tool
```

- [ ] **Step 4: Commit**

```bash
git add code/backend/routes/bullet_ops.py code/backend/app.py
git commit -m "feat(api): bullet ops — clone, reorder, stale-count, duplicate check"
```

---

## Task 4: Backend — AI Endpoints

**Files:**
- Modify: `code/backend/routes/bullet_ops.py` — add AI endpoints

- [ ] **Step 1: Add analyze, generate, wordsmith, variant endpoints**

Add to `bullet_ops.py`:

```python
import json
import time
from flask import Response, stream_with_context
from routes.ai_router import route_ai_request  # existing AI router


def _analyze_single_bullet(bullet_id):
    """Service function: analyze one bullet. Returns (analysis_dict, error_str)."""
    bullet = db.query_one(
        "SELECT b.*, ch.employer, ch.title FROM bullets b "
        "LEFT JOIN career_history ch ON b.career_history_id = ch.id "
        "WHERE b.id = %s", (bullet_id,)
    )
    if not bullet:
        return None, "Not found"

    prompt = f"""Analyze this resume bullet point for strength and quality.
Bullet: "{bullet['text']}"
Job: {bullet.get('employer', 'Unknown')} - {bullet.get('title', 'Unknown')}

Return JSON with:
- "strength": "strong", "moderate", or "weak"
- "star_check": {{"has_situation": bool, "has_task": bool, "has_action": bool, "has_result": bool}}
- "feedback": brief actionable feedback (1-2 sentences)
- "suggested_skills": array of skill tags this bullet demonstrates

Return ONLY valid JSON, no markdown."""

    result = route_ai_request(prompt, response_format="json")
    if not result:
        return None, "AI unavailable"

    try:
        analysis = json.loads(result) if isinstance(result, str) else result
    except (json.JSONDecodeError, TypeError):
        return None, "AI returned invalid response"

    analysis["content_hash_at_analysis"] = bullet.get("content_hash", "")

    db.execute(
        "UPDATE bullets SET ai_analysis = %s::jsonb, ai_analyzed_at = NOW() WHERE id = %s",
        (json.dumps(analysis), bullet_id),
    )

    return analysis, None


@bp.route("/api/bullets/<int:bullet_id>/analyze", methods=["POST"])
def analyze_bullet(bullet_id):
    """AI analysis for a single bullet."""
    analysis, error = _analyze_single_bullet(bullet_id)
    if error:
        code = 404 if error == "Not found" else 503
        return jsonify({"error": error}), code
    return jsonify({"id": bullet_id, "analysis": analysis})


@bp.route("/api/bullets/analyze", methods=["POST"])
def analyze_batch():
    """Batch AI analysis via SSE streaming.
    Body: {career_history_id} or {all: true}.
    Returns text/event-stream with progress events.
    """
    data = request.get_json(force=True)
    career_history_id = data.get("career_history_id")
    analyze_all = data.get("all", False)

    clauses = ["text IS NOT NULL", "type != 'synopsis'"]
    params = []

    if career_history_id and not analyze_all:
        clauses.append("career_history_id = %s")
        params.append(career_history_id)

    bullets = db.query(
        f"""
        SELECT id FROM bullets
        WHERE {' AND '.join(clauses)}
          AND (ai_analysis IS NULL
               OR content_hash != COALESCE(ai_analysis->>'content_hash_at_analysis', ''))
        ORDER BY career_history_id, display_order
        """,
        params,
    )

    total = len(bullets)

    def generate():
        completed = 0
        failed = 0
        yield f"data: {json.dumps({'type': 'start', 'total': total})}\n\n"

        for bullet in bullets:
            analysis, error = _analyze_single_bullet(bullet["id"])
            if error:
                failed += 1
                status = "failed"
            else:
                completed += 1
                status = "done"

            yield f"data: {json.dumps({'type': 'progress', 'bullet_id': bullet['id'], 'status': status, 'completed': completed, 'failed': failed, 'total': total})}\n\n"

        yield f"data: {json.dumps({'type': 'complete', 'completed': completed, 'failed': failed, 'total': total})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.route("/api/bullets/<int:bullet_id>/strengthen", methods=["POST"])
def strengthen_bullet(bullet_id):
    """AI strengthen a weak bullet. Body: {instruction?}"""
    bullet = db.query_one("SELECT * FROM bullets WHERE id = %s", (bullet_id,))
    if not bullet:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(force=True) or {}
    instruction = data.get("instruction", "")

    feedback = ""
    if bullet.get("ai_analysis"):
        feedback = bullet["ai_analysis"].get("feedback", "")

    prompt = f"""Strengthen this weak resume bullet point. Make it impactful with specific metrics.
Original: "{bullet['text']}"
AI Feedback: {feedback}
{f'Additional instruction: {instruction}' if instruction else ''}

Return ONLY the improved bullet text, no quotes or formatting."""

    result = route_ai_request(prompt)
    if not result:
        return jsonify({"error": "AI unavailable"}), 503

    new_text = result.strip().strip('"').strip("'")
    updated = db.execute_returning(
        "UPDATE bullets SET text = %s WHERE id = %s RETURNING id, text, content_hash",
        (new_text, bullet_id),
    )

    return jsonify({"id": bullet_id, "original": bullet["text"], "updated": updated["text"]})


@bp.route("/api/bullets/generate", methods=["POST"])
def generate_bullet():
    """AI generate new bullet. Body: {career_history_id, instruction}"""
    data = request.get_json(force=True)
    career_history_id = data.get("career_history_id")
    instruction = data.get("instruction", "")
    if not career_history_id or not instruction:
        return jsonify({"error": "career_history_id and instruction required"}), 400

    job = db.query_one("SELECT * FROM career_history WHERE id = %s", (career_history_id,))
    if not job:
        return jsonify({"error": "Job not found"}), 404

    prompt = f"""Generate a resume bullet point for this role:
Role: {job.get('title', '')} at {job.get('employer', '')}
Instruction: {instruction}

Write ONE strong resume bullet point. Start with an action verb. Include specific metrics if possible.
Return ONLY the bullet text, no quotes or formatting."""

    result = route_ai_request(prompt)
    if not result:
        return jsonify({"error": "AI unavailable"}), 503

    bullet_text = result.strip().strip('"').strip("'")

    # Get next display order
    max_order = db.query_one(
        "SELECT COALESCE(MAX(display_order), -1) + 1 as next_order FROM bullets WHERE career_history_id = %s",
        (career_history_id,),
    )

    new_bullet = db.execute_returning(
        """
        INSERT INTO bullets (career_history_id, text, type, display_order, content_hash)
        VALUES (%s, %s, 'achievement', %s, md5(%s))
        RETURNING id, career_history_id, text, type, display_order
        """,
        (career_history_id, bullet_text, max_order["next_order"], bullet_text),
    )

    return jsonify(new_bullet), 201


@bp.route("/api/bullets/<int:bullet_id>/wordsmith", methods=["POST"])
def wordsmith_bullet(bullet_id):
    """AI polish a bullet. Body: {instruction?}"""
    bullet = db.query_one("SELECT * FROM bullets WHERE id = %s", (bullet_id,))
    if not bullet:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(force=True) or {}
    instruction = data.get("instruction", "Polish and strengthen this bullet point")

    prompt = f"""Improve this resume bullet point.
Original: "{bullet['text']}"
Instruction: {instruction}

Return ONLY the improved bullet text, no quotes or formatting."""

    result = route_ai_request(prompt)
    if not result:
        return jsonify({"error": "AI unavailable"}), 503

    new_text = result.strip().strip('"').strip("'")

    updated = db.execute_returning(
        "UPDATE bullets SET text = %s WHERE id = %s RETURNING id, text, content_hash",
        (new_text, bullet_id),
    )

    return jsonify({"id": bullet_id, "original": bullet["text"], "updated": updated["text"]})


@bp.route("/api/bullets/<int:bullet_id>/variant", methods=["POST"])
def create_variant(bullet_id):
    """AI generate a variant of a bullet. Body: {instruction}"""
    bullet = db.query_one("SELECT * FROM bullets WHERE id = %s", (bullet_id,))
    if not bullet:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(force=True) or {}
    instruction = data.get("instruction", "Create an alternative version")

    prompt = f"""Create a variant of this resume bullet point.
Original: "{bullet['text']}"
Instruction: {instruction}

Return ONLY the new bullet text, no quotes or formatting."""

    result = route_ai_request(prompt)
    if not result:
        return jsonify({"error": "AI unavailable"}), 503

    variant_text = result.strip().strip('"').strip("'")

    max_order = db.query_one(
        "SELECT COALESCE(MAX(display_order), -1) + 1 as next_order FROM bullets WHERE career_history_id = %s",
        (bullet["career_history_id"],),
    )

    new_bullet = db.execute_returning(
        """
        INSERT INTO bullets (career_history_id, text, type, tags, display_order, content_hash)
        VALUES (%s, %s, %s, %s, %s, md5(%s))
        RETURNING id, career_history_id, text, type, display_order
        """,
        (bullet["career_history_id"], variant_text, bullet.get("type", "achievement"),
         bullet.get("tags"), max_order["next_order"], variant_text),
    )

    return jsonify(new_bullet), 201


@bp.route("/api/skills/sync-from-tags", methods=["POST"])
def sync_skills_from_tags():
    """Scan all bullet tags, create missing skill records."""
    all_tags = db.query(
        "SELECT DISTINCT UNNEST(tags) as tag FROM bullets WHERE tags IS NOT NULL"
    )
    existing_skills = db.query("SELECT LOWER(name) as name FROM skills")
    existing_set = {s["name"] for s in existing_skills}

    created = []
    for row in all_tags:
        tag = row["tag"].strip()
        if not tag or tag.lower() in existing_set:
            continue
        skill = db.execute_returning(
            "INSERT INTO skills (name, source) VALUES (%s, 'bullet_tag') RETURNING id, name",
            (tag,),
        )
        created.append(skill)
        existing_set.add(tag.lower())

    return jsonify({"created": created, "created_count": len(created)})
```

- [ ] **Step 2: Verify AI router import path**

Check `code/backend/routes/` for the AI router module name. It may be `ai_router.py` or integrated differently. Adjust the import accordingly.

```bash
ls code/backend/routes/ai*
grep -r "def route_ai_request" code/backend/
```

- [ ] **Step 3: Rebuild backend and test**

```bash
cd code && docker compose up -d --build backend
# Test generate
curl -s -X POST "http://localhost:8055/api/bullets/generate" \
  -H "Content-Type: application/json" \
  -d '{"career_history_id": 1, "instruction": "Create a bullet about cloud migration"}' | python -m json.tool
```

- [ ] **Step 4: Commit**

```bash
git add code/backend/routes/bullet_ops.py
git commit -m "feat(api): AI bullet operations — analyze, generate, wordsmith, variant, skills sync"
```

---

## Task 5: Frontend — Page Setup + Routing

**Files:**
- Create: `code/frontend/src/pages/bullets/BulletBrowser.tsx`
- Modify: `code/frontend/src/App.tsx`

- [ ] **Step 1: Create BulletBrowser shell with two-panel layout**

Create `code/frontend/src/pages/bullets/BulletBrowser.tsx`:

```tsx
import { useState } from 'react';
import JobList from './JobList';
import SynopsisEditor from './SynopsisEditor';
import BulletList from './BulletList';

export default function BulletBrowser() {
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [aiEnabled, setAiEnabled] = useState(false);

  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* Left Panel: Jobs */}
      <div className="w-[340px] border-r border-gray-700 flex flex-col overflow-y-auto bg-gray-900">
        <JobList selectedJobId={selectedJobId} onSelectJob={setSelectedJobId} />
      </div>

      {/* Right Panel: Synopsis + Bullets */}
      <div className="flex-1 flex flex-col overflow-y-auto bg-gray-900">
        {selectedJobId ? (
          <>
            <SynopsisEditor jobId={selectedJobId} aiEnabled={aiEnabled} />
            <BulletList jobId={selectedJobId} aiEnabled={aiEnabled} onAiToggle={setAiEnabled} />
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            Select a job from the left to view its bullets
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add route to App.tsx**

Find the Routes section and add:

```tsx
import BulletBrowser from './pages/bullets/BulletBrowser';
// In the Routes:
<Route path="/bullets" element={<BulletBrowser />} />
```

Also add nav link if there's a sidebar/nav component.

- [ ] **Step 3: Commit**

```bash
git add code/frontend/src/pages/bullets/BulletBrowser.tsx code/frontend/src/App.tsx
git commit -m "feat(ui): bullet browser page shell with routing"
```

---

## Task 6: Frontend — JobList + JobCard Components

**Files:**
- Create: `code/frontend/src/pages/bullets/JobList.tsx`
- Create: `code/frontend/src/pages/bullets/JobCard.tsx`
- Create: `code/frontend/src/pages/bullets/SmartDateInput.tsx`

- [ ] **Step 1: Create JobList component**

Fetches career history via `api.get('/career-history')`, renders search input + list of JobCards. Props: `selectedJobId`, `onSelectJob(id)`.

Key features:
- Search input filters jobs by title/company
- Total jobs + bullets count in header
- Maps over jobs rendering JobCard for each

- [ ] **Step 2: Create JobCard component**

Three states: collapsed, expanded-view, expanded-edit.

Props: `job`, `isSelected`, `onSelect`, `onUpdate`.

Collapsed: title + company + bullet count + expand arrow.
Expanded-view: details grid (title, company, location, dates, metadata) + edit button.
Expanded-edit: all fields as inputs, SmartDateInput for dates, key-value metadata editor, save/cancel.

Uses `useMutation` for PATCH `/api/career-history/{id}`.

- [ ] **Step 3: Create SmartDateInput component**

Reusable component. Props: `value`, `onChange`, `isoValue`, `onIsoChange`.

Features:
- Text input that accepts any date format
- Parses on blur/change using regex patterns for: year only, month+year, full date, ISO, "Present"
- Shows resolved ISO date beside the input
- Small calendar icon that opens native `<input type="date">` as fallback
- Parsing function + duration calculator:

```tsx
function parseFlexDate(input: string): { iso: string | null; display: string } {
  const s = input.trim();
  if (!s || /^present$/i.test(s)) return { iso: null, display: 'Present' };
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return { iso: s, display: s };
  if (/^\d{4}$/.test(s)) return { iso: `${s}-01-01`, display: s };
  const d = new Date(s);
  if (!isNaN(d.getTime())) {
    const iso = d.toISOString().split('T')[0];
    return { iso, display: s };
  }
  return { iso: null, display: s };
}

function calcDuration(fromIso: string | null, toIso: string | null): string {
  if (!fromIso) return '';
  const start = new Date(fromIso);
  const end = toIso ? new Date(toIso) : new Date();
  let months = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
  if (months < 0) return '';
  const years = Math.floor(months / 12);
  months = months % 12;
  const parts = [];
  if (years > 0) parts.push(`${years} yr${years > 1 ? 's' : ''}`);
  if (months > 0) parts.push(`${months} mo${months > 1 ? 's' : ''}`);
  return parts.join(' ') || '< 1 mo';
}
```

Duration badge is shown between the From and To fields in the JobCard edit mode, recalculated on every date change.

- [ ] **Step 4: Commit**

```bash
git add code/frontend/src/pages/bullets/JobList.tsx code/frontend/src/pages/bullets/JobCard.tsx code/frontend/src/pages/bullets/SmartDateInput.tsx
git commit -m "feat(ui): job list, job card with edit mode, smart date input"
```

---

## Task 7: Frontend — SynopsisEditor Component

**Files:**
- Create: `code/frontend/src/pages/bullets/SynopsisEditor.tsx`

- [ ] **Step 1: Create SynopsisEditor**

Props: `jobId`, `aiEnabled`.

Fetches bullets with `type=synopsis` for the given jobId via `api.get('/bullets?career_history_id={jobId}&type=synopsis')`.

Features:
- Variant tabs (each synopsis is a tab, default one has a star)
- Active variant text shown in editable div/textarea
- Action buttons: Edit, Wordsmith (AI only), Set Default, + New Variant, Generate (AI only)
- "Set Default" calls PATCH to toggle `is_default`
- "New Variant" creates a blank synopsis bullet via POST
- Empty state: "No synopsis. Click + New Variant to add one."

- [ ] **Step 2: Commit**

```bash
git add code/frontend/src/pages/bullets/SynopsisEditor.tsx
git commit -m "feat(ui): synopsis editor with variant tabs"
```

---

## Task 8: Frontend — BulletList + BulletCard Components

**Files:**
- Create: `code/frontend/src/pages/bullets/BulletList.tsx`
- Create: `code/frontend/src/pages/bullets/BulletCard.tsx`

- [ ] **Step 1: Create BulletList**

Props: `jobId`, `aiEnabled`, `onAiToggle`.

Fetches bullets via `api.get('/bullets?career_history_id={jobId}&type=!synopsis')` (exclude synopses). Manages filter text, type filter, sort order.

Layout:
- Header: "Bullets" label + strength counts (strong/mod/weak from ai_analysis) + AI Tools dropdown + Add Bullet button
- Toolbar: filter input, type dropdown, sort dropdown
- AiToolbar component (AI toggle + Analyze All)
- List of BulletCards
- Drag-and-drop reorder via HTML5 drag events (call POST `/api/bullets/reorder` on drop)

- [ ] **Step 2: Create BulletCard**

Props: `bullet`, `aiEnabled`, `onUpdate`, `onDelete`.

View mode:
- Drag handle (⠿)
- Bullet text
- Skill tags (colored badges from `bullet.tags`)
- Strength badge from `ai_analysis.strength` (green/yellow/red) — only if analyzed
- Stale indicator if `content_hash != ai_analysis.content_hash_at_analysis`
- AI feedback text (from `ai_analysis.feedback`) — only for moderate/weak
- Action buttons: Edit, Clone, Delete (always); Wordsmith, Variant, Strengthen (AI only)

Edit mode (inline):
- Textarea replacing text display
- Save calls PATCH `/api/bullets/{id}` with new text
- On save, calls POST `/api/bullets/{id}/check-duplicates` and shows DuplicateWarning if matches found
- Cancel reverts to view mode

- [ ] **Step 3: Commit**

```bash
git add code/frontend/src/pages/bullets/BulletList.tsx code/frontend/src/pages/bullets/BulletCard.tsx
git commit -m "feat(ui): bullet list with filtering, bullet card with edit/clone/delete"
```

---

## Task 9: Frontend — AI Components

**Files:**
- Create: `code/frontend/src/pages/bullets/AiToolbar.tsx`
- Create: `code/frontend/src/pages/bullets/AiInstructionModal.tsx`
- Create: `code/frontend/src/pages/bullets/DuplicateWarning.tsx`

- [ ] **Step 1: Create AiToolbar**

Props: `aiEnabled`, `onToggle`, `jobId`.

Features:
- Toggle switch (styled like the extension's AI toggle — terminal green aesthetic)
- "Analyze All" button — disabled when `stale_count + never_analyzed == 0` (polls `/api/bullets/stale-count?career_history_id={jobId}`)
- On click: calls POST `/api/bullets/analyze` with `{career_history_id}`, shows progress bar
- Progress: "Analyzing... {completed}/{total}" with elapsed time

- [ ] **Step 2: Create AiInstructionModal**

Props: `isOpen`, `onClose`, `onSubmit(instruction)`, `title`, `placeholder`.

Simple modal: title, textarea for instruction, Cancel + Submit buttons.
Used by: Generate Bullet, Wordsmith, Generate Variant, Strengthen.

- [ ] **Step 3: Create DuplicateWarning**

Props: `isOpen`, `onClose`, `onContinue`, `withinJob`, `crossJob`.

Caution popup showing similar bullets grouped by within-job and cross-job, with similarity percentages and job context. "Continue Saving" and "Go Back" buttons.

- [ ] **Step 4: Commit**

```bash
git add code/frontend/src/pages/bullets/AiToolbar.tsx code/frontend/src/pages/bullets/AiInstructionModal.tsx code/frontend/src/pages/bullets/DuplicateWarning.tsx
git commit -m "feat(ui): AI toolbar, instruction modal, duplicate warning"
```

---

## Task 10: Integration + Build + Test

**Files:**
- Modify: `code/frontend/src/api/client.ts` — add types if needed
- All frontend bullet components

- [ ] **Step 1: Add TypeScript interfaces to api client**

Add to `code/frontend/src/api/client.ts`:

```tsx
export interface Bullet {
  id: number;
  career_history_id: number;
  text: string;
  type: string;
  tags?: string[];
  display_order: number;
  ai_analysis?: {
    strength: 'strong' | 'moderate' | 'weak';
    star_check: Record<string, boolean>;
    feedback: string;
    suggested_skills: string[];
    content_hash_at_analysis: string;
  };
  ai_analyzed_at?: string;
  content_hash?: string;
  is_default?: boolean;
  updated_at?: string;
  created_at?: string;
}

export interface CareerHistoryJob {
  id: number;
  employer: string;
  title: string;
  location?: string;
  start_date?: string;
  end_date?: string;
  start_date_raw?: string;
  end_date_raw?: string;
  start_date_iso?: string;
  end_date_iso?: string;
  metadata?: Record<string, string>;
  bullet_count?: number;
}
```

- [ ] **Step 2: Rebuild frontend and backend**

```bash
cd code && docker compose up -d --build frontend backend
```

- [ ] **Step 3: Navigate to /bullets in browser and verify**

Open http://localhost:5175/bullets and verify:
- Left panel shows job list
- Clicking a job loads synopsis + bullets in right panel
- Edit mode works on job cards
- Add/edit/clone/delete bullets work
- AI toggle enables AI features
- Analyze All runs batch analysis

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: bullet browser — full integration, types, build verified"
```

---

## Task Summary

| Task | Description | Estimated Effort |
|------|-------------|-----------------|
| 1 | Database migration | Small |
| 2 | Update existing backend endpoints | Small |
| 3 | New bullet ops blueprint (clone, reorder, duplicates) | Medium |
| 4 | AI endpoints (analyze, generate, wordsmith, variant) | Medium |
| 5 | Frontend page shell + routing | Small |
| 6 | JobList + JobCard + SmartDateInput | Medium |
| 7 | SynopsisEditor | Medium |
| 8 | BulletList + BulletCard | Large |
| 9 | AI components (toolbar, modal, duplicate warning) | Medium |
| 10 | Integration, types, build, test | Medium |
