import { useState, useEffect, useRef, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';
import EditorToolbar from './EditorToolbar';
import HeaderBlock from './blocks/HeaderBlock';
import TextBlock from './blocks/TextBlock';
import ExperienceBlock from './blocks/ExperienceBlock';
import SkillTagsBlock from './blocks/SkillTagsBlock';
import LiteralListBlock from './blocks/LiteralListBlock';
import ThemePanel from './ThemePanel';
import ContentPickerModal from './ContentPickerModal';
import type { BulletRef, SkillRef, RecipeV2, ResolvedV2, ThemeSettings } from './types';

interface Props {
  recipeId: number;
  recipeName: string;
  recipe: RecipeV2;
  resolved: ResolvedV2;
  theme: ThemeSettings;
}

export default function ResumeEditor({ recipeId, recipeName, recipe: initialRecipe, resolved: initialResolved, theme: initialTheme }: Props) {
  const [recipe, setRecipe] = useState<RecipeV2>(initialRecipe);
  const [resolved, setResolved] = useState<ResolvedV2>(initialResolved);
  const [theme, setTheme] = useState<ThemeSettings>(initialTheme);
  const [saveState, setSaveState] = useState<'saved' | 'saving' | 'unsaved'>('saved');
  const [showTheme, setShowTheme] = useState(false);
  const [pickerState, setPickerState] = useState<{
    mode: 'bullets' | 'jobs' | 'summaries';
    jobIndex?: number;
    filterEmployer?: string;
  } | null>(null);

  // Sync resolved when initial data changes (e.g. after query refetch)
  useEffect(() => { setResolved(initialResolved); }, [initialResolved]);
  useEffect(() => { setRecipe(initialRecipe); }, [initialRecipe]);

  // Undo/redo
  const undoStack = useRef<RecipeV2[]>([]);
  const redoStack = useRef<RecipeV2[]>([]);
  const MAX_UNDO = 50;

  const pushUndo = useCallback((prev: RecipeV2) => {
    undoStack.current = [...undoStack.current.slice(-MAX_UNDO + 1), prev];
    redoStack.current = [];
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        if (undoStack.current.length > 0) {
          const prev = undoStack.current.pop()!;
          redoStack.current.push(recipe);
          setRecipe(prev);
        }
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
        e.preventDefault();
        if (redoStack.current.length > 0) {
          const next = redoStack.current.pop()!;
          undoStack.current.push(recipe);
          setRecipe(next);
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [recipe]);

  // Autosave
  const autosaveMutation = useMutation({
    mutationFn: (data: { recipe: RecipeV2; theme: ThemeSettings }) =>
      api.put(`/resume/recipes/${recipeId}/autosave`, data),
    onMutate: () => setSaveState('saving'),
    onSuccess: () => setSaveState('saved'),
    onError: () => setSaveState('unsaved'),
  });

  const saveTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const initialRender = useRef(true);
  useEffect(() => {
    // Skip autosave on initial render
    if (initialRender.current) {
      initialRender.current = false;
      return;
    }
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    setSaveState('unsaved');
    saveTimerRef.current = setTimeout(() => {
      autosaveMutation.mutate({ recipe, theme });
    }, 1500);
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recipe, theme]);

  const updateRecipe = useCallback((updater: (prev: RecipeV2) => RecipeV2) => {
    setRecipe(prev => {
      pushUndo(prev);
      return updater(prev);
    });
  }, [pushUndo]);

  // Generate .docx
  const generateMutation = useMutation({
    mutationFn: async () => {
      const base = import.meta.env.VITE_API_URL || '/api';
      const res = await fetch(`${base}/resume/recipes/${recipeId}/generate`, { method: 'POST' });
      if (!res.ok) throw new Error('Generation failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${recipeName.replace(/\s+/g, '_')}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    },
  });

  // Theme CSS variables
  const themeStyle: Record<string, string> = {
    '--font-family': theme.font_family ?? 'Georgia, serif',
    '--font-size-body': `${theme.font_size_body ?? 11}pt`,
    '--font-size-heading': `${theme.font_size_heading ?? 14}pt`,
    '--font-size-name': `${theme.font_size_name ?? 20}pt`,
    '--accent-color': theme.accent_color ?? '#2563eb',
    '--header-alignment': theme.header_alignment ?? 'left',
  };

  return (
    <div className="flex flex-col h-full">
      <EditorToolbar
        recipeName={recipeName}
        saveState={saveState}
        onGenerate={() => generateMutation.mutate()}
        onAiReview={() => {/* Phase 4 */}}
        onAtsScore={() => {/* Phase 4 */}}
        onToggleTheme={() => setShowTheme(!showTheme)}
        generating={generateMutation.isPending}
      />

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 overflow-y-auto p-8 max-w-4xl mx-auto" style={themeStyle as React.CSSProperties}>
          <div className="bg-white text-gray-900 shadow-lg rounded p-8 min-h-[11in]" style={{ fontFamily: 'var(--font-family)' }}>

            {/* Header */}
            {resolved.header && recipe.header && (
              <HeaderBlock data={resolved.header} headerId={recipe.header.id ?? 1} themeVars={themeStyle} />
            )}

            {/* Headline */}
            <TextBlock
              label="Headline"
              slotKey="headline"
              value={typeof resolved.headline === 'string' ? resolved.headline : ''}
              onSave={(_, text) => updateRecipe(r => ({ ...r, headline: { literal: text } }))}
            />

            {/* Highlights */}
            {resolved.highlights && resolved.highlights.length > 0 && (
              <LiteralListBlock
                label="Highlights"
                slotKey="highlights"
                items={resolved.highlights}
                onUpdate={(_, items) => updateRecipe(r => ({
                  ...r, highlights: items.map(text => ({ literal: text })),
                }))}
              />
            )}

            {/* Summary */}
            <TextBlock
              label="Summary"
              slotKey="summary"
              value={typeof resolved.summary === 'string' ? resolved.summary : ''}
              onSave={(_, text) => updateRecipe(r => ({ ...r, summary: { literal: text } }))}
              onPickFromDb={() => setPickerState({ mode: 'summaries' })}
            />

            {/* Experience */}
            {recipe.experience && resolved.experience && (
              <ExperienceBlock
                jobs={recipe.experience}
                resolvedJobs={resolved.experience}
                recipeId={recipeId}
                onRecipeChange={(exp) => updateRecipe(r => ({ ...r, experience: exp }))}
                onPickBullet={(jobIdx) => setPickerState({
                  mode: 'bullets',
                  jobIndex: jobIdx,
                  filterEmployer: resolved.experience?.[jobIdx]?.employer,
                })}
                onAddJob={() => setPickerState({ mode: 'jobs' })}
              />
            )}

            {/* Skills */}
            {recipe.skills && resolved.skills && (
              <SkillTagsBlock
                skillRefs={recipe.skills}
                resolvedSkills={resolved.skills}
                onUpdate={(skills) => updateRecipe(r => ({ ...r, skills }))}
              />
            )}

            {/* Education */}
            <LiteralListBlock
              label="Education"
              slotKey="education"
              items={resolved.education ?? []}
              onUpdate={(_, items) => updateRecipe(r => ({
                ...r, education: items.map(text => ({ literal: text })),
              }))}
            />

            {/* Certifications */}
            <LiteralListBlock
              label="Certifications"
              slotKey="certifications"
              items={resolved.certifications ?? []}
              onUpdate={(_, items) => updateRecipe(r => ({
                ...r, certifications: items.map(text => ({ literal: text })),
              }))}
            />

            {/* Additional Experience */}
            {resolved.additional_experience && resolved.additional_experience.length > 0 && (
              <LiteralListBlock
                label="Additional Experience"
                slotKey="additional_experience"
                items={resolved.additional_experience}
                onUpdate={(_, items) => updateRecipe(r => ({
                  ...r, additional_experience: items.map(text => ({ literal: text })),
                }))}
              />
            )}
          </div>
        </div>

        {showTheme && (
          <ThemePanel theme={theme} onChange={setTheme} onClose={() => setShowTheme(false)} />
        )}
      </div>

      {pickerState && (
        <ContentPickerModal
          mode={pickerState.mode}
          filterEmployer={pickerState.filterEmployer}
          onSelect={(item) => {
            if (pickerState.mode === 'bullets' && pickerState.jobIndex != null) {
              updateRecipe(r => {
                const exp = [...(r.experience ?? [])];
                exp[pickerState.jobIndex!] = {
                  ...exp[pickerState.jobIndex!],
                  bullets: [...exp[pickerState.jobIndex!].bullets, { ref: item.ref, id: item.id }],
                };
                return { ...r, experience: exp };
              });
            } else if (pickerState.mode === 'jobs') {
              updateRecipe(r => ({
                ...r,
                experience: [...(r.experience ?? []), { ref: 'career_history', id: item.id, bullets: [] }],
              }));
            } else if (pickerState.mode === 'summaries') {
              updateRecipe(r => ({ ...r, summary: { ref: 'summary_variants', id: item.id } }));
            }
            setPickerState(null);
          }}
          onClose={() => setPickerState(null)}
        />
      )}
    </div>
  );
}
