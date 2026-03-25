import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
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

export default function JobList({ selectedJobId, onSelectJob }: JobListProps) {
  const [search, setSearch] = useState('');

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

  const totalBullets = useMemo(
    () => enrichedJobs.reduce((sum, j) => sum + (j.bullet_count || 0), 0),
    [enrichedJobs],
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-gray-100">Career History</h2>
          <div className="flex gap-2 text-xs text-gray-500">
            <span>{enrichedJobs.length} jobs</span>
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

      {/* Job list */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-4 text-gray-500 text-sm">Loading career history...</div>
        ) : filtered.length === 0 ? (
          <div className="p-4 text-gray-500 text-sm">
            {search
              ? 'No jobs match your filter.'
              : 'No jobs found. Import a resume or add a job manually.'}
          </div>
        ) : (
          filtered.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              isSelected={selectedJobId === job.id}
              onSelect={() => onSelectJob(job.id)}
              onUpdate={() => refetch()}
            />
          ))
        )}
      </div>
    </div>
  );
}
