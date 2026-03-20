import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { savedJobs } from '../../api/client';
import type { SavedJob } from '../../api/client';

const STATUSES = ['All', 'saved', 'evaluating', 'applying', 'applied', 'passed'];

export default function SavedJobs() {
  const [filter, setFilter] = useState('All');
  const qc = useQueryClient();

  const params = filter === 'All' ? '?limit=100' : `?status=${filter}&limit=100`;
  const { data, isLoading } = useQuery({
    queryKey: ['saved-jobs', filter],
    queryFn: () => savedJobs.list(params),
  });

  const applyJob = useMutation({
    mutationFn: (id: number) => savedJobs.apply(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['saved-jobs'] }),
  });

  const deleteJob = useMutation({
    mutationFn: (id: number) => savedJobs.del(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['saved-jobs'] }),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Saved Jobs</h1>
        <span className="text-sm text-gray-500">{data?.length ?? 0} jobs</span>
      </div>

      <div className="flex gap-2 mb-4">
        {STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              filter === s ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {isLoading && <p className="text-gray-400">Loading...</p>}
        {(data ?? []).map((job: SavedJob) => (
          <div key={job.id} className="bg-white rounded-lg border border-gray-200 p-4 flex justify-between items-start">
            <div>
              <h3 className="font-medium text-gray-900">{job.title}</h3>
              <p className="text-sm text-gray-500">{job.company} {job.location ? `- ${job.location}` : ''}</p>
              <div className="flex gap-3 mt-2 text-xs text-gray-400">
                {job.source && <span>{job.source}</span>}
                {job.salary_range && <span>{job.salary_range}</span>}
                {job.fit_score != null && <span>Fit: {job.fit_score}/10</span>}
              </div>
            </div>
            <div className="flex gap-2">
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                job.status === 'saved' ? 'bg-blue-100 text-blue-700' :
                job.status === 'evaluating' ? 'bg-yellow-100 text-yellow-700' :
                job.status === 'applying' ? 'bg-purple-100 text-purple-700' :
                'bg-gray-100 text-gray-600'
              }`}>
                {job.status}
              </span>
              {job.status !== 'applied' && (
                <button
                  onClick={() => applyJob.mutate(job.id)}
                  className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700"
                >
                  Apply
                </button>
              )}
              <button
                onClick={() => deleteJob.mutate(job.id)}
                className="px-3 py-1 bg-red-50 text-red-600 text-xs rounded hover:bg-red-100"
              >
                Remove
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
