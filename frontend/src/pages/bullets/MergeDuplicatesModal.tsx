import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';

interface CompanyDuplicate { group: number[]; names: string[]; }
interface RoleDuplicate { employer: string; group: number[]; titles: string[]; }
interface DuplicatesData { company_duplicates: CompanyDuplicate[]; role_duplicates: RoleDuplicate[]; }

interface StagedMerge {
  keep_id: number;
  merge_ids: number[];
  new_employer?: string;
  new_title?: string;
  label: string;
}

interface CareerJob {
  id: number;
  employer: string;
  title: string;
  start_date?: string | null;
  end_date?: string | null;
}

type WizardStep = 'choose' | 'automatic' | 'manual-companies' | 'manual-roles';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onComplete: () => void;
}

export default function MergeDuplicatesModal({ isOpen, onClose, onComplete }: Props) {
  const [step, setStep] = useState<WizardStep>('choose');
  const [stagedMerges, setStagedMerges] = useState<StagedMerge[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveProgress, setSaveProgress] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Auto state
  const [autoData, setAutoData] = useState<DuplicatesData | null>(null);
  const [autoLoading, setAutoLoading] = useState(false);
  const [autoSelections, setAutoSelections] = useState<Record<string, number>>({});
  const [autoSkipped, setAutoSkipped] = useState<Set<string>>(new Set());

  // Manual company merge state
  const [companyChecked, setCompanyChecked] = useState<Set<string>>(new Set());
  const [companySearch, setCompanySearch] = useState('');

  // Manual role merge state
  const [roleChecked, setRoleChecked] = useState<Set<number>>(new Set());
  const [roleSearch, setRoleSearch] = useState('');

  const { data: allJobs = [] } = useQuery<CareerJob[]>({
    queryKey: ['career-history'],
    queryFn: () => api.get('/career-history?limit=500'),
    enabled: isOpen,
  });

  // Group jobs by employer
  const employerGroups = useMemo(() => {
    const groups: Record<string, CareerJob[]> = {};
    for (const job of allJobs) {
      const key = job.employer || 'Unknown';
      if (!groups[key]) groups[key] = [];
      groups[key].push(job);
    }
    return Object.entries(groups)
      .map(([employer, jobs]) => ({ employer, jobs }))
      .sort((a, b) => a.employer.localeCompare(b.employer));
  }, [allJobs]);

  const filteredCompanies = useMemo(() => {
    if (!companySearch.trim()) return employerGroups;
    const q = companySearch.toLowerCase();
    return employerGroups.filter((g) => g.employer.toLowerCase().includes(q));
  }, [employerGroups, companySearch]);

  // For role step: only show companies with 2+ roles (after company merges are staged)
  const companiesForRoles = useMemo(() => {
    if (!roleSearch.trim()) return employerGroups.filter((g) => g.jobs.length >= 2);
    const q = roleSearch.toLowerCase();
    return employerGroups.filter((g) => g.jobs.length >= 2 && (g.employer.toLowerCase().includes(q) || g.jobs.some((j) => j.title.toLowerCase().includes(q))));
  }, [employerGroups, roleSearch]);

  if (!isOpen) return null;

  const yearOf = (d?: string | null) => d?.match(/(\d{4})/)?.[1] || '';

  // --- Auto mode ---
  const loadAutomatic = async () => {
    setAutoLoading(true); setError(null);
    try {
      const data = await api.get<DuplicatesData>('/career-history/duplicates');
      setAutoData(data); setAutoSelections({}); setAutoSkipped(new Set());
      setStep('automatic');
    } catch (e) { setError((e as Error).message); }
    finally { setAutoLoading(false); }
  };

  const stageAutoMerge = (type: 'company' | 'role', idx: number) => {
    if (!autoData) return;
    const key = `${type}-${idx}`;
    if (type === 'company') {
      const dup = autoData.company_duplicates[idx];
      const keepName = dup.names[autoSelections[key] ?? 0];
      setStagedMerges((prev) => [...prev, {
        keep_id: dup.group[0], merge_ids: dup.group.slice(1), new_employer: keepName,
        label: `Companies: ${dup.names.map((n) => `"${n}"`).join(' + ')} → "${keepName}"`,
      }]);
    } else {
      const dup = autoData.role_duplicates[idx];
      const si = autoSelections[key] ?? 0;
      setStagedMerges((prev) => [...prev, {
        keep_id: dup.group[si], merge_ids: dup.group.filter((_, i) => i !== si),
        new_title: dup.titles[si],
        label: `Roles at "${dup.employer}": ${dup.titles.map((t) => `"${t}"`).join(' + ')} → "${dup.titles[si]}"`,
      }]);
    }
    setAutoSkipped((prev) => new Set(prev).add(key));
  };

  // --- Manual company merge ---
  const toggleCompany = (employer: string) => {
    setCompanyChecked((prev) => {
      const next = new Set(prev);
      if (next.has(employer)) next.delete(employer); else next.add(employer);
      return next;
    });
  };

  const stageCompanyMerge = () => {
    const names = Array.from(companyChecked);
    if (names.length < 2) { alert('Select at least 2 companies to merge.'); return; }

    const keepName = prompt(`Which company name to keep?\n\n${names.map((n, i) => `  ${i + 1}. ${n}`).join('\n')}\n\nType the name:`, names[0]);
    if (!keepName) return;

    // Find all job IDs across selected companies
    const allIds: number[] = [];
    for (const name of names) {
      const group = employerGroups.find((g) => g.employer === name);
      if (group) allIds.push(...group.jobs.map((j) => j.id));
    }
    if (allIds.length < 2) return;

    setStagedMerges((prev) => [...prev, {
      keep_id: allIds[0], merge_ids: allIds.slice(1), new_employer: keepName.trim(),
      label: `Companies: ${names.map((n) => `"${n}"`).join(' + ')} → "${keepName.trim()}"`,
    }]);
    setCompanyChecked(new Set());
  };

  // --- Manual role merge ---
  const toggleRole = (id: number) => {
    setRoleChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const stageRoleMerge = () => {
    const ids = Array.from(roleChecked);
    if (ids.length < 2) { alert('Select at least 2 roles to merge.'); return; }

    const jobs = ids.map((id) => allJobs.find((j) => j.id === id)).filter(Boolean) as CareerJob[];
    const keepTitle = prompt(`Title for the merged role:`, jobs[0].title);
    if (keepTitle === null) return;

    setStagedMerges((prev) => [...prev, {
      keep_id: ids[0], merge_ids: ids.slice(1), new_title: keepTitle || undefined,
      label: `Roles: ${jobs.map((j) => `"${j.title}"`).join(' + ')} → "${keepTitle || jobs[0].title}"`,
    }]);
    setRoleChecked(new Set());
  };

  const removeStagedMerge = (idx: number) => setStagedMerges((prev) => prev.filter((_, i) => i !== idx));

  // --- Save ---
  const saveAll = async () => {
    if (stagedMerges.length === 0) { alert('No merges staged.'); return; }
    setSaving(true); setError(null);
    for (let i = 0; i < stagedMerges.length; i++) {
      setSaveProgress(`Executing ${i + 1} of ${stagedMerges.length}...`);
      try {
        await api.post('/career-history/merge', {
          keep_id: stagedMerges[i].keep_id,
          merge_ids: stagedMerges[i].merge_ids,
          new_employer: stagedMerges[i].new_employer,
          new_title: stagedMerges[i].new_title,
        });
      } catch (e) {
        setError(`Merge ${i + 1} failed: ${(e as Error).message}`);
        setSaving(false); return;
      }
    }
    setSaving(false); onComplete();
  };

  const handleCancel = () => {
    if (stagedMerges.length > 0 && !window.confirm('Discard all staged merges?')) return;
    setStagedMerges([]); setStep('choose'); setAutoData(null);
    setCompanyChecked(new Set()); setRoleChecked(new Set());
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
            {step === 'manual-companies' && 'Manual Step 1 — Merge Companies'}
            {step === 'manual-roles' && 'Manual Step 2 — Merge Roles'}
          </h2>
          <button onClick={handleCancel} className="text-gray-500 hover:text-gray-300 text-xl">&times;</button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {error && <div className="text-sm text-red-400 bg-red-900/20 rounded px-3 py-2 mb-4">{error}</div>}

          {/* Choose mode */}
          {step === 'choose' && (
            <div className="space-y-4">
              <p className="text-sm text-gray-400">How would you like to find duplicates?</p>
              <div className="grid grid-cols-2 gap-4">
                <button onClick={loadAutomatic} disabled={autoLoading}
                  className="border border-gray-600 rounded-lg p-6 text-left hover:border-blue-500 hover:bg-blue-900/10 transition-colors">
                  <div className="text-lg mb-2">🔍 Automatic</div>
                  <div className="text-sm text-gray-400">Scan for similar company names and duplicate roles using fuzzy matching.</div>
                  {autoLoading && <div className="text-xs text-blue-400 mt-2">Scanning...</div>}
                </button>
                <button onClick={() => setStep('manual-companies')}
                  className="border border-gray-600 rounded-lg p-6 text-left hover:border-yellow-500 hover:bg-yellow-900/10 transition-colors">
                  <div className="text-lg mb-2">✋ Manual</div>
                  <div className="text-sm text-gray-400">Step 1: merge companies. Step 2: merge roles within companies.</div>
                </button>
              </div>
            </div>
          )}

          {/* Automatic */}
          {step === 'automatic' && autoData && (
            <div className="space-y-6">
              {(!autoData.company_duplicates?.length && !autoData.role_duplicates?.length) && (
                <div className="text-center text-gray-500 py-8">
                  No duplicates detected. Try Manual mode.
                  <button onClick={() => setStep('manual-companies')} className="block mx-auto mt-2 text-blue-400 text-sm">Switch to Manual →</button>
                </div>
              )}
              {autoData.company_duplicates?.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-300 mb-3">Company Names</h3>
                  <div className="space-y-3">
                    {autoData.company_duplicates.map((dup, gi) => {
                      const key = `company-${gi}`;
                      const done = autoSkipped.has(key);
                      return (
                        <div key={gi} className={`border border-gray-700 rounded-lg p-3 ${done ? 'opacity-40' : ''}`}>
                          <div className="text-xs text-gray-500 mb-2">{dup.names.map((n) => `"${n}"`).join(' / ')}</div>
                          {!done && (
                            <>
                              <div className="space-y-1">
                                {dup.names.map((name, ni) => (
                                  <label key={ni} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                                    <input type="radio" name={key} checked={(autoSelections[key] ?? 0) === ni}
                                      onChange={() => setAutoSelections((p) => ({ ...p, [key]: ni }))} className="accent-blue-500" />
                                    Keep "{name}"
                                  </label>
                                ))}
                              </div>
                              <div className="flex gap-2 mt-2">
                                <button onClick={() => stageAutoMerge('company', gi)} className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded">Stage</button>
                                <button onClick={() => setAutoSkipped((p) => new Set(p).add(key))} className="px-3 py-1 bg-gray-700 text-gray-300 text-xs rounded">Skip</button>
                              </div>
                            </>
                          )}
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
                      const done = autoSkipped.has(key);
                      return (
                        <div key={gi} className={`border border-gray-700 rounded-lg p-3 ${done ? 'opacity-40' : ''}`}>
                          <div className="text-xs text-gray-500 mb-2">At "{dup.employer}":</div>
                          {!done && (
                            <>
                              <div className="space-y-1">
                                {dup.titles.map((title, ti) => (
                                  <label key={ti} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                                    <input type="radio" name={key} checked={(autoSelections[key] ?? 0) === ti}
                                      onChange={() => setAutoSelections((p) => ({ ...p, [key]: ti }))} className="accent-blue-500" />
                                    "{title}"
                                  </label>
                                ))}
                              </div>
                              <div className="flex gap-2 mt-2">
                                <button onClick={() => stageAutoMerge('role', gi)} className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded">Stage</button>
                                <button onClick={() => setAutoSkipped((p) => new Set(p).add(key))} className="px-3 py-1 bg-gray-700 text-gray-300 text-xs rounded">Skip</button>
                              </div>
                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              <button onClick={() => setStep('manual-companies')} className="text-sm text-blue-400 hover:text-blue-300">Switch to Manual →</button>
            </div>
          )}

          {/* Manual Step 1: Companies */}
          {step === 'manual-companies' && (
            <div className="space-y-3">
              <p className="text-xs text-gray-500">Check 2+ companies with the same/similar name, click "Merge Selected Companies". Repeat as needed, then proceed to Step 2.</p>
              <div className="flex items-center gap-3">
                <input type="text" value={companySearch} onChange={(e) => setCompanySearch(e.target.value)}
                  placeholder="Search companies..." className="flex-1 bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-100 placeholder-gray-500 focus:border-blue-400 focus:outline-none" />
                <button onClick={stageCompanyMerge} disabled={companyChecked.size < 2}
                  className="px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-white text-xs rounded disabled:opacity-50 whitespace-nowrap">
                  Merge {companyChecked.size} Companies
                </button>
              </div>
              <div className="max-h-[45vh] overflow-y-auto border border-gray-700 rounded-lg">
                {filteredCompanies.map((group) => (
                  <label key={group.employer}
                    className={`flex items-center gap-3 px-4 py-2.5 border-b border-gray-800 last:border-b-0 cursor-pointer hover:bg-gray-800/30 ${
                      companyChecked.has(group.employer) ? 'bg-yellow-900/20' : ''
                    }`}>
                    <input type="checkbox" checked={companyChecked.has(group.employer)}
                      onChange={() => toggleCompany(group.employer)} className="accent-yellow-400 w-4 h-4 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-gray-200">{group.employer}</span>
                      <span className="text-xs text-gray-500 ml-2">{group.jobs.length} role{group.jobs.length > 1 ? 's' : ''}</span>
                    </div>
                  </label>
                ))}
              </div>
              <div className="flex justify-between pt-2">
                <button onClick={() => setStep('choose')} className="text-sm text-gray-400 hover:text-gray-300">← Back</button>
                <button onClick={() => { setStep('manual-roles'); setRoleChecked(new Set()); }}
                  className="text-sm text-blue-400 hover:text-blue-300">Step 2: Merge Roles →</button>
              </div>
            </div>
          )}

          {/* Manual Step 2: Roles */}
          {step === 'manual-roles' && (
            <div className="space-y-3">
              <p className="text-xs text-gray-500">Within each company, check 2+ roles to merge together. Their bullets will be combined.</p>
              <div className="flex items-center gap-3">
                <input type="text" value={roleSearch} onChange={(e) => setRoleSearch(e.target.value)}
                  placeholder="Search companies or roles..." className="flex-1 bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-100 placeholder-gray-500 focus:border-blue-400 focus:outline-none" />
                <button onClick={stageRoleMerge} disabled={roleChecked.size < 2}
                  className="px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-white text-xs rounded disabled:opacity-50 whitespace-nowrap">
                  Merge {roleChecked.size} Roles
                </button>
              </div>
              <div className="max-h-[45vh] overflow-y-auto border border-gray-700 rounded-lg">
                {companiesForRoles.map((group) => (
                  <div key={group.employer} className="border-b border-gray-800 last:border-b-0">
                    <div className="px-4 py-2 bg-gray-800/50 text-sm font-semibold text-gray-300">{group.employer}</div>
                    {group.jobs.map((job) => {
                      const staged = stagedMerges.some((m) => m.merge_ids.includes(job.id));
                      if (staged) return null;
                      return (
                        <label key={job.id}
                          className={`flex items-center gap-3 px-6 py-2 cursor-pointer hover:bg-gray-800/30 ${
                            roleChecked.has(job.id) ? 'bg-yellow-900/20' : ''
                          }`}>
                          <input type="checkbox" checked={roleChecked.has(job.id)}
                            onChange={() => toggleRole(job.id)} className="accent-yellow-400 w-4 h-4 shrink-0" />
                          <span className="flex-1 text-sm text-gray-200 truncate">{job.title}</span>
                          <span className="text-xs text-gray-500 shrink-0">
                            {yearOf(job.start_date)}{job.end_date ? `–${yearOf(job.end_date)}` : '–now'}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                ))}
              </div>
              <button onClick={() => setStep('manual-companies')} className="text-sm text-gray-400 hover:text-gray-300">← Back to Companies</button>
            </div>
          )}
        </div>

        {/* Staged merges + footer */}
        <div className="border-t border-gray-700">
          {stagedMerges.length > 0 && (
            <div className="px-5 py-3 bg-gray-800/50 max-h-[120px] overflow-y-auto">
              <div className="text-xs font-semibold text-yellow-400 mb-1">Staged ({stagedMerges.length})</div>
              {stagedMerges.map((m, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-gray-300 py-0.5">
                  <span className="flex-1 truncate">{m.label}</span>
                  <button onClick={() => removeStagedMerge(i)} className="text-red-400 hover:text-red-300 shrink-0">✕</button>
                </div>
              ))}
            </div>
          )}
          <div className="flex items-center justify-between px-5 py-3">
            <span className="text-sm text-gray-500">{saving && saveProgress}</span>
            <div className="flex gap-2">
              <button onClick={handleCancel} disabled={saving} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded disabled:opacity-50">Cancel</button>
              {stagedMerges.length > 0 && (
                <button onClick={saveAll} disabled={saving}
                  className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm rounded disabled:opacity-50">
                  {saving ? 'Saving...' : `Save & Done (${stagedMerges.length})`}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
