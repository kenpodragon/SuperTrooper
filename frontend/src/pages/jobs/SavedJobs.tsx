import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { savedJobs, api } from '../../api/client';
import type { SavedJob } from '../../api/client';

const STATUSES = ['All', 'saved', 'evaluating', 'applying', 'applied', 'passed'];

const statusBadge: Record<string, string> = {
  saved: 'bg-blue-100 text-blue-700',
  evaluating: 'bg-yellow-100 text-yellow-700',
  applying: 'bg-purple-100 text-purple-700',
  applied: 'bg-green-100 text-green-700',
  passed: 'bg-gray-100 text-gray-500',
};

interface GapPreview {
  overall_score?: number;
  recommendation?: string;
  strong_matches?: string[];
  gaps?: string[];
}

interface ParsedJD {
  skills?: string[];
  requirements?: string[];
  salary_range?: string;
  experience_level?: string;
}

function JobDetailPanel({
  job,
  onClose,
}: {
  job: SavedJob;
  onClose: () => void;
}) {
  const [showGap, setShowGap] = useState(false);
  const gapQuery = useQuery({
    queryKey: ['gap-preview', job.id],
    queryFn: () => api.post<GapPreview>('/pipeline/gap-analysis', { saved_job_id: job.id }),
    enabled: showGap,
  });

  // Attempt to extract parsed JD info
  const jdText = job.jd_text || '';
  const hasJD = jdText.length > 0;

  return (
    <div className="fixed inset-y-0 right-0 w-[440px] bg-white shadow-xl border-l border-gray-200 z-50 overflow-y-auto">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 truncate pr-2">{job.title}</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
      </div>
      <div className="p-4 space-y-4">
        <div>
          <p className="text-sm font-medium text-gray-800">{job.company}</p>
          <p className="text-xs text-gray-500">{job.location || 'Location not specified'}</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <p className="text-xs text-gray-500">Status</p>
            <span className={`inline-block mt-1 px-2 py-0.5 rounded-full text-xs font-medium ${statusBadge[job.status || ''] || 'bg-gray-100'}`}>
              {job.status}
            </span>
          </div>
          <div>
            <p className="text-xs text-gray-500">Source</p>
            <p className="text-sm text-gray-800 mt-1">{job.source || '-'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Salary Range</p>
            <p className="text-sm text-gray-800 mt-1">{job.salary_range || 'Not specified'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Fit Score</p>
            <p className="text-sm font-medium mt-1">
              {job.fit_score != null ? (
                <span className={job.fit_score >= 7 ? 'text-green-600' : job.fit_score >= 5 ? 'text-yellow-600' : 'text-red-600'}>
                  {job.fit_score}/10
                </span>
              ) : '-'}
            </p>
          </div>
        </div>

        {job.url && (
          <div>
            <p className="text-xs text-gray-500">Posting URL</p>
            <a href={job.url} target="_blank" rel="noreferrer" className="text-sm text-blue-600 hover:underline break-all">{job.url}</a>
          </div>
        )}

        {job.notes && (
          <div>
            <p className="text-xs text-gray-500">Notes</p>
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{job.notes}</p>
          </div>
        )}

        {hasJD && (
          <div className="border-t border-gray-200 pt-3">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Job Description</h3>
            <div className="max-h-48 overflow-y-auto text-xs text-gray-600 whitespace-pre-wrap bg-gray-50 p-3 rounded border border-gray-100">
              {jdText}
            </div>
          </div>
        )}

        {/* Gap Analysis */}
        <div className="border-t border-gray-200 pt-3">
          <button
            onClick={() => setShowGap(true)}
            className="px-3 py-1.5 bg-gray-900 text-white text-xs rounded hover:bg-gray-700"
          >
            Run Gap Analysis
          </button>
          {gapQuery.isLoading && <p className="text-xs text-gray-400 mt-2">Analyzing...</p>}
          {gapQuery.data && (
            <div className="mt-2 bg-gray-50 rounded border border-gray-200 p-3 space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">Score:</span>
                <span className={`text-sm font-semibold ${(gapQuery.data.overall_score ?? 0) >= 70 ? 'text-green-700' : 'text-yellow-700'}`}>
                  {gapQuery.data.overall_score}%
                </span>
              </div>
              {gapQuery.data.recommendation && (
                <p className="text-xs text-gray-600">{gapQuery.data.recommendation}</p>
              )}
              {gapQuery.data.strong_matches && gapQuery.data.strong_matches.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-green-700">Strong Matches:</p>
                  <ul className="text-xs text-gray-600 list-disc list-inside">
                    {gapQuery.data.strong_matches.slice(0, 5).map((m, i) => <li key={i}>{m}</li>)}
                  </ul>
                </div>
              )}
              {gapQuery.data.gaps && gapQuery.data.gaps.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-red-700">Gaps:</p>
                  <ul className="text-xs text-gray-600 list-disc list-inside">
                    {gapQuery.data.gaps.slice(0, 5).map((g, i) => <li key={i}>{g}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function SavedJobs() {
  const [filter, setFilter] = useState('All');
  const [selected, setSelected] = useState<number[]>([]);
  const [detailJob, setDetailJob] = useState<SavedJob | null>(null);
  const qc = useQueryClient();

  const params = filter === 'All' ? '?limit=100' : `?status=${filter}&limit=100`;
  const { data, isLoading } = useQuery({
    queryKey: ['saved-jobs', filter],
    queryFn: () => savedJobs.list(params),
  });

  const applyJob = useMutation({
    mutationFn: (id: number) => savedJobs.apply(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['saved-jobs'] });
      qc.invalidateQueries({ queryKey: ['applications'] });
    },
  });

  const convertJob = useMutation({
    mutationFn: (id: number) => api.post<any>('/pipeline/convert-saved-job', { saved_job_id: id }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['saved-jobs'] });
      qc.invalidateQueries({ queryKey: ['applications'] });
    },
  });

  const deleteJob = useMutation({
    mutationFn: (id: number) => savedJobs.del(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['saved-jobs'] }),
  });

  const batchConvert = useMutation({
    mutationFn: (ids: number[]) => api.post<any>('/pipeline/batch-convert', { saved_job_ids: ids }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['saved-jobs'] });
      qc.invalidateQueries({ queryKey: ['applications'] });
      setSelected([]);
    },
  });

  const batchArchive = useMutation({
    mutationFn: (ids: number[]) => api.post<any>('/pipeline/batch-archive', { saved_job_ids: ids }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['saved-jobs'] });
      setSelected([]);
    },
  });

  const jobs = data ?? [];
  const allSelected = jobs.length > 0 && selected.length === jobs.length;

  function toggleSelect(id: number) {
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }

  function toggleAll() {
    setSelected(allSelected ? [] : jobs.map((j: SavedJob) => j.id));
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Saved Jobs</h1>
        <span className="text-sm text-gray-500">{jobs.length} jobs</span>
      </div>

      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-2">
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => { setFilter(s); setSelected([]); }}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                filter === s ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        {selected.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">{selected.length} selected</span>
            <button
              onClick={() => batchConvert.mutate(selected)}
              disabled={batchConvert.isPending}
              className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700 disabled:opacity-50"
            >
              Convert to Applications
            </button>
            <button
              onClick={() => batchArchive.mutate(selected)}
              disabled={batchArchive.isPending}
              className="px-3 py-1 bg-gray-500 text-white text-xs rounded hover:bg-gray-600 disabled:opacity-50"
            >
              Archive
            </button>
          </div>
        )}
      </div>

      {/* Select all */}
      {jobs.length > 0 && (
        <div className="mb-2 flex items-center gap-2">
          <input type="checkbox" checked={allSelected} onChange={toggleAll} className="rounded" />
          <span className="text-xs text-gray-500">Select all</span>
        </div>
      )}

      <div className="space-y-3">
        {isLoading && <p className="text-gray-400">Loading...</p>}
        {jobs.map((job: SavedJob) => (
          <div
            key={job.id}
            className="bg-white rounded-lg border border-gray-200 p-4 flex justify-between items-start cursor-pointer hover:shadow-sm transition-shadow"
          >
            <div className="flex items-start gap-3 flex-1 min-w-0" onClick={() => setDetailJob(job)}>
              <input
                type="checkbox"
                checked={selected.includes(job.id)}
                onChange={(e) => { e.stopPropagation(); toggleSelect(job.id); }}
                onClick={(e) => e.stopPropagation()}
                className="mt-1 rounded"
              />
              <div className="min-w-0">
                <h3 className="font-medium text-gray-900">{job.title}</h3>
                <p className="text-sm text-gray-500">{job.company} {job.location ? `- ${job.location}` : ''}</p>
                <div className="flex gap-3 mt-2 text-xs text-gray-400 flex-wrap">
                  {job.source && <span>{job.source}</span>}
                  {job.salary_range && (
                    <span className="text-green-600 font-medium">{job.salary_range}</span>
                  )}
                  {job.fit_score != null && (
                    <span className={`font-medium ${job.fit_score >= 7 ? 'text-green-600' : job.fit_score >= 5 ? 'text-yellow-600' : 'text-red-600'}`}>
                      Fit: {job.fit_score}/10
                    </span>
                  )}
                  {job.url && (
                    <span className="text-blue-500">Has link</span>
                  )}
                  {job.jd_text && (
                    <span className="text-purple-500">JD parsed</span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex gap-2 shrink-0 items-center">
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusBadge[job.status || ''] || 'bg-gray-100 text-gray-600'}`}>
                {job.status}
              </span>
              {job.status !== 'applied' && (
                <>
                  <button
                    onClick={(e) => { e.stopPropagation(); convertJob.mutate(job.id); }}
                    className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700"
                    title="Convert to application"
                  >
                    Convert
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); applyJob.mutate(job.id); }}
                    className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700"
                  >
                    Apply
                  </button>
                </>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); deleteJob.mutate(job.id); }}
                className="px-3 py-1 bg-red-50 text-red-600 text-xs rounded hover:bg-red-100"
              >
                Remove
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Detail Panel */}
      {detailJob && <JobDetailPanel job={detailJob} onClose={() => setDetailJob(null)} />}
    </div>
  );
}
