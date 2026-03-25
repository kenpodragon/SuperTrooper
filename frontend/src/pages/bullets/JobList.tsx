import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import JobCard, { type CareerJob } from './JobCard';

interface JobListProps {
  selectedJobId: number | null;
  onSelectJob: (id: number) => void;
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

interface CompanyGroup {
  employer: string;
  jobs: CareerJob[];
  totalBullets: number;
}

export default function JobList({ selectedJobId, onSelectJob }: JobListProps) {
  const [search, setSearch] = useState('');
  const [collapsedCompanies, setCollapsedCompanies] = useState<Set<string>>(new Set());
  const [editingCompany, setEditingCompany] = useState<string | null>(null);
  const [editCompanyName, setEditCompanyName] = useState('');
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

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-gray-100">Career History</h2>
          <div className="flex gap-2 text-xs text-gray-500">
            <span>{companyGroups.length} companies</span>
            <span>{enrichedJobs.length} roles</span>
            <span>{totalBullets} bullets</span>
          </div>
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
        ) : companyGroups.length === 0 ? (
          <div className="p-4 text-gray-500 text-sm">
            {search
              ? 'No jobs match your filter.'
              : 'No jobs found. Import a resume or add a job manually.'}
          </div>
        ) : (
          companyGroups.map((group) => {
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
                    {isCollapsed ? '▸' : '▾'}
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
                      <button
                        onClick={(e) => { e.stopPropagation(); startEditCompany(group.employer); }}
                        className="text-gray-600 hover:text-gray-400 text-xs"
                        title="Rename company"
                      >
                        ✏️
                      </button>
                      <span className="text-xs text-gray-600">
                        {group.jobs.length} role{group.jobs.length > 1 ? 's' : ''} · {group.totalBullets}
                      </span>
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
                      />
                    </div>
                  ))}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
