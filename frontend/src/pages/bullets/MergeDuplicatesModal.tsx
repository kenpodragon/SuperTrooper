import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';

// API response shapes
interface CompanyDuplicate {
  group: number[];
  names: string[];
}
interface RoleDuplicate {
  employer: string;
  group: number[];
  titles: string[];
}
interface DuplicatesData {
  company_duplicates: CompanyDuplicate[];
  role_duplicates: RoleDuplicate[];
}

// A staged merge operation (not yet committed)
interface StagedMerge {
  keep_id: number;
  merge_ids: number[];
  new_employer?: string;
  new_title?: string;
  label: string; // human-readable description
}

interface CareerJob {
  id: number;
  employer: string;
  title: string;
  start_date?: string | null;
  end_date?: string | null;
}

type WizardStep = 'choose' | 'automatic' | 'manual' | 'saving';

interface MergeDuplicatesModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: () => void;
}

export default function MergeDuplicatesModal({ isOpen, onClose, onComplete }: MergeDuplicatesModalProps) {
  const [step, setStep] = useState<WizardStep>('choose');
  const [stagedMerges, setStagedMerges] = useState<StagedMerge[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveProgress, setSaveProgress] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Auto mode state
  const [autoData, setAutoData] = useState<DuplicatesData | null>(null);
  const [autoLoading, setAutoLoading] = useState(false);
  const [autoSelections, setAutoSelections] = useState<Record<string, number>>({});
  const [autoSkipped, setAutoSkipped] = useState<Set<string>>(new Set());

  // Manual mode state
  const [manualChecked, setManualChecked] = useState<Set<number>>(new Set());
  const [manualSearch, setManualSearch] = useState('');

  // Fetch all jobs for manual mode
  const { data: allJobs = [] } = useQuery<CareerJob[]>({
    queryKey: ['career-history'],
    queryFn: () => api.get('/career-history?limit=500'),
    enabled: isOpen,
  });

  // Group jobs by employer for manual mode
  const jobsByEmployer = useMemo(() => {
    const groups: Record<string, CareerJob[]> = {};
    for (const job of allJobs) {
      const key = job.employer || 'Unknown';
      if (!groups[key]) groups[key] = [];
      groups[key].push(job);
    }
    return Object.entries(groups)
      .map(([employer, jobs]) => ({ employer, jobs: jobs.sort((a, b) => (b.start_date || '').localeCompare(a.start_date || '')) }))
      .sort((a, b) => a.employer.localeCompare(b.employer));
  }, [allJobs]);

  const filteredEmployers = useMemo(() => {
    if (!manualSearch.trim()) return jobsByEmployer;
    const q = manualSearch.toLowerCase();
    return jobsByEmployer.filter(
      (g) => g.employer.toLowerCase().includes(q) || g.jobs.some((j) => j.title.toLowerCase().includes(q))
    );
  }, [jobsByEmployer, manualSearch]);

  if (!isOpen) return null;

  // --- Automatic mode ---
  const loadAutomatic = async () => {
    setAutoLoading(true);
    setError(null);
    try {
      const data = await api.get<DuplicatesData>('/career-history/duplicates');
      setAutoData(data);
      setAutoSelections({});
      setAutoSkipped(new Set());
      setStep('automatic');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAutoLoading(false);
    }
  };

  const stageAutoMerge = (type: 'company' | 'role', idx: number) => {
    if (!autoData) return;
    const key = `${type}-${idx}`;

    if (type === 'company') {
      const dup = autoData.company_duplicates[idx];
      const selectedName = dup.names[autoSelections[key] ?? 0];
      const keepId = dup.group[0];
      const mergeIds = dup.group.slice(1);
      setStagedMerges((prev) => [...prev, {
        keep_id: keepId,
        merge_ids: mergeIds,
        new_employer: selectedName,
        label: `Merge companies: ${dup.names.map((n) => `"${n}"`).join(' + ')} → "${selectedName}"`,
      }]);
    } else {
      const dup = autoData.role_duplicates[idx];
      const selectedIdx = autoSelections[key] ?? 0;
      const keepId = dup.group[selectedIdx];
      const mergeIds = dup.group.filter((_, i) => i !== selectedIdx);
      const keepTitle = dup.titles[selectedIdx];
      setStagedMerges((prev) => [...prev, {
        keep_id: keepId,
        merge_ids: mergeIds,
        new_title: keepTitle,
        label: `Merge roles at "${dup.employer}": ${dup.titles.map((t) => `"${t}"`).join(' + ')} → "${keepTitle}"`,
      }]);
    }
    setAutoSkipped((prev) => new Set(prev).add(key));
  };

  const skipAuto = (type: string, idx: number) => {
    setAutoSkipped((prev) => new Set(prev).add(`${type}-${idx}`));
  };

  // --- Manual mode ---
  const toggleManualCheck = (id: number) => {
    setManualChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const stageManualMerge = () => {
    const ids = Array.from(manualChecked);
    if (ids.length < 2) { alert('Select at least 2 items to merge.'); return; }

    const jobs = ids.map((id) => allJobs.find((j) => j.id === id)).filter(Boolean) as CareerJob[];
    const keepId = ids[0];
    const mergeIds = ids.slice(1);
    const keepJob = jobs[0];

    // If all same employer, this is a role merge
    const sameEmployer = jobs.every((j) => j.employer === jobs[0].employer);

    const label = sameEmployer
      ? `Merge roles at "${keepJob.employer}": ${jobs.map((j) => `"${j.title}"`).join(' + ')}`
      : `Merge: ${jobs.map((j) => `"${j.employer} - ${j.title}"`).join(' + ')}`;

    const newEmployer = sameEmployer ? undefined : prompt('Company name for the merged entry:', keepJob.employer) || undefined;
    const newTitle = prompt('Title for the merged entry:', keepJob.title);
    if (newTitle === null) return; // cancelled

    setStagedMerges((prev) => [...prev, {
      keep_id: keepId,
      merge_ids: mergeIds,
      new_employer: newEmployer,
      new_title: newTitle || undefined,
      label,
    }]);
    setManualChecked(new Set());
  };

  const removeStagedMerge = (idx: number) => {
    setStagedMerges((prev) => prev.filter((_, i) => i !== idx));
  };

  // --- Save all staged merges ---
  const saveAll = async () => {
    if (stagedMerges.length === 0) { alert('No merges staged.'); return; }
    setSaving(true);
    setError(null);

    for (let i = 0; i < stagedMerges.length; i++) {
      const merge = stagedMerges[i];
      setSaveProgress(`Executing merge ${i + 1} of ${stagedMerges.length}...`);
      try {
        await api.post('/career-history/merge', {
          keep_id: merge.keep_id,
          merge_ids: merge.merge_ids,
          new_employer: merge.new_employer,
          new_title: merge.new_title,
        });
      } catch (e) {
        setError(`Merge ${i + 1} failed: ${(e as Error).message}. ${i} of ${stagedMerges.length} completed.`);
        setSaving(false);
        return;
      }
    }

    setSaveProgress('All merges complete!');
    setSaving(false);
    onComplete();
  };

  const handleCancel = () => {
    if (stagedMerges.length > 0 && !window.confirm('Discard all staged merges?')) return;
    setStagedMerges([]);
    setStep('choose');
    setAutoData(null);
    setManualChecked(new Set());
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-gray-900 border border-gray-700 rounded-lg shadow-xl max-w-3xl w-full max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-gray-100">
            {step === 'choose' && 'Merge Duplicates'}
            {step === 'automatic' && 'Automatic — Detected Duplicates'}
            {step === 'manual' && 'Manual — Select Items to Merge'}
          </h2>
          <button onClick={handleCancel} className="text-gray-500 hover:text-gray-300 text-xl">&times;</button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {error && (
            <div className="text-sm text-red-400 bg-red-900/20 rounded px-3 py-2 mb-4">{error}</div>
          )}

          {/* Step 1: Choose mode */}
          {step === 'choose' && (
            <div className="space-y-4">
              <p className="text-sm text-gray-400">How would you like to find duplicates?</p>
              <div className="grid grid-cols-2 gap-4">
                <button
                  onClick={loadAutomatic}
                  disabled={autoLoading}
                  className="border border-gray-600 rounded-lg p-6 text-left hover:border-blue-500 hover:bg-blue-900/10 transition-colors"
                >
                  <div className="text-lg mb-2">🔍 Automatic</div>
                  <div className="text-sm text-gray-400">
                    Scan for similar company names and duplicate roles using fuzzy matching. Review detected matches.
                  </div>
                  {autoLoading && <div className="text-xs text-blue-400 mt-2">Scanning...</div>}
                </button>
                <button
                  onClick={() => setStep('manual')}
                  className="border border-gray-600 rounded-lg p-6 text-left hover:border-yellow-500 hover:bg-yellow-900/10 transition-colors"
                >
                  <div className="text-lg mb-2">✋ Manual</div>
                  <div className="text-sm text-gray-400">
                    Browse all companies and roles. Checkbox the ones you want to merge together.
                  </div>
                </button>
              </div>
            </div>
          )}

          {/* Automatic mode */}
          {step === 'automatic' && autoData && (
            <div className="space-y-6">
              {(!autoData.company_duplicates?.length && !autoData.role_duplicates?.length) && (
                <div className="text-center text-gray-500 py-8">
                  No duplicates detected. Try Manual mode for more control.
                  <button onClick={() => setStep('manual')} className="block mx-auto mt-2 text-blue-400 hover:text-blue-300 text-sm">
                    Switch to Manual →
                  </button>
                </div>
              )}

              {autoData.company_duplicates?.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-300 mb-3">Company Names</h3>
                  <div className="space-y-3">
                    {autoData.company_duplicates.map((dup, gi) => {
                      const key = `company-${gi}`;
                      const isDone = autoSkipped.has(key);
                      return (
                        <div key={gi} className={`border border-gray-700 rounded-lg p-3 ${isDone ? 'opacity-40' : ''}`}>
                          <div className="text-xs text-gray-500 mb-2">
                            {dup.names.map((n) => `"${n}"`).join(' / ')}
                          </div>
                          {!isDone && (
                            <>
                              <div className="space-y-1">
                                {dup.names.map((name, ni) => (
                                  <label key={ni} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                                    <input
                                      type="radio"
                                      name={key}
                                      checked={(autoSelections[key] ?? 0) === ni}
                                      onChange={() => setAutoSelections((prev) => ({ ...prev, [key]: ni }))}
                                      className="accent-blue-500"
                                    />
                                    Keep "{name}"
                                  </label>
                                ))}
                              </div>
                              <div className="flex gap-2 mt-2">
                                <button onClick={() => stageAutoMerge('company', gi)} className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded">
                                  Stage Merge
                                </button>
                                <button onClick={() => skipAuto('company', gi)} className="px-3 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded">
                                  Skip
                                </button>
                              </div>
                            </>
                          )}
                          {isDone && <div className="text-xs text-green-400">Staged ✓</div>}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {autoData.role_duplicates?.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-300 mb-3">Duplicate Roles</h3>
                  <div className="space-y-3">
                    {autoData.role_duplicates.map((dup, gi) => {
                      const key = `role-${gi}`;
                      const isDone = autoSkipped.has(key);
                      return (
                        <div key={gi} className={`border border-gray-700 rounded-lg p-3 ${isDone ? 'opacity-40' : ''}`}>
                          <div className="text-xs text-gray-500 mb-2">At "{dup.employer}":</div>
                          {!isDone && (
                            <>
                              <div className="space-y-1">
                                {dup.titles.map((title, ti) => (
                                  <label key={ti} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                                    <input
                                      type="radio"
                                      name={key}
                                      checked={(autoSelections[key] ?? 0) === ti}
                                      onChange={() => setAutoSelections((prev) => ({ ...prev, [key]: ti }))}
                                      className="accent-blue-500"
                                    />
                                    "{title}"
                                  </label>
                                ))}
                              </div>
                              <div className="flex gap-2 mt-2">
                                <button onClick={() => stageAutoMerge('role', gi)} className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded">
                                  Stage Merge
                                </button>
                                <button onClick={() => skipAuto('role', gi)} className="px-3 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded">
                                  Skip
                                </button>
                              </div>
                            </>
                          )}
                          {isDone && <div className="text-xs text-green-400">Staged ✓</div>}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              <div className="pt-2">
                <button onClick={() => setStep('manual')} className="text-sm text-blue-400 hover:text-blue-300">
                  Switch to Manual mode to find more →
                </button>
              </div>
            </div>
          )}

          {/* Manual mode */}
          {step === 'manual' && (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={manualSearch}
                  onChange={(e) => setManualSearch(e.target.value)}
                  placeholder="Search companies or roles..."
                  className="flex-1 bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-100 placeholder-gray-500 focus:border-blue-400 focus:outline-none"
                />
                <button
                  onClick={stageManualMerge}
                  disabled={manualChecked.size < 2}
                  className="px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-white text-xs rounded disabled:opacity-50 whitespace-nowrap"
                >
                  Merge {manualChecked.size} Selected
                </button>
              </div>

              <div className="text-xs text-gray-500 mb-2">
                Check 2+ items, click "Merge Selected". Repeat for more groups. Nothing saves until you click Save.
              </div>

              <div className="max-h-[40vh] overflow-y-auto border border-gray-700 rounded-lg">
                {filteredEmployers.map((group) => (
                  <div key={group.employer} className="border-b border-gray-800 last:border-b-0">
                    <div className="px-3 py-2 bg-gray-800/50 text-sm font-semibold text-gray-300">
                      {group.employer}
                    </div>
                    {group.jobs.map((job) => {
                      // Hide jobs that are already staged for merge (as merge_ids)
                      const isStaged = stagedMerges.some((m) => m.merge_ids.includes(job.id));
                      if (isStaged) return null;
                      return (
                        <label
                          key={job.id}
                          className={`flex items-center gap-3 px-4 py-2 cursor-pointer hover:bg-gray-800/30 ${
                            manualChecked.has(job.id) ? 'bg-yellow-900/20' : ''
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={manualChecked.has(job.id)}
                            onChange={() => toggleManualCheck(job.id)}
                            className="accent-yellow-400 w-4 h-4 shrink-0"
                          />
                          <div className="flex-1 min-w-0">
                            <span className="text-sm text-gray-200">{job.title}</span>
                          </div>
                          <span className="text-xs text-gray-500 shrink-0">
                            {job.start_date?.match(/(\d{4})/)?.[1] || ''}
                            {job.end_date ? `–${job.end_date.match(/(\d{4})/)?.[1] || ''}` : '–now'}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                ))}
              </div>

              {autoData && (
                <button onClick={() => setStep('automatic')} className="text-sm text-blue-400 hover:text-blue-300">
                  ← Back to Automatic results
                </button>
              )}
            </div>
          )}
        </div>

        {/* Staged merges panel + footer */}
        <div className="border-t border-gray-700">
          {stagedMerges.length > 0 && (
            <div className="px-5 py-3 bg-gray-800/50 max-h-[150px] overflow-y-auto">
              <div className="text-xs font-semibold text-yellow-400 mb-2">
                Staged Merges ({stagedMerges.length})
              </div>
              {stagedMerges.map((merge, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-gray-300 py-1">
                  <span className="flex-1 truncate">{merge.label}</span>
                  <button
                    onClick={() => removeStagedMerge(i)}
                    className="text-red-400 hover:text-red-300 shrink-0"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center justify-between px-5 py-3">
            <div className="text-sm text-gray-500">
              {saving && saveProgress}
            </div>
            <div className="flex gap-2">
              {step !== 'choose' && !saving && (
                <button
                  onClick={() => { setStep('choose'); setAutoData(null); }}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded"
                >
                  ← Back
                </button>
              )}
              <button
                onClick={handleCancel}
                disabled={saving}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded disabled:opacity-50"
              >
                Cancel
              </button>
              {stagedMerges.length > 0 && (
                <button
                  onClick={saveAll}
                  disabled={saving}
                  className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm rounded disabled:opacity-50"
                >
                  {saving ? 'Saving...' : `Save & Done (${stagedMerges.length} merges)`}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
