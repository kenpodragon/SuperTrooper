import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

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

export default function FreshJobs() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState('new');
  const [selected, setSelected] = useState<number[]>([]);

  const { data, isLoading } = useQuery({
    queryKey: ['fresh-jobs', statusFilter],
    queryFn: () => api.get<any[]>(`/fresh-jobs?status=${statusFilter}`),
  });

  const { data: stats } = useQuery({
    queryKey: ['fresh-jobs-stats'],
    queryFn: () => api.get<any>('/fresh-jobs/stats'),
  });

  const triage = useMutation({
    mutationFn: ({ id, action }: { id: number; action: string }) =>
      api.post<any>(`/fresh-jobs/${id}/triage`, { action }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fresh-jobs'] });
      qc.invalidateQueries({ queryKey: ['fresh-jobs-stats'] });
      setSelected([]);
    },
  });

  const batchTriage = useMutation({
    mutationFn: ({ ids, action }: { ids: number[]; action: string }) =>
      api.post<any>('/fresh-jobs/batch-triage', { ids, action }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fresh-jobs'] });
      qc.invalidateQueries({ queryKey: ['fresh-jobs-stats'] });
      setSelected([]);
    },
  });

  const jobs = data ?? [];
  const allSelected = jobs.length > 0 && selected.length === jobs.length;

  function toggleSelect(id: number) {
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }

  function toggleAll() {
    setSelected(allSelected ? [] : jobs.map((j: any) => j.id));
  }

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

        <div className="p-4 border-b border-gray-100 flex items-center gap-3">
          <input type="checkbox" checked={allSelected} onChange={toggleAll} className="rounded" />
          <span className="text-xs text-gray-500 uppercase tracking-wide">Select All</span>
        </div>

        {isLoading && <p className="text-sm text-gray-400 p-4">Loading...</p>}
        {!isLoading && jobs.length === 0 && <p className="text-sm text-gray-400 p-4">No jobs in this category.</p>}

        {jobs.map((job: any) => (
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
              </div>
              <p className="text-xs text-gray-600 mt-0.5">{job.company} &middot; {job.location}</p>
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
