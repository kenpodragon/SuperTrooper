import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface FreshJob {
  id: number;
  title: string;
  company: string;
  location?: string;
  source?: string;
  fit_score?: number;
  salary_min?: number;
  salary_max?: number;
  salary_range?: string;
  skills_matched?: string[];
  skills_missing?: string[];
  status: string;
  created_at?: string;
  company_dossier?: string;
  similar_group?: string;
}

interface FreshJobStats {
  total_new: number;
  reviewed_today: number;
  saved_this_week: number;
}

interface TriageResponse {
  id: number;
  status: string;
}

interface BatchTriageResponse {
  updated: number;
}

const SOURCES = ['All', 'Indeed', 'Remotive', 'The Muse', 'RSS', 'LinkedIn', 'Manual'];

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-semibold text-gray-900 mt-1">{value}</p>
    </div>
  );
}

function fitBadge(score?: number) {
  if (score == null) return <span className="text-xs text-gray-400">N/A</span>;
  const color = score >= 80 ? 'bg-green-100 text-green-800' : score >= 60 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800';
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>{score}</span>;
}

function SkillBreakdown({ matched, missing }: { matched?: string[]; missing?: string[] }) {
  if (!matched?.length && !missing?.length) return null;
  return (
    <div className="mt-1.5 flex flex-wrap gap-1">
      {(matched ?? []).slice(0, 4).map(s => (
        <span key={s} className="text-xs px-1.5 py-0.5 bg-green-50 text-green-700 rounded">{s}</span>
      ))}
      {(missing ?? []).slice(0, 3).map(s => (
        <span key={s} className="text-xs px-1.5 py-0.5 bg-red-50 text-red-600 rounded line-through">{s}</span>
      ))}
    </div>
  );
}

function CompanyTooltip({ company, dossier }: { company: string; dossier?: string }) {
  const [show, setShow] = useState(false);
  return (
    <span
      className="relative cursor-help"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <span className="text-xs text-gray-600">{company}</span>
      {show && dossier && (
        <div className="absolute z-40 left-0 top-full mt-1 w-64 p-3 bg-white border border-gray-200 rounded-lg shadow-lg text-xs text-gray-700 whitespace-pre-wrap">
          {dossier}
        </div>
      )}
    </span>
  );
}

export default function FreshJobs() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState('new');
  const [sourceFilter, setSourceFilter] = useState('All');
  const [salaryMin, setSalaryMin] = useState('');
  const [selected, setSelected] = useState<number[]>([]);

  const { data, isLoading } = useQuery({
    queryKey: ['fresh-jobs', statusFilter],
    queryFn: () => api.get<FreshJob[]>(`/fresh-jobs?status=${statusFilter}`),
  });

  const { data: stats } = useQuery({
    queryKey: ['fresh-jobs-stats'],
    queryFn: () => api.get<FreshJobStats>('/fresh-jobs/stats'),
  });

  const triage = useMutation({
    mutationFn: ({ id, action }: { id: number; action: string }) =>
      api.post<TriageResponse>(`/fresh-jobs/${id}/triage`, { action }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fresh-jobs'] });
      qc.invalidateQueries({ queryKey: ['fresh-jobs-stats'] });
      setSelected([]);
    },
    onError: (err: any) => alert(err?.response?.data?.error || 'Triage failed'),
  });

  const batchTriage = useMutation({
    mutationFn: ({ ids, action }: { ids: number[]; action: string }) =>
      api.post<BatchTriageResponse>('/fresh-jobs/batch-triage', { job_ids: ids, action }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fresh-jobs'] });
      qc.invalidateQueries({ queryKey: ['fresh-jobs-stats'] });
      setSelected([]);
    },
    onError: (err: any) => alert(err?.response?.data?.error || 'Batch triage failed'),
  });

  let jobs = data ?? [];

  // Client-side filters
  if (sourceFilter !== 'All') {
    jobs = jobs.filter((j: FreshJob) => (j.source || '').toLowerCase() === sourceFilter.toLowerCase());
  }
  if (salaryMin) {
    const min = parseInt(salaryMin, 10);
    if (!isNaN(min)) {
      jobs = jobs.filter((j: FreshJob) => (j.salary_min ?? j.salary_max ?? 0) >= min);
    }
  }

  const allSelected = jobs.length > 0 && selected.length === jobs.length;

  function toggleSelect(id: number) {
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }

  function toggleAll() {
    setSelected(allSelected ? [] : jobs.map((j: FreshJob) => j.id));
  }

  // Group similar jobs
  const grouped: Record<string, FreshJob[]> = {};
  jobs.forEach(j => {
    const key = j.similar_group || `single-${j.id}`;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(j);
  });
  const hasSimilarGroups = Object.values(grouped).some(g => g.length > 1);

  const tabs = ['new', 'reviewing', 'saved', 'dismissed'];

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Fresh Jobs Inbox</h1>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard label="New Today" value={stats?.total_new ?? '...'} />
        <StatCard label="Reviewed Today" value={stats?.reviewed_today ?? '...'} />
        <StatCard label="Saved This Week" value={stats?.saved_this_week ?? '...'} />
      </div>

      <div className="bg-white rounded-lg border border-gray-200">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div className="flex gap-2">
            {tabs.map(t => (
              <button
                key={t}
                onClick={() => { setStatusFilter(t); setSelected([]); }}
                className={`px-3 py-1.5 text-sm rounded-md capitalize ${statusFilter === t ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-100'}`}
              >
                {t}
              </button>
            ))}
          </div>
          {selected.length > 0 && (
            <div className="flex gap-2">
              <span className="text-sm text-gray-500">{selected.length} selected</span>
              <button
                onClick={() => batchTriage.mutate({ ids: selected, action: 'save' })}
                className="text-xs px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700"
              >
                Save All
              </button>
              <button
                onClick={() => batchTriage.mutate({ ids: selected, action: 'dismiss' })}
                className="text-xs px-2 py-1 bg-gray-500 text-white rounded hover:bg-gray-600"
              >
                Dismiss All
              </button>
            </div>
          )}
        </div>

        {/* Filters row */}
        <div className="p-3 border-b border-gray-100 flex items-center gap-3 bg-gray-50 flex-wrap">
          <input type="checkbox" checked={allSelected} onChange={toggleAll} className="rounded" />
          <span className="text-xs text-gray-500 uppercase tracking-wide">Select All</span>
          <div className="ml-auto flex items-center gap-3">
            <select
              className="text-xs border border-gray-200 rounded px-2 py-1"
              value={sourceFilter}
              onChange={e => setSourceFilter(e.target.value)}
            >
              {SOURCES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <div className="flex items-center gap-1">
              <span className="text-xs text-gray-500">Min $</span>
              <input
                type="number"
                className="text-xs border border-gray-200 rounded px-2 py-1 w-20"
                placeholder="0"
                value={salaryMin}
                onChange={e => setSalaryMin(e.target.value)}
              />
            </div>
          </div>
        </div>

        {isLoading && <p className="text-sm text-gray-400 p-4">Loading...</p>}
        {!isLoading && jobs.length === 0 && <p className="text-sm text-gray-400 p-4">No jobs in this category.</p>}

        {jobs.map((job: FreshJob) => (
          <div key={job.id} className="flex items-start gap-3 p-4 border-b border-gray-100 last:border-0 hover:bg-gray-50">
            <input
              type="checkbox"
              checked={selected.includes(job.id)}
              onChange={() => toggleSelect(job.id)}
              className="mt-1 rounded"
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="text-sm font-medium text-gray-900">{job.title}</p>
                {fitBadge(job.fit_score)}
                <span className="text-xs text-gray-400">{job.source}</span>
                {(job.salary_range || job.salary_min) && (
                  <span className="text-xs text-green-600 font-medium">
                    {job.salary_range || `$${(job.salary_min ?? 0).toLocaleString()}`}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <CompanyTooltip company={job.company} dossier={job.company_dossier} />
                <span className="text-xs text-gray-400">&middot;</span>
                <span className="text-xs text-gray-500">{job.location}</span>
              </div>
              <SkillBreakdown matched={job.skills_matched} missing={job.skills_missing} />
              <p className="text-xs text-gray-400 mt-0.5">{job.created_at ? new Date(job.created_at).toLocaleDateString() : ''}</p>
            </div>
            <div className="flex gap-1.5 shrink-0">
              <button
                onClick={() => triage.mutate({ id: job.id, action: 'review' })}
                className="text-xs px-2 py-1 border border-blue-300 text-blue-700 rounded hover:bg-blue-50"
              >
                Review
              </button>
              <button
                onClick={() => triage.mutate({ id: job.id, action: 'save' })}
                className="text-xs px-2 py-1 border border-green-300 text-green-700 rounded hover:bg-green-50"
              >
                Save
              </button>
              <button
                onClick={() => triage.mutate({ id: job.id, action: 'apply' })}
                className="text-xs px-2 py-1 border border-purple-300 text-purple-700 rounded hover:bg-purple-50"
              >
                Quick Apply
              </button>
              <button
                onClick={() => triage.mutate({ id: job.id, action: 'dismiss' })}
                className="text-xs px-2 py-1 border border-gray-300 text-gray-500 rounded hover:bg-gray-50"
              >
                Dismiss
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
