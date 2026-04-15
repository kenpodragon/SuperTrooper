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

  const otherTemplates = allTemplates.filter((t) => t.id !== template.id && t.is_active !== false);

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
    setBulkTarget('');
  };

  const handleDelete = async () => {
    setLoading(true);
    setError(null);
    try {
      if (mode === 'delete' || template.recipe_count === 0) {
        await templates.delWithStrategy(template.id, { delete_recipes: template.recipe_count > 0 });
      } else {
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
