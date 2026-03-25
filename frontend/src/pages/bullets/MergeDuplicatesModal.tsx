import { useState } from 'react';
import { api } from '../../api/client';

// Matches actual API response shape from GET /api/career-history/duplicates
interface CompanyDuplicate {
  group: number[];   // career_history IDs
  names: string[];   // employer name variants
}

interface RoleDuplicate {
  employer: string;
  group: number[];   // career_history IDs
  titles: string[];  // title variants
}

interface DuplicatesData {
  company_duplicates: CompanyDuplicate[];
  role_duplicates: RoleDuplicate[];
}

interface MergeDuplicatesModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: () => void;
  duplicates: DuplicatesData;
}

export default function MergeDuplicatesModal({
  isOpen,
  onClose,
  onComplete,
  duplicates,
}: MergeDuplicatesModalProps) {
  const [companySelections, setCompanySelections] = useState<Record<number, number>>({});
  const [roleSelections, setRoleSelections] = useState<Record<number, number>>({});
  const [merging, setMerging] = useState<string | null>(null);
  const [merged, setMerged] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const mergeCompany = async (groupIdx: number) => {
    const group = duplicates.company_duplicates[groupIdx];
    const selectedIdx = companySelections[groupIdx] ?? 0;
    const keepName = group.names[selectedIdx];
    // Keep the first ID, merge the rest. The backend will rename all to keepName.
    const keepId = group.group[0];
    const mergeIds = group.group.slice(1);

    if (mergeIds.length === 0) return;

    setMerging(`company-${groupIdx}`);
    setError(null);
    try {
      await api.post('/career-history/merge', {
        keep_id: keepId,
        merge_ids: mergeIds,
        new_employer: keepName,
      });
      setMerged((prev) => new Set(prev).add(`company-${groupIdx}`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setMerging(null);
    }
  };

  const mergeRole = async (groupIdx: number) => {
    const group = duplicates.role_duplicates[groupIdx];
    const selectedIdx = roleSelections[groupIdx] ?? 0;
    const keepId = group.group[selectedIdx];
    const mergeIds = group.group.filter((_, i) => i !== selectedIdx);

    if (mergeIds.length === 0) return;

    setMerging(`role-${groupIdx}`);
    setError(null);
    try {
      await api.post('/career-history/merge', {
        keep_id: keepId,
        merge_ids: mergeIds,
      });
      setMerged((prev) => new Set(prev).add(`role-${groupIdx}`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setMerging(null);
    }
  };

  const allDone =
    (duplicates.company_duplicates || []).every((_, i) => merged.has(`company-${i}`)) &&
    (duplicates.role_duplicates || []).every((_, i) => merged.has(`role-${i}`));

  const handleClose = () => {
    if (merged.size > 0) onComplete();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-gray-900 border border-gray-700 rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-gray-100">Merge Duplicate Entries</h2>
          <button onClick={handleClose} className="text-gray-500 hover:text-gray-300 text-xl">
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
          {error && (
            <div className="text-sm text-red-400 bg-red-900/20 rounded px-3 py-2">{error}</div>
          )}

          {/* Company duplicates */}
          {duplicates.company_duplicates?.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-300 mb-3">Company Names</h3>
              <div className="space-y-4">
                {duplicates.company_duplicates.map((dup, gi) => {
                  const isDone = merged.has(`company-${gi}`);
                  return (
                    <div
                      key={gi}
                      className={`border border-gray-700 rounded-lg p-4 ${isDone ? 'opacity-50' : ''}`}
                    >
                      <div className="text-xs text-gray-500 mb-2">
                        Variants: {dup.names.map((n) => `"${n}"`).join(' / ')}
                        <span className="ml-2 text-gray-600">({dup.group.length} job IDs: {dup.group.join(', ')})</span>
                      </div>
                      <div className="space-y-1.5">
                        {dup.names.map((name, ni) => (
                          <label
                            key={ni}
                            className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer"
                          >
                            <input
                              type="radio"
                              name={`company-${gi}`}
                              checked={(companySelections[gi] ?? 0) === ni}
                              onChange={() =>
                                setCompanySelections((prev) => ({ ...prev, [gi]: ni }))
                              }
                              disabled={isDone}
                              className="accent-blue-500"
                            />
                            Keep "{name}"
                          </label>
                        ))}
                      </div>
                      <div className="flex gap-2 mt-3">
                        <button
                          onClick={() => mergeCompany(gi)}
                          disabled={isDone || merging === `company-${gi}`}
                          className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded disabled:opacity-50"
                        >
                          {merging === `company-${gi}` ? 'Merging...' : isDone ? 'Merged' : 'Merge'}
                        </button>
                        {!isDone && (
                          <button
                            onClick={() =>
                              setMerged((prev) => new Set(prev).add(`company-${gi}`))
                            }
                            className="px-3 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded"
                          >
                            Skip
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Role duplicates */}
          {duplicates.role_duplicates?.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-300 mb-3">Duplicate Roles</h3>
              <div className="space-y-4">
                {duplicates.role_duplicates.map((dup, gi) => {
                  const isDone = merged.has(`role-${gi}`);
                  return (
                    <div
                      key={gi}
                      className={`border border-gray-700 rounded-lg p-4 ${isDone ? 'opacity-50' : ''}`}
                    >
                      <div className="text-xs text-gray-500 mb-2">At "{dup.employer}":</div>
                      <div className="space-y-1.5">
                        {dup.titles.map((title, ti) => (
                          <label
                            key={ti}
                            className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer"
                          >
                            <input
                              type="radio"
                              name={`role-${gi}`}
                              checked={(roleSelections[gi] ?? 0) === ti}
                              onChange={() =>
                                setRoleSelections((prev) => ({ ...prev, [gi]: ti }))
                              }
                              disabled={isDone}
                              className="accent-blue-500"
                            />
                            "{title}"
                            <span className="text-xs text-gray-600 ml-auto">
                              ID: {dup.group[ti]}
                            </span>
                          </label>
                        ))}
                      </div>
                      <div className="flex gap-2 mt-3">
                        <button
                          onClick={() => mergeRole(gi)}
                          disabled={isDone || merging === `role-${gi}`}
                          className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded disabled:opacity-50"
                        >
                          {merging === `role-${gi}` ? 'Merging...' : isDone ? 'Merged' : 'Merge'}
                        </button>
                        {!isDone && (
                          <button
                            onClick={() => setMerged((prev) => new Set(prev).add(`role-${gi}`))}
                            className="px-3 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded"
                          >
                            Skip
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {allDone && (
            <div className="text-sm text-green-400 text-center py-2">
              All duplicates handled. Close to refresh.
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-5 py-3 border-t border-gray-700">
          <button
            onClick={handleClose}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-200 text-sm rounded"
          >
            {merged.size > 0 ? 'Done' : 'Close'}
          </button>
        </div>
      </div>
    </div>
  );
}
