import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import JobCard, { type CareerJob } from './JobCard';
import MergeDuplicatesModal from './MergeDuplicatesModal';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

interface JobListProps {
  selectedJobId: number | null;
  onSelectJob: (id: number | null) => void;
}

interface CareerJobRow {
  id: number;
  employer: string;
  title: string;
  start_date?: string | null;
  end_date?: string | null;
  location?: string | null;
  industry?: string | null;
  team_size?: number | null;
  budget_usd?: number | null;
  revenue_impact?: string | null;
  is_current?: boolean;
  linkedin_dates?: string | null;
  notes?: string | null;
  metadata?: Record<string, string> | null;
}

export interface CompanyGroup {
  employer: string;
  jobs: CareerJob[];
  totalBullets: number;
}

/** Extract year from a date string, or null */
function yearOf(d?: string | null): number | null {
  if (!d) return null;
  const m = d.match(/(\d{4})/);
  return m ? parseInt(m[1]) : null;
}

/** Compute a date range string for a set of jobs.
 *  Single span: "2011–2022". Gaps: "2011 ... 2022". Current: "2011 ... now" or "2011–now". */
function jobsDateRange(jobs: CareerJob[]): string {
  const starts: number[] = [];
  const ends: (number | null)[] = [];
  let hasCurrent = false;
  for (const j of jobs) {
    const s = yearOf(j.start_date);
    if (s) starts.push(s);
    if (!j.end_date && (j.is_current || !j.end_date)) {
      hasCurrent = true;
      ends.push(null);
    } else {
      const e = yearOf(j.end_date);
      if (e) ends.push(e);
    }
  }
  if (starts.length === 0) return '';
  const earliest = Math.min(...starts);
  const endLabel = hasCurrent ? 'now' : (ends.filter((e): e is number => e !== null).length > 0 ? String(Math.max(...ends.filter((e): e is number => e !== null))) : '');
  if (!endLabel) return String(earliest);

  // Detect gaps: sort jobs by start, check if any end < next start
  const sorted = [...jobs].sort((a, b) => (a.start_date || '').localeCompare(b.start_date || ''));
  let hasGap = false;
  for (let i = 0; i < sorted.length - 1; i++) {
    const thisEnd = yearOf(sorted[i].end_date);
    const nextStart = yearOf(sorted[i + 1].start_date);
    if (thisEnd && nextStart && nextStart - thisEnd > 1) {
      hasGap = true;
      break;
    }
  }

  const sep = hasGap ? ' ... ' : '–';
  return `${earliest}${sep}${endLabel}`;
}

/** Date range for a single job */
function jobDateRange(job: CareerJob): string {
  const s = yearOf(job.start_date);
  if (!s) return '';
  if (!job.end_date) return `${s}–now`;
  const e = yearOf(job.end_date);
  if (!e) return String(s);
  if (s === e) return String(s);
  return `${s}–${e}`;
}

export default function JobList({ selectedJobId, onSelectJob }: JobListProps) {
  const [search, setSearch] = useState('');
  const [collapsedCompanies, setCollapsedCompanies] = useState<Set<string>>(new Set());
  const [editingCompany, setEditingCompany] = useState<string | null>(null);
  const [editCompanyName, setEditCompanyName] = useState('');
  const [mergeModalOpen, setMergeModalOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data: jobs = [], isLoading, refetch } = useQuery({
    queryKey: ['career-history'],
    queryFn: () => api.get<CareerJobRow[]>('/career-history?limit=200'),
  });

  // Fetch bullet counts per job
  const { data: allBullets = [] } = useQuery({
    queryKey: ['bullets-all'],
    queryFn: () => api.get<Array<{ id: number; career_history_id?: number }>>('/bullets?limit=5000'),
  });

  const bulletCountMap = useMemo(() => {
    const map: Record<number, number> = {};
    for (const b of allBullets) {
      if (b.career_history_id) {
        map[b.career_history_id] = (map[b.career_history_id] || 0) + 1;
      }
    }
    return map;
  }, [allBullets]);

  const enrichedJobs: CareerJob[] = useMemo(
    () => jobs.map((j) => ({ ...j, bullet_count: bulletCountMap[j.id] || 0 })),
    [jobs, bulletCountMap],
  );

  const filtered = useMemo(() => {
    if (!search.trim()) return enrichedJobs;
    const q = search.toLowerCase();
    return enrichedJobs.filter(
      (j) =>
        j.title.toLowerCase().includes(q) ||
        j.employer.toLowerCase().includes(q),
    );
  }, [enrichedJobs, search]);

  // Group by employer
  const companyGroups = useMemo(() => {
    const groups: Record<string, CareerJob[]> = {};
    for (const job of filtered) {
      const key = job.employer || 'Unknown';
      if (!groups[key]) groups[key] = [];
      groups[key].push(job);
    }
    // Sort jobs within each group by start_date descending
    const result: CompanyGroup[] = Object.entries(groups).map(([employer, jobs]) => ({
      employer,
      jobs: jobs.sort((a, b) => {
        const da = a.start_date || '';
        const db = b.start_date || '';
        return db.localeCompare(da);
      }),
      totalBullets: jobs.reduce((sum, j) => sum + (j.bullet_count || 0), 0),
    }));
    // Sort groups: most recent job's start_date first
    result.sort((a, b) => {
      const da = a.jobs[0]?.start_date || '';
      const db = b.jobs[0]?.start_date || '';
      return db.localeCompare(da);
    });
    return result;
  }, [filtered]);

  // Filter out UNASSIGNED if it has zero bullets
  const visibleGroups = useMemo(() => {
    return companyGroups.filter((g) => {
      if (g.employer === 'UNASSIGNED' && g.totalBullets === 0) return false;
      return true;
    });
  }, [companyGroups]);

  const totalBullets = useMemo(
    () => enrichedJobs.reduce((sum, j) => sum + (j.bullet_count || 0), 0),
    [enrichedJobs],
  );

  const toggleCompany = (employer: string) => {
    setCollapsedCompanies((prev) => {
      const next = new Set(prev);
      if (next.has(employer)) next.delete(employer);
      else next.add(employer);
      return next;
    });
  };

  // Rename company across all jobs
  const renameMutation = useMutation({
    mutationFn: async ({ oldName, newName }: { oldName: string; newName: string }) => {
      const jobsToUpdate = enrichedJobs.filter((j) => j.employer === oldName);
      await Promise.all(
        jobsToUpdate.map((j) => api.patch(`/career-history/${j.id}`, { employer: newName }))
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['career-history'] });
      setEditingCompany(null);
    },
  });

  const startEditCompany = (employer: string) => {
    setEditingCompany(employer);
    setEditCompanyName(employer);
  };

  const saveCompanyName = () => {
    if (!editingCompany || !editCompanyName.trim()) return;
    if (editCompanyName.trim() === editingCompany) {
      setEditingCompany(null);
      return;
    }
    renameMutation.mutate({ oldName: editingCompany, newName: editCompanyName.trim() });
  };

  // Delete company
  const deleteCompany = async (group: CompanyGroup) => {
    const choice = prompt(
      `Delete "${group.employer}" and all ${group.jobs.length} role(s) under it?\n` +
      `Total bullets: ${group.totalBullets}\n\n` +
      `Type your choice:\n` +
      `  1 = Delete jobs only (keep bullets in UNASSIGNED)\n` +
      `  2 = Delete jobs AND all bullets\n` +
      `  (Cancel to abort)`
    );
    if (!choice || (choice.trim() !== '1' && choice.trim() !== '2')) return;
    const keepBullets = choice.trim() === '1';

    try {
      const encodedEmployer = encodeURIComponent(group.employer);
      await fetch(`${API_BASE}/company/${encodedEmployer}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keep_bullets: keepBullets }),
      });
      queryClient.invalidateQueries({ queryKey: ['career-history'] });
      queryClient.invalidateQueries({ queryKey: ['bullets-all'] });
      if (group.jobs.some((j) => j.id === selectedJobId)) {
        onSelectJob(null);
      }
    } catch (e) {
      alert(`Delete failed: ${(e as Error).message}`);
    }
  };

  // Merge duplicates — wizard handles its own data loading


  const handleMergeComplete = () => {
    queryClient.invalidateQueries({ queryKey: ['career-history'] });
    queryClient.invalidateQueries({ queryKey: ['bullets-all'] });
    setMergeModalOpen(false);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-gray-100">Career History</h2>
          <button
            onClick={() => setMergeModalOpen(true)}
            className="text-xs text-yellow-400 hover:text-yellow-300"
            title="Find and merge duplicate companies/roles"
          >
            Merge Duplicates
          </button>
        </div>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter by title or company..."
          className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-100 placeholder-gray-500 focus:border-blue-400 focus:outline-none"
        />
      </div>

      {/* Grouped job list */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-4 text-gray-500 text-sm">Loading career history...</div>
        ) : visibleGroups.length === 0 ? (
          <div className="p-4 text-gray-500 text-sm">
            {search
              ? 'No jobs match your filter.'
              : 'No jobs found. Import a resume or add a job manually.'}
          </div>
        ) : (
          visibleGroups.map((group) => {
            const isCollapsed = collapsedCompanies.has(group.employer);
            const hasSelectedJob = group.jobs.some((j) => j.id === selectedJobId);

            return (
              <div key={group.employer} className="border-b border-gray-800">
                {/* Company header */}
                <div
                  className={`flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-gray-800/50 ${
                    hasSelectedJob ? 'bg-blue-900/20' : ''
                  }`}
                  onClick={() => toggleCompany(group.employer)}
                >
                  <span className="text-gray-500 text-xs w-4 text-center">
                    {isCollapsed ? '\u25B8' : '\u25BE'}
                  </span>

                  {editingCompany === group.employer ? (
                    <div className="flex-1 flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                      <input
                        value={editCompanyName}
                        onChange={(e) => setEditCompanyName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') saveCompanyName();
                          if (e.key === 'Escape') setEditingCompany(null);
                        }}
                        autoFocus
                        className="flex-1 bg-gray-800 border border-blue-500 rounded px-2 py-0.5 text-sm text-gray-100 focus:outline-none"
                      />
                      <button
                        onClick={saveCompanyName}
                        className="text-xs text-green-400 hover:text-green-300"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingCompany(null)}
                        className="text-xs text-gray-500 hover:text-gray-400"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <>
                      <span className="flex-1 text-sm font-semibold text-gray-200 truncate">
                        {group.employer}
                      </span>
                      <span className="text-xs text-gray-500 shrink-0">
                        {jobsDateRange(group.jobs)}
                      </span>
                      <button
                        onClick={(e) => { e.stopPropagation(); startEditCompany(group.employer); }}
                        className="text-gray-600 hover:text-gray-400 text-xs shrink-0"
                        title="Rename company"
                      >
                        ✏️
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteCompany(group); }}
                        className="text-gray-600 hover:text-red-400 text-xs shrink-0"
                        title="Delete company"
                      >
                        🗑
                      </button>
                    </>
                  )}
                </div>

                {/* Jobs under this company */}
                {!isCollapsed &&
                  group.jobs.map((job) => (
                    <div key={job.id} className="pl-4">
                      <JobCard
                        job={job}
                        isSelected={selectedJobId === job.id}
                        onSelect={() => onSelectJob(job.id)}
                        onUpdate={() => refetch()}
                        onDeleted={() => {
                          if (selectedJobId === job.id) onSelectJob(null);
                          queryClient.invalidateQueries({ queryKey: ['career-history'] });
                          queryClient.invalidateQueries({ queryKey: ['bullets-all'] });
                        }}
                      />
                    </div>
                  ))}
              </div>
            );
          })
        )}
      </div>

      {/* Merge Duplicates Modal */}
      <MergeDuplicatesModal
        isOpen={mergeModalOpen}
        onClose={() => setMergeModalOpen(false)}
        onComplete={handleMergeComplete}
      />
    </div>
  );
}
