import { useState } from 'react';
import { api } from '../../api/client';

interface CompanyDuplicate {
  employer: string;
  variants: Array<{
    name: string;
    role_count: number;
    bullet_count: number;
    job_ids: number[];
  }>;
}

interface RoleDuplicate {
  employer: string;
  roles: Array<{
    id: number;
    title: string;
    bullet_count: number;
    start_date?: string;
    end_date?: string;
  }>;
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
    const keepName = group.variants[selectedIdx].name;
    const keepIds = group.variants[selectedIdx].job_ids;
    const mergeIds = group.variants
      .filter((_, i) => i !== selectedIdx)
      .flatMap((v) => v.job_ids);

    if (mergeIds.length === 0) return;

    setMerging(`company-${groupIdx}`);
    setError(null);
    try {
      await api.post('/career-history/merge', {
        keep_id: keepIds[0],
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
    const keepRole = group.roles[selectedIdx];
    const mergeIds = group.roles.filter((_, i) => i !== selectedIdx).map((r) => r.id);

    if (mergeIds.length === 0) return;

    setMerging(`role-${groupIdx}`);
    setError(null);
    try {
      await api.post('/career-history/merge', {
        keep_id: keepRole.id,
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
    duplicates.company_duplicates.every((_, i) => merged.has(`company-${i}`)) &&
    duplicates.role_duplicates.every((_, i) => merged.has(`role-${i}`));

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
          {duplicates.company_duplicates.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-300 mb-3">Company Names</h3>
              <div className="space-y-4">
                {duplicates.company_duplicates.map((group, gi) => {
                  const isDone = merged.has(`company-${gi}`);
                  return (
                    <div
                      key={gi}
                      className={`border border-gray-700 rounded-lg p-4 ${isDone ? 'opacity-50' : ''}`}
                    >
                      <div className="text-xs text-gray-500 mb-2">
                        Variants: {group.variants.map((v) => `"${v.name}"`).join(' / ')}
                      </div>
                      <div className="space-y-1.5">
                        {group.variants.map((variant, vi) => (
                          <label
                            key={vi}
                            className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer"
                          >
                            <input
                              type="radio"
                              name={`company-${gi}`}
                              checked={(companySelections[gi] ?? 0) === vi}
                              onChange={() =>
                                setCompanySelections((prev) => ({ ...prev, [gi]: vi }))
                              }
                              disabled={isDone}
                              className="accent-blue-500"
                            />
                            Keep "{variant.name}"
                            <span className="text-xs text-gray-500 ml-auto">
                              {variant.role_count} role{variant.role_count !== 1 ? 's' : ''},{' '}
                              {variant.bullet_count} bullet{variant.bullet_count !== 1 ? 's' : ''}
                            </span>
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
          {duplicates.role_duplicates.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-300 mb-3">Duplicate Roles</h3>
              <div className="space-y-4">
                {duplicates.role_duplicates.map((group, gi) => {
                  const isDone = merged.has(`role-${gi}`);
                  return (
                    <div
                      key={gi}
                      className={`border border-gray-700 rounded-lg p-4 ${isDone ? 'opacity-50' : ''}`}
                    >
                      <div className="text-xs text-gray-500 mb-2">At "{group.employer}":</div>
                      <div className="space-y-1.5">
                        {group.roles.map((role, ri) => (
                          <label
                            key={ri}
                            className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer"
                          >
                            <input
                              type="radio"
                              name={`role-${gi}`}
                              checked={(roleSelections[gi] ?? 0) === ri}
                              onChange={() =>
                                setRoleSelections((prev) => ({ ...prev, [gi]: ri }))
                              }
                              disabled={isDone}
                              className="accent-blue-500"
                            />
                            "{role.title}"
                            <span className="text-xs text-gray-500 ml-auto">
                              {role.bullet_count} bullet{role.bullet_count !== 1 ? 's' : ''}
                              {role.start_date && ` · ${role.start_date}`}
                              {role.end_date && ` - ${role.end_date}`}
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
