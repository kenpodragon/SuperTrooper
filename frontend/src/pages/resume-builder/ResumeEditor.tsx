import { useState, useEffect, useRef, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, recipeGenerateDocx, templateThumbnailUrl } from '../../api/client';
import EditorToolbar from './EditorToolbar';
import HeaderBlock from './blocks/HeaderBlock';
import TextBlock from './blocks/TextBlock';
import ExperienceBlock from './blocks/ExperienceBlock';
import SkillTagsBlock from './blocks/SkillTagsBlock';
import LiteralListBlock from './blocks/LiteralListBlock';
import ThemePanel from './ThemePanel';
import AtsScoreModal from './AtsScoreModal';
import AiReviewPanel from './AiReviewPanel';
import BestPicksPanel from './BestPicksPanel';
import AiGenerateModal from './AiGenerateModal';
import ContentPickerModal from './ContentPickerModal';
import TemplateSwapPanel from './TemplateSwapPanel';
import type { BulletRef, SkillRef, RecipeV2, ResolvedV2, ThemeSettings } from './types';

interface Props {
  recipeId: number;
  recipeName: string;
  recipe: RecipeV2;
  resolved: ResolvedV2;
  theme: ThemeSettings;
  templateId: number;
  templateName: string;
}

function isSectionRecipe(recipe: Record<string, any>): boolean {
  const sectionKeys = new Set(['HEADER', 'HEADLINE', 'SUMMARY', 'HIGHLIGHTS', 'EXPERIENCE',
    'CERTIFICATIONS', 'EDUCATION', 'SKILLS', 'ADDITIONAL_EXP']);
  return Object.keys(recipe).some(k => sectionKeys.has(k));
}

export default function ResumeEditor({ recipeId, recipeName, recipe: initialRecipe, resolved: initialResolved, theme: initialTheme, templateId, templateName }: Props) {
  const [recipe, setRecipe] = useState<RecipeV2>(initialRecipe);
  const [resolved, setResolved] = useState<ResolvedV2>(initialResolved);
  const [theme, setTheme] = useState<ThemeSettings>(initialTheme);
  const [saveState, setSaveState] = useState<'saved' | 'saving' | 'unsaved'>('saved');
  const [showTheme, setShowTheme] = useState(false);
  const [showAtsScore, setShowAtsScore] = useState(false);
  const [showAiReview, setShowAiReview] = useState(false);
  const [showBestPicks, setShowBestPicks] = useState(false);
  const [showSwapPanel, setShowSwapPanel] = useState(false);
  const [pickerState, setPickerState] = useState<{
    mode: 'bullets' | 'jobs' | 'summaries';
    jobIndex?: number;
    filterEmployer?: string;
  } | null>(null);
  const [generateState, setGenerateState] = useState<{
    slotType: string;
    jobId?: number;
    jobIndex?: number;
    existingBullets?: string[];
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

  const queryClient = useQueryClient();

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
      const blob = await recipeGenerateDocx(recipeId);
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
        onAiReview={() => setShowAiReview(true)}
        onAtsScore={() => setShowAtsScore(true)}
        onBestPicks={() => setShowBestPicks(true)}
        onToggleTheme={() => setShowTheme(!showTheme)}
        onAiGenerate={() => setGenerateState({ slotType: 'bullet' })}
        generating={generateMutation.isPending}
      />

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
            await queryClient.invalidateQueries({ queryKey: ['recipe-builder', recipeId] });
            await queryClient.invalidateQueries({ queryKey: ['templates'] });
            setShowSwapPanel(false);
          }}
          onClose={() => setShowSwapPanel(false)}
        />
      )}

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 overflow-y-auto p-8 max-w-4xl mx-auto" style={{ background: '#e5e7eb', ...themeStyle } as React.CSSProperties}>
          <div style={{
            background: '#fff', color: '#111', boxShadow: '0 2px 16px rgba(0,0,0,0.12)',
            borderRadius: 4, padding: '48px 56px', minHeight: '11in', maxWidth: 850,
            margin: '0 auto', fontFamily: 'var(--font-family)',
            fontSize: 'var(--font-size-body, 10.5pt)', lineHeight: 1.5,
          }}>

            {/* Header — render if recipe has header ref OR resolved header data (v1 recipes) */}
            {(recipe.header || resolved.header) && (
              <HeaderBlock data={resolved.header ?? {}} headerId={recipe.header?.id ?? 1} themeVars={themeStyle} />
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

            {/* Experience — render if recipe has experience OR resolved has it (v1 recipes) */}
            {(recipe.experience || (resolved.experience && resolved.experience.length > 0)) && (
              <ExperienceBlock
                jobs={recipe.experience ?? (resolved.experience ?? []).map((rj: any) => ({
                  ref: 'career_history',
                  id: rj.id,
                  bullets: (rj.bullets ?? []).map((b: string) => ({ literal: b })),
                }))}
                resolvedJobs={resolved.experience ?? []}
                recipeId={recipeId}
                onRecipeChange={(exp) => updateRecipe(r => ({ ...r, experience: exp }))}
                onPickBullet={(jobIdx) => setPickerState({
                  mode: 'bullets',
                  jobIndex: jobIdx,
                  filterEmployer: resolved.experience?.[jobIdx]?.employer,
                })}
                onAddJob={() => setPickerState({ mode: 'jobs' })}
                onAiGenerate={(jobIdx) => {
                  const job = recipe.experience?.[jobIdx];
                  const rJob = resolved.experience?.[jobIdx];
                  setGenerateState({
                    slotType: 'bullet',
                    jobId: job?.id,
                    jobIndex: jobIdx,
                    existingBullets: rJob?.bullets ?? [],
                  });
                }}
              />
            )}

            {/* Skills — render if recipe has skills OR resolved has them (v1 recipes) */}
            {(recipe.skills || (resolved.skills && resolved.skills.length > 0)) && (
              <SkillTagsBlock
                skillRefs={recipe.skills ?? [{ literal: (resolved.skills ?? []).join(', ') }]}
                resolvedSkills={resolved.skills ?? []}
                onUpdate={(skills) => updateRecipe(r => ({ ...r, skills }))}
              />
            )}

            {/* Education */}
            <LiteralListBlock
              label="Education"
              slotKey="education"
              items={resolved.education ?? []}
              onUpdate={(_, items) => {
                if (isSectionRecipe(recipe)) return;
                updateRecipe(r => ({
                  ...r, education: items.map(text => ({ literal: text })),
                }));
              }}
            />

            {/* Certifications */}
            <LiteralListBlock
              label="Certifications"
              slotKey="certifications"
              items={resolved.certifications ?? []}
              onUpdate={(_, items) => {
                if (isSectionRecipe(recipe)) return;
                updateRecipe(r => ({
                  ...r, certifications: items.map(text => ({ literal: text })),
                }));
              }}
            />

            {/* Additional Experience */}
            {resolved.additional_experience && resolved.additional_experience.length > 0 && (
              <LiteralListBlock
                label="Additional Experience"
                slotKey="additional_experience"
                items={resolved.additional_experience}
                onUpdate={(_, items) => {
                  if (isSectionRecipe(recipe)) return;
                  updateRecipe(r => ({
                    ...r, additional_experience: items.map(text => ({ literal: text })),
                  }));
                }}
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
              if (isSectionRecipe(recipe)) {
                // Section format: store as table references under UPPERCASE keys
                updateRecipe(r => ({
                  ...r,
                  HEADLINE: { table: 'summary_variants', id: item.id, column: 'headline' },
                  SUMMARY: { table: 'summary_variants', id: item.id, column: 'text' },
                }));
              } else {
                updateRecipe(r => ({ ...r, summary: { ref: 'summary_variants', id: item.id } }));
              }
            }
            setPickerState(null);
          }}
          onClose={() => setPickerState(null)}
        />
      )}
      {showAtsScore && (
        <AtsScoreModal
          recipeId={recipeId}
          applicationId={recipe?.application_id}
          onClose={() => setShowAtsScore(false)}
        />
      )}
      {showAiReview && (
        <AiReviewPanel
          recipeId={recipeId}
          onClose={() => setShowAiReview(false)}
        />
      )}
      {showBestPicks && (
        <BestPicksPanel
          recipeId={recipeId}
          applicationId={recipe?.application_id}
          onClose={() => setShowBestPicks(false)}
        />
      )}
      {generateState && (
        <AiGenerateModal
          recipeId={recipeId}
          slotType={generateState.slotType}
          jobId={generateState.jobId}
          existingBullets={generateState.existingBullets}
          onSelect={(text) => {
            if (generateState.slotType === 'bullet' && generateState.jobIndex != null) {
              updateRecipe(r => {
                const exp = [...(r.experience ?? [])];
                exp[generateState.jobIndex!] = {
                  ...exp[generateState.jobIndex!],
                  bullets: [...exp[generateState.jobIndex!].bullets, { literal: text }],
                };
                return { ...r, experience: exp };
              });
            } else if (generateState.slotType === 'summary') {
              updateRecipe(r => ({ ...r, summary: { literal: text } }));
            } else if (generateState.slotType === 'highlight') {
              updateRecipe(r => ({
                ...r,
                highlights: [...(r.highlights ?? []), { literal: text }],
              }));
            } else if (generateState.slotType === 'bullet') {
              // Generic bullet from toolbar (no job context) - add as highlight
              updateRecipe(r => ({
                ...r,
                highlights: [...(r.highlights ?? []), { literal: text }],
              }));
            }
            setGenerateState(null);
          }}
          onClose={() => setGenerateState(null)}
        />
      )}
    </div>
  );
}
