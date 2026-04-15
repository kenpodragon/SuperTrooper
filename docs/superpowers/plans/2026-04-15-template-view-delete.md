# Template View/Delete/Swap — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add template management (gallery enhancements, smart delete with recipe reassignment, template swap in editor, default template).

**Architecture:** Enhance existing TemplatesBrowser with a delete modal that handles recipe reassignment. Add a slide-out TemplateSwapPanel to the ResumeEditor. Extend the backend DELETE endpoint to accept reassignment strategies. Add `is_default` column for seed template protection.

**Tech Stack:** React + TanStack Query (frontend), Flask + PostgreSQL (backend), existing `templates` API client helpers.

**Spec:** `code/docs/superpowers/specs/2026-04-15-template-view-delete-design.md`

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/pages/resumes/DeleteTemplateModal.tsx` | Delete confirmation modal with recipe reassignment UI |
| `frontend/src/pages/resume-builder/TemplateSwapPanel.tsx` | Slide-out panel for changing template in editor |
| `db/migrations/035_template_is_default.sql` | Add `is_default` column to `resume_templates` |

### Modified Files
| File | Changes |
|------|---------|
| `backend/routes/resume.py` (~lines 1130-1142) | Extend DELETE endpoint to accept reassignment strategy |
| `frontend/src/pages/resumes/TemplatesBrowser.tsx` | Replace `confirm()` with DeleteTemplateModal, add default badge |
| `frontend/src/pages/resume-builder/ResumeEditor.tsx` | Add template info bar + "Change" button, wire TemplateSwapPanel |
| `frontend/src/pages/resume-builder/ResumeBuilder.tsx` | Pass `templateId` + `templateName` to ResumeEditor |
| `frontend/src/api/client.ts` | Add `templates.delWithStrategy()` helper |

---

## Task 1: Migration — Add `is_default` Column

**Files:**
- Create: `db/migrations/035_template_is_default.sql`

- [ ] **Step 1: Write migration**

```sql
-- 035_template_is_default.sql
-- Add is_default flag to resume_templates for seed/built-in template protection.
ALTER TABLE resume_templates ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE;
```

- [ ] **Step 2: Run migration**

Run: `PGPASSWORD=WUHD8fBisb57FS4Q3bdvfuvgnim9fL1c psql -h localhost -p 5555 -U supertroopers -d supertroopers -f db/migrations/035_template_is_default.sql`
Expected: `ALTER TABLE`

- [ ] **Step 3: Verify column exists**

Run: `PGPASSWORD=WUHD8fBisb57FS4Q3bdvfuvgnim9fL1c psql -h localhost -p 5555 -U supertroopers -d supertroopers -c "SELECT column_name, data_type, column_default FROM information_schema.columns WHERE table_name = 'resume_templates' AND column_name = 'is_default';"`
Expected: `is_default | boolean | false`

- [ ] **Step 4: Commit**

```bash
git add db/migrations/035_template_is_default.sql
git commit -m "feat: add is_default column to resume_templates"
```

---

## Task 2: Backend — Extend DELETE Endpoint

**Files:**
- Modify: `backend/routes/resume.py` (~lines 1130-1142)

The current DELETE endpoint blocks if recipes reference the template. We need to accept a strategy: reassign recipes to another template, or delete them.

- [ ] **Step 1: Replace the existing `delete_template` function**

Find the existing function at ~line 1130 and replace it with:

```python
@bp.route("/api/resume/templates/<int:template_id>", methods=["DELETE"])
def delete_template(template_id):
    """Delete a template with optional recipe handling strategy.

    Body (optional JSON):
        reassign_to: dict mapping recipe_id (str) -> new_template_id (int)
        delete_recipes: bool — if true, delete all linked recipes
    If recipes exist and no strategy provided, returns 409 with affected list.
    """
    row = db.query_one("SELECT id, name, is_default FROM resume_templates WHERE id = %s", (template_id,))
    if not row:
        return jsonify({"error": "Template not found"}), 404

    if row.get("is_default"):
        return jsonify({"error": "Cannot delete the default template"}), 403

    # Check for linked recipes
    linked = db.query(
        "SELECT id, name FROM resume_recipes WHERE template_id = %s",
        (template_id,),
    ) or []

    if linked:
        data = request.get_json(silent=True) or {}
        reassign_to = data.get("reassign_to")  # {"recipe_id": new_template_id, ...}
        delete_recipes = data.get("delete_recipes", False)

        if delete_recipes:
            db.execute("DELETE FROM resume_recipes WHERE template_id = %s", (template_id,))
        elif reassign_to:
            for rid_str, new_tid in reassign_to.items():
                rid = int(rid_str)
                # Verify target template exists
                target = db.query_one("SELECT id FROM resume_templates WHERE id = %s", (new_tid,))
                if not target:
                    return jsonify({"error": f"Target template {new_tid} not found for recipe {rid}"}), 400
                db.execute(
                    "UPDATE resume_recipes SET template_id = %s WHERE id = %s",
                    (new_tid, rid),
                )
        else:
            return jsonify({
                "error": f"Cannot delete: {len(linked)} recipe(s) reference this template. Provide reassign_to or delete_recipes.",
                "affected_recipes": [{"id": r["id"], "name": r["name"]} for r in linked],
            }), 409

    db.execute("DELETE FROM resume_templates WHERE id = %s", (template_id,))
    return jsonify({"deleted": template_id, "name": row["name"]})
```

- [ ] **Step 2: Update GET templates to include is_default**

Find the `list_templates` function (~line 1079) and add `is_default` to the SELECT and response. In the SQL query, add `t.is_default` to the SELECT columns. In the row mapping, add `"is_default": r.get("is_default", False)`.

- [ ] **Step 3: Test via psql + curl equivalent**

Verify with a Python request to confirm the endpoint accepts the new body format (test against a non-critical template or just verify the 409 response returns the recipe list).

- [ ] **Step 4: Restart containers**

```bash
cd "c:/Users/ssala/OneDrive/Desktop/Resumes/code" && docker compose up -d
```

- [ ] **Step 5: Commit**

```bash
git add backend/routes/resume.py
git commit -m "feat: extend template DELETE with recipe reassignment strategy"
```

---

## Task 3: Frontend — API Client Helper

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add `delWithStrategy` to templates object and update types**

Add to the `templates` object (after the existing `del` method):

```typescript
delWithStrategy: (id: number, strategy: { reassign_to?: Record<string, number>; delete_recipes?: boolean }) =>
  api.del<{ deleted: number; name: string } | { error: string; affected_recipes: { id: number; name: string }[] }>(
    `/resume/templates/${id}`,
    strategy,
  ),
```

Also add `is_default` to the `TemplateListItem` interface:

```typescript
is_default?: boolean;
```

Check if `api.del` supports a body argument. If it currently only takes a URL, add an optional body parameter:

```typescript
del: async <T>(path: string, body?: unknown): Promise<T> => {
  const res = await fetch(`${BASE}${path}`, {
    method: 'DELETE',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw err;
  }
  return res.json();
},
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add template delete-with-strategy API helper"
```

---

## Task 4: Frontend — DeleteTemplateModal

**Files:**
- Create: `frontend/src/pages/resumes/DeleteTemplateModal.tsx`

- [ ] **Step 1: Create the modal component**

```tsx
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { templates } from '../../api/client';
import type { TemplateListItem } from '../../api/client';

interface Props {
  template: TemplateListItem;
  allTemplates: TemplateListItem[];
  onClose: () => void;
}

export default function DeleteTemplateModal({ template, allTemplates, onClose }: Props) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<'reassign' | 'delete'>('reassign');
  const [bulkTarget, setBulkTarget] = useState<number | ''>('');
  const [perRecipe, setPerRecipe] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [affectedRecipes, setAffectedRecipes] = useState<{ id: number; name: string }[]>([]);
  const [loaded, setLoaded] = useState(false);

  // Other templates available for reassignment (exclude the one being deleted)
  const otherTemplates = allTemplates.filter((t) => t.id !== template.id && t.is_active !== false);

  // Load affected recipes on mount
  const loadAffected = async () => {
    if (loaded) return;
    try {
      await templates.delWithStrategy(template.id, {});
    } catch (err: any) {
      if (err?.affected_recipes) {
        setAffectedRecipes(err.affected_recipes);
      }
    }
    setLoaded(true);
  };

  // Run on first render
  if (!loaded && template.recipe_count > 0) {
    loadAffected();
  }

  const handleBulkAssign = (targetId: number) => {
    setBulkTarget(targetId);
    const mapped: Record<string, number> = {};
    affectedRecipes.forEach((r) => { mapped[String(r.id)] = targetId; });
    setPerRecipe(mapped);
  };

  const handlePerRecipeChange = (recipeId: number, targetId: number) => {
    setPerRecipe((prev) => ({ ...prev, [String(recipeId)]: targetId }));
    setBulkTarget(''); // clear bulk since user customized
  };

  const handleDelete = async () => {
    setLoading(true);
    setError(null);
    try {
      if (mode === 'delete' || template.recipe_count === 0) {
        await templates.delWithStrategy(template.id, { delete_recipes: template.recipe_count > 0 });
      } else {
        // Validate all recipes have assignments
        const unassigned = affectedRecipes.filter((r) => !perRecipe[String(r.id)]);
        if (unassigned.length > 0) {
          setError(`${unassigned.length} recipe(s) still need a template assignment.`);
          setLoading(false);
          return;
        }
        await templates.delWithStrategy(template.id, { reassign_to: perRecipe });
      }
      qc.invalidateQueries({ queryKey: ['templates'] });
      qc.invalidateQueries({ queryKey: ['recipes'] });
      onClose();
    } catch (err: any) {
      setError(err?.error || err?.message || 'Delete failed');
    } finally {
      setLoading(false);
    }
  };

  const hasRecipes = template.recipe_count > 0;

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}
      onClick={onClose}
    >
      <div
        style={{ background: 'white', borderRadius: 12, padding: 24, maxWidth: 520, width: '100%', margin: 16, maxHeight: '80vh', overflowY: 'auto' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Delete Template</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: '#9ca3af' }}>&times;</button>
        </div>

        <p style={{ fontSize: 14, color: '#374151', marginBottom: 16 }}>
          Delete <strong>{template.name}</strong>? The template layout will be removed. All parsed data (bullets, career history, skills) stays.
        </p>

        {hasRecipes && (
          <>
            <div style={{ padding: 12, background: '#fef3c7', borderRadius: 8, marginBottom: 16, fontSize: 13, color: '#92400e' }}>
              {template.recipe_count} recipe{template.recipe_count !== 1 ? 's' : ''} use this template.
            </div>

            {/* Mode toggle */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              <button
                onClick={() => setMode('reassign')}
                style={{
                  padding: '8px 16px', borderRadius: 6, fontSize: 13, cursor: 'pointer', border: '1px solid',
                  borderColor: mode === 'reassign' ? '#3b82f6' : '#d1d5db',
                  background: mode === 'reassign' ? '#eff6ff' : 'white',
                  color: mode === 'reassign' ? '#1d4ed8' : '#6b7280',
                }}
              >
                Reassign Recipes
              </button>
              <button
                onClick={() => setMode('delete')}
                style={{
                  padding: '8px 16px', borderRadius: 6, fontSize: 13, cursor: 'pointer', border: '1px solid',
                  borderColor: mode === 'delete' ? '#ef4444' : '#d1d5db',
                  background: mode === 'delete' ? '#fef2f2' : 'white',
                  color: mode === 'delete' ? '#dc2626' : '#6b7280',
                }}
              >
                Delete Recipes Too
              </button>
            </div>

            {mode === 'reassign' && (
              <>
                {/* Bulk assign */}
                <div style={{ marginBottom: 12 }}>
                  <label style={{ fontSize: 12, fontWeight: 500, color: '#374151', display: 'block', marginBottom: 4 }}>
                    Assign all to:
                  </label>
                  <select
                    value={bulkTarget}
                    onChange={(e) => handleBulkAssign(Number(e.target.value))}
                    style={{ width: '100%', padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13 }}
                  >
                    <option value="">Choose template...</option>
                    {otherTemplates.map((t) => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                </div>

                {/* Per-recipe assignment */}
                <div style={{ maxHeight: 200, overflowY: 'auto', marginBottom: 12 }}>
                  {affectedRecipes.map((r) => (
                    <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderBottom: '1px solid #f3f4f6' }}>
                      <span style={{ fontSize: 13, flex: 1, color: '#374151' }}>{r.name}</span>
                      <select
                        value={perRecipe[String(r.id)] || ''}
                        onChange={(e) => handlePerRecipeChange(r.id, Number(e.target.value))}
                        style={{ padding: '4px 6px', border: '1px solid #d1d5db', borderRadius: 4, fontSize: 12, maxWidth: 200 }}
                      >
                        <option value="">Assign to...</option>
                        {otherTemplates.map((t) => (
                          <option key={t.id} value={t.id}>{t.name}</option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              </>
            )}

            {mode === 'delete' && (
              <div style={{ padding: 12, background: '#fef2f2', borderRadius: 8, marginBottom: 16, fontSize: 13, color: '#991b1b' }}>
                This will delete {template.recipe_count} recipe{template.recipe_count !== 1 ? 's' : ''}. Bullet data and career history are NOT affected.
              </div>
            )}
          </>
        )}

        {error && <p style={{ fontSize: 13, color: '#dc2626', marginBottom: 12 }}>{error}</p>}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{ padding: '8px 16px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, cursor: 'pointer', background: 'white' }}
          >
            Cancel
          </button>
          <button
            onClick={handleDelete}
            disabled={loading}
            style={{
              padding: '8px 16px', borderRadius: 6, fontSize: 13, cursor: loading ? 'wait' : 'pointer', border: 'none',
              background: mode === 'delete' || !hasRecipes ? '#dc2626' : '#1e293b',
              color: 'white', opacity: loading ? 0.6 : 1,
            }}
          >
            {loading ? 'Deleting...' : mode === 'delete' || !hasRecipes ? 'Delete' : 'Reassign & Delete'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/resumes/DeleteTemplateModal.tsx
git commit -m "feat: add DeleteTemplateModal with recipe reassignment"
```

---

## Task 5: Frontend — Enhance TemplatesBrowser

**Files:**
- Modify: `frontend/src/pages/resumes/TemplatesBrowser.tsx`

- [ ] **Step 1: Add import and state for DeleteTemplateModal**

At the top of the file, add:

```typescript
import DeleteTemplateModal from './DeleteTemplateModal';
```

Add state inside `TemplatesBrowser`:

```typescript
const [deleteTarget, setDeleteTarget] = useState<TemplateListItem | null>(null);
```

- [ ] **Step 2: Replace `confirmDelete` and `deleteMut` with modal trigger**

Remove the `deleteMut` mutation (lines 18-25) and the `confirmDelete` function (lines 42-47).

Replace `onDelete` prop usage on `TemplateCard` (line 110):

```tsx
onDelete={() => setDeleteTarget(t)}
```

After the grid `</div>` (after line 114), add the modal:

```tsx
{deleteTarget && (
  <DeleteTemplateModal
    template={deleteTarget}
    allTemplates={templateList ?? []}
    onClose={() => setDeleteTarget(null)}
  />
)}
```

- [ ] **Step 3: Add default badge and hide delete on default templates**

In the `TemplateCard` component, update the info section. After the name `<h3>` (line 171), add:

```tsx
{t.is_default && (
  <span style={{
    fontSize: 10, padding: '2px 8px', borderRadius: 12,
    background: '#dbeafe', color: '#1d4ed8', fontWeight: 500,
  }}>
    Default
  </span>
)}
```

Conditionally hide the delete button (wrap existing delete button, line 173):

```tsx
{!t.is_default && (
  <button
    onClick={(e) => { e.stopPropagation(); onDelete(); }}
    style={{
      background: 'none', border: 'none', color: '#ef4444',
      cursor: 'pointer', fontSize: 12, padding: '2px 6px', borderRadius: 4,
    }}
    title="Delete template"
  >
    Del
  </button>
)}
```

- [ ] **Step 4: Add `is_default` to TemplateCard props type**

The `TemplateListItem` type was updated in Task 3. Verify the `TemplateCard` component receives `is_default` via the `template` prop (it does — the whole object is passed).

- [ ] **Step 5: Test in browser**

Open http://localhost:5173/resumes, go to Templates tab. Verify:
- Cards render with thumbnails
- Default template shows "Default" badge, no delete button
- Non-default templates show "Del" button
- Clicking "Del" opens the modal (not browser `confirm()`)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/resumes/TemplatesBrowser.tsx
git commit -m "feat: wire DeleteTemplateModal into TemplatesBrowser, add default badge"
```

---

## Task 6: Frontend — TemplateSwapPanel

**Files:**
- Create: `frontend/src/pages/resume-builder/TemplateSwapPanel.tsx`

- [ ] **Step 1: Create the slide-out panel component**

```tsx
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { templates as templatesApi, templateThumbnailUrl } from '../../api/client';

interface Props {
  currentTemplateId: number;
  onSelect: (templateId: number) => void;
  onClose: () => void;
}

export default function TemplateSwapPanel({ currentTemplateId, onSelect, onClose }: Props) {
  const [selected, setSelected] = useState<number>(currentTemplateId);

  const { data: templateList } = useQuery({
    queryKey: ['templates'],
    queryFn: () => templatesApi.list(),
  });

  const activeTemplates = (templateList ?? []).filter((t) => t.is_active !== false);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.2)', zIndex: 40 }}
      />
      {/* Panel */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: 280,
        background: 'white', borderLeft: '2px solid #3b82f6',
        boxShadow: '-4px 0 12px rgba(0,0,0,0.08)', zIndex: 50,
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid #e5e7eb' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Change Template</h3>
            <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, cursor: 'pointer', color: '#9ca3af' }}>&times;</button>
          </div>
          <p style={{ fontSize: 12, color: '#6b7280', marginTop: 4, marginBottom: 0 }}>Select a new layout design</p>
        </div>

        {/* Template list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {activeTemplates.map((t) => {
            const isCurrent = t.id === currentTemplateId;
            const isSelected = t.id === selected;
            return (
              <div
                key={t.id}
                onClick={() => setSelected(t.id)}
                style={{
                  border: `2px solid ${isSelected ? '#3b82f6' : '#e5e7eb'}`,
                  borderRadius: 8, padding: 8, cursor: 'pointer',
                  background: isSelected ? '#f0f7ff' : 'white',
                  transition: 'border-color 0.15s',
                }}
              >
                <div style={{
                  height: 60, background: '#f9fafb', borderRadius: 4,
                  marginBottom: 6, display: 'flex', alignItems: 'center',
                  justifyContent: 'center', overflow: 'hidden',
                }}>
                  {t.has_thumbnail ? (
                    <img
                      src={templateThumbnailUrl(t.id)}
                      alt={t.name}
                      style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }}
                    />
                  ) : (
                    <span style={{ fontSize: 24, color: '#d1d5db' }}>&#128196;</span>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 500, color: '#111' }}>{t.name}</span>
                  {isCurrent && (
                    <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 8, background: '#dbeafe', color: '#1d4ed8' }}>Current</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div style={{ padding: 12, borderTop: '1px solid #e5e7eb', display: 'flex', gap: 8 }}>
          <button
            onClick={onClose}
            style={{ flex: 1, padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, cursor: 'pointer', background: 'white' }}
          >
            Cancel
          </button>
          <button
            onClick={() => { if (selected !== currentTemplateId) onSelect(selected); }}
            disabled={selected === currentTemplateId}
            style={{
              flex: 1, padding: '8px 12px', borderRadius: 6, fontSize: 13,
              cursor: selected === currentTemplateId ? 'not-allowed' : 'pointer',
              border: 'none', background: '#1e293b', color: 'white',
              opacity: selected === currentTemplateId ? 0.5 : 1,
            }}
          >
            Apply Template
          </button>
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/resume-builder/TemplateSwapPanel.tsx
git commit -m "feat: add TemplateSwapPanel slide-out component"
```

---

## Task 7: Frontend — Wire Template Swap into Editor

**Files:**
- Modify: `frontend/src/pages/resume-builder/ResumeBuilder.tsx`
- Modify: `frontend/src/pages/resume-builder/ResumeEditor.tsx`

- [ ] **Step 1: Pass template info from ResumeBuilder to ResumeEditor**

In `ResumeBuilder.tsx`, the recipe query fetches recipe data which includes `template_id`. Find where `<ResumeEditor>` is rendered and add `templateId` and `templateName` props:

```tsx
<ResumeEditor
  recipeId={recipeId}
  recipeName={recipe.name}
  recipe={recipe.recipe}
  resolved={recipe.resolved}
  theme={recipe.theme}
  templateId={recipe.template_id}
  templateName={recipe.template_name || 'Unknown'}
/>
```

Check the recipe API response to confirm `template_id` and `template_name` are included. If `template_name` is not returned, add it to the backend recipe detail endpoint (join with `resume_templates` table).

- [ ] **Step 2: Add template props and swap state to ResumeEditor**

In `ResumeEditor.tsx`, update the Props interface:

```typescript
interface Props {
  recipeId: number;
  recipeName: string;
  recipe: RecipeV2;
  resolved: ResolvedV2;
  theme: ThemeSettings;
  templateId: number;
  templateName: string;
}
```

Add imports and state:

```typescript
import TemplateSwapPanel from './TemplateSwapPanel';
import { api, templateThumbnailUrl } from '../../api/client';
```

```typescript
const [showSwapPanel, setShowSwapPanel] = useState(false);
```

- [ ] **Step 3: Add template info bar to editor layout**

In the editor's JSX, add a template bar above or below the toolbar. Find where `<EditorToolbar>` is rendered and add after it:

```tsx
{/* Template info bar */}
<div style={{
  display: 'flex', alignItems: 'center', gap: 12, padding: '8px 16px',
  background: '#f9fafb', borderBottom: '1px solid #e5e7eb',
}}>
  <div style={{
    width: 40, height: 52, background: '#fff', border: '1px solid #e5e7eb',
    borderRadius: 4, overflow: 'hidden', display: 'flex', alignItems: 'center',
    justifyContent: 'center', flexShrink: 0,
  }}>
    <img
      src={templateThumbnailUrl(templateId)}
      alt="Template"
      style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }}
      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
    />
  </div>
  <div style={{ flex: 1, minWidth: 0 }}>
    <div style={{ fontSize: 12, color: '#6b7280' }}>Template</div>
    <div style={{ fontSize: 13, fontWeight: 500, color: '#111', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
      {templateName}
    </div>
  </div>
  <button
    onClick={() => setShowSwapPanel(true)}
    style={{
      padding: '6px 12px', border: '1px solid #d1d5db', borderRadius: 6,
      fontSize: 12, cursor: 'pointer', background: 'white', color: '#374151',
      flexShrink: 0,
    }}
  >
    Change
  </button>
</div>

{showSwapPanel && (
  <TemplateSwapPanel
    currentTemplateId={templateId}
    onSelect={async (newTemplateId) => {
      await api.put(`/resume/recipes/${recipeId}`, { template_id: newTemplateId });
      setShowSwapPanel(false);
      window.location.reload(); // Reload to re-fetch recipe with new template
    }}
    onClose={() => setShowSwapPanel(false)}
  />
)}
```

Note: `window.location.reload()` is a pragmatic choice here. The recipe data including resolved content needs to re-fetch with the new template. A more refined approach would invalidate the query, but a reload is simpler and correct.

- [ ] **Step 4: Verify recipe API includes template info**

Check that `GET /api/resume/recipes/<id>` returns `template_id` and a `template_name` field. If `template_name` is missing, add a JOIN in the backend:

In `backend/routes/resume.py`, find the recipe detail endpoint and add:

```python
template_name = ""
if recipe_row.get("template_id"):
    tpl = db.query_one("SELECT name FROM resume_templates WHERE id = %s", (recipe_row["template_id"],))
    template_name = tpl["name"] if tpl else ""
# Include in response:
# "template_name": template_name,
```

- [ ] **Step 5: Test in browser**

Open http://localhost:5173/resume-builder/{id}. Verify:
- Template info bar shows below toolbar with thumbnail, name, and "Change" button
- Clicking "Change" opens slide-out panel
- Panel shows all templates with current highlighted
- Selecting a different template and clicking "Apply" reloads with new template

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/resume-builder/ResumeBuilder.tsx frontend/src/pages/resume-builder/ResumeEditor.tsx backend/routes/resume.py
git commit -m "feat: wire template swap panel into resume editor"
```

---

## Task 8: Cleanup & Verification

- [ ] **Step 1: Full browser walkthrough**

Test the complete flow:
1. Go to Resumes > Templates tab — verify card grid with thumbnails, default badge
2. Click "Del" on a template with recipes — verify modal shows with reassignment options
3. Use "Assign all to" to bulk reassign, then delete — verify recipes moved, template gone
4. Go to Resumes > Templates tab — verify a template with 0 recipes shows simple delete
5. Open a recipe in the editor — verify template bar shows with thumbnail
6. Click "Change" — verify slide-out panel, select new template, apply — editor reloads

- [ ] **Step 2: Verify default template protection**

Confirm the default template card shows "Default" badge and no delete button. If no template is flagged as default yet (the seed file is a manual step), temporarily flag one for testing:

```sql
UPDATE resume_templates SET is_default = true WHERE id = (SELECT id FROM resume_templates ORDER BY id LIMIT 1);
```

- [ ] **Step 3: Final commit if any fixes**

```bash
git add -A && git commit -m "fix: template view/delete/swap polish"
```
