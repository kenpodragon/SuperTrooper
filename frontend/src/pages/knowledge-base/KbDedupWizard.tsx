import { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';
import DedupStepAutoMerge from './DedupStepAutoMerge';
import DedupStepReview from './DedupStepReview';
import DedupStepJunk from './DedupStepJunk';
import { SummaryRoleTypeEditor } from './SummaryRoleTypeEditor';
import { SummarySplitReview } from './SummarySplitReview';

// ---- Types ---------------------------------------------------------------

interface ScanResult {
  auto_merge: any[];
  needs_review: any[];
  junk: any[];
  count: number;
  employer_merge?: any[];
  role_merge?: any[];
  mixed_content?: any[];
  role_type_suggestions?: any[];
}

type SubStage =
  | 'scanning'
  | 'auto_merge'
  | 'review'
  | 'junk'
  | 'summary_role_types'
  | 'summary_split'
  | 'skipped'
  | 'done';

// ---- Constants -----------------------------------------------------------

const ENTITY_STEPS = [
  { key: 'career_history', label: 'Career History' },
  { key: 'bullets',        label: 'Bullets' },
  { key: 'skills',         label: 'Skills' },
  { key: 'education',      label: 'Education' },
  { key: 'certifications', label: 'Certifications' },
  { key: 'summaries',      label: 'Summaries' },
  { key: 'languages',      label: 'Languages' },
  { key: 'references',     label: 'References' },
] as const;

type EntityKey = (typeof ENTITY_STEPS)[number]['key'];

// ---- Helpers -------------------------------------------------------------

function firstSubStageFor(entityKey: EntityKey, result: ScanResult): SubStage {
  const isEmpty =
    result.auto_merge.length === 0 &&
    result.needs_review.length === 0 &&
    result.junk.length === 0 &&
    (result.employer_merge?.length ?? 0) === 0 &&
    (result.role_merge?.length ?? 0) === 0 &&
    (result.mixed_content?.length ?? 0) === 0 &&
    (result.role_type_suggestions?.length ?? 0) === 0;

  if (isEmpty) return 'skipped';

  if (entityKey === 'summaries') {
    return 'summary_role_types';
  }

  if (result.auto_merge.length > 0) return 'auto_merge';
  if (result.needs_review.length > 0) return 'review';
  if (result.junk.length > 0) return 'junk';
  return 'skipped';
}

function nextSubStage(
  current: SubStage,
  result: ScanResult,
  entityKey: EntityKey,
): SubStage {
  switch (current) {
    case 'summary_role_types':
      if ((result.mixed_content?.length ?? 0) > 0) return 'summary_split';
      if (result.auto_merge.length > 0) return 'auto_merge';
      if (result.needs_review.length > 0) return 'review';
      if (result.junk.length > 0) return 'junk';
      return 'done';

    case 'summary_split':
      if (result.auto_merge.length > 0) return 'auto_merge';
      if (result.needs_review.length > 0) return 'review';
      if (result.junk.length > 0) return 'junk';
      return 'done';

    case 'auto_merge':
      if (result.needs_review.length > 0) return 'review';
      if (result.junk.length > 0) return 'junk';
      return 'done';

    case 'review':
      if (result.junk.length > 0) return 'junk';
      return 'done';

    case 'junk':
      return 'done';

    default:
      return 'done';
  }
}

// ---- Props ---------------------------------------------------------------

interface KbDedupWizardProps {
  isOpen: boolean;
  onClose: () => void;
}

// ---- Component -----------------------------------------------------------

export default function KbDedupWizard({ isOpen, onClose }: KbDedupWizardProps) {
  const [entityIdx, setEntityIdx]           = useState(0);
  const [subStage, setSubStage]             = useState<SubStage>('scanning');
  const [scanResult, setScanResult]         = useState<ScanResult | null>(null);
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());

  const scanMutation = useMutation({
    mutationFn: (entityType: string) =>
      api.post<ScanResult>('/kb/dedup/scan', { entity_type: entityType, use_ai: true }),
    onSuccess: (result) => {
      setScanResult(result);
      const entityKey = ENTITY_STEPS[entityIdx].key;
      setSubStage(firstSubStageFor(entityKey, result));
    },
  });

  // Trigger scan whenever the entity index changes
  useEffect(() => {
    if (!isOpen) return;
    setSubStage('scanning');
    setScanResult(null);
    scanMutation.mutate(ENTITY_STEPS[entityIdx].key);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityIdx, isOpen]);

  // Reset when wizard opens
  useEffect(() => {
    if (isOpen) {
      setEntityIdx(0);
      setSubStage('scanning');
      setScanResult(null);
      setCompletedSteps(new Set());
    }
  }, [isOpen]);

  function advanceSubStage() {
    if (!scanResult) return;
    const entityKey = ENTITY_STEPS[entityIdx].key;
    const next = nextSubStage(subStage, scanResult, entityKey);
    if (next === 'done') {
      advanceEntity();
    } else {
      setSubStage(next);
    }
  }

  function advanceEntity() {
    setCompletedSteps((prev) => new Set(prev).add(entityIdx));
    const nextIdx = entityIdx + 1;
    if (nextIdx >= ENTITY_STEPS.length) {
      onClose();
    } else {
      setEntityIdx(nextIdx);
    }
  }

  if (!isOpen) return null;

  const currentEntity = ENTITY_STEPS[entityIdx];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="relative flex h-[90vh] w-full max-w-4xl flex-col rounded-xl bg-gray-900 shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-700 px-6 py-4">
          <h2 className="text-lg font-semibold text-white">Clean Up Knowledge Base</h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-gray-400 hover:bg-gray-700 hover:text-white transition-colors"
            aria-label="Close"
          >
            <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>

        {/* Progress Bar */}
        <div className="border-b border-gray-700 px-6 py-4">
          <div className="flex items-center gap-1">
            {ENTITY_STEPS.map((step, idx) => {
              const isDone    = completedSteps.has(idx);
              const isCurrent = idx === entityIdx;
              const isFuture  = idx > entityIdx && !isDone;

              return (
                <div key={step.key} className="flex flex-1 flex-col items-center gap-1">
                  {/* Step dot */}
                  <div
                    className={[
                      'flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold transition-colors',
                      isDone    ? 'bg-green-500 text-white'  : '',
                      isCurrent ? 'bg-purple-600 text-white' : '',
                      isFuture  ? 'bg-gray-700 text-gray-400' : '',
                    ].join(' ')}
                  >
                    {isDone ? (
                      <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                    ) : (
                      idx + 1
                    )}
                  </div>
                  {/* Step label */}
                  <span
                    className={[
                      'text-center text-[10px] leading-tight',
                      isDone    ? 'text-green-400'  : '',
                      isCurrent ? 'text-purple-400' : '',
                      isFuture  ? 'text-gray-500'   : '',
                    ].join(' ')}
                  >
                    {step.label}
                  </span>
                  {/* Connector line (not on last) */}
                  {idx < ENTITY_STEPS.length - 1 && (
                    <div
                      className={[
                        'absolute hidden',
                      ].join(' ')}
                    />
                  )}
                </div>
              );
            })}
          </div>

          {/* Horizontal connector track */}
          <div className="relative mt-1 h-1 rounded-full bg-gray-700">
            <div
              className="h-1 rounded-full bg-purple-600 transition-all duration-300"
              style={{
                width: `${((completedSteps.size) / ENTITY_STEPS.length) * 100}%`,
              }}
            />
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {subStage === 'scanning' && (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-gray-400">
              <svg
                className="h-8 w-8 animate-spin text-purple-500"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              <p>Scanning {currentEntity.label}...</p>
              {scanMutation.isError && (
                <p className="text-red-400 text-sm">
                  {scanMutation.error instanceof Error
                    ? scanMutation.error.message
                    : 'Scan failed'}
                </p>
              )}
            </div>
          )}

          {subStage === 'skipped' && (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-gray-400">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-500/20">
                <svg className="h-6 w-6 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
              <p className="text-green-400 font-medium">{currentEntity.label} — Nothing to clean up</p>
              <button
                onClick={advanceEntity}
                className="mt-2 rounded-md bg-purple-600 px-5 py-2 text-sm text-white hover:bg-purple-500 transition-colors"
              >
                Next
              </button>
            </div>
          )}

          {subStage === 'auto_merge' && scanResult && (
            <DedupStepAutoMerge
              entityType={currentEntity.key}
              groups={scanResult.auto_merge}
              onComplete={advanceSubStage}
            />
          )}

          {subStage === 'review' && scanResult && (
            <DedupStepReview
              entityType={currentEntity.key}
              groups={scanResult.needs_review}
              onComplete={advanceSubStage}
            />
          )}

          {subStage === 'junk' && scanResult && (
            <DedupStepJunk
              entityType={currentEntity.key}
              items={scanResult.junk}
              onComplete={advanceSubStage}
            />
          )}

          {subStage === 'summary_role_types' && scanResult && (
            <SummaryRoleTypeEditor
              suggestions={scanResult.role_type_suggestions ?? []}
              onComplete={advanceSubStage}
            />
          )}

          {subStage === 'summary_split' && scanResult && (
            <SummarySplitReview
              mixedContent={scanResult.mixed_content ?? []}
              onComplete={advanceSubStage}
            />
          )}
        </div>

      </div>
    </div>
  );
}
