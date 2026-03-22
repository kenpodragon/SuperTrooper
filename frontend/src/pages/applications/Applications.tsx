import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { applications, emails, api, gapAnalyses } from '../../api/client';
import type { Application, EmailIntelStatus, GapAnalysis } from '../../api/client';

const KANBAN_STATUSES = ['Applied', 'Phone Screen', 'Interview', 'Technical', 'Final', 'Offer', 'Accepted', 'Rejected', 'Ghosted', 'Withdrawn'] as const;
const ALL_STATUSES = ['All', 'Stale', ...KANBAN_STATUSES];

const statusColor: Record<string, string> = {
  Applied: 'bg-blue-100 text-blue-700 border-blue-200',
  'Phone Screen': 'bg-purple-100 text-purple-700 border-purple-200',
  Interview: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  Technical: 'bg-cyan-100 text-cyan-700 border-cyan-200',
  Final: 'bg-amber-100 text-amber-700 border-amber-200',
  Offer: 'bg-green-100 text-green-700 border-green-200',
  Accepted: 'bg-green-200 text-green-800 border-green-300',
  Rejected: 'bg-red-100 text-red-700 border-red-200',
  Ghosted: 'bg-gray-100 text-gray-500 border-gray-200',
  Withdrawn: 'bg-gray-100 text-gray-500 border-gray-200',
  Rescinded: 'bg-red-200 text-red-800 border-red-300',
};

const kanbanColumnColor: Record<string, string> = {
  Applied: 'border-t-blue-400',
  'Phone Screen': 'border-t-purple-400',
  Interview: 'border-t-indigo-400',
  Technical: 'border-t-cyan-400',
  Final: 'border-t-amber-400',
  Offer: 'border-t-green-400',
  Accepted: 'border-t-green-500',
  Rejected: 'border-t-red-400',
  Ghosted: 'border-t-gray-400',
  Withdrawn: 'border-t-gray-300',
};

function daysSince(dateStr?: string): number | null {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  const now = new Date();
  return Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
}

function StaleBadge({ app }: { app: Application }) {
  const days = daysSince(app.last_status_change || app.date_applied);
  if (days == null || days < 14) return null;
  const color = days >= 30 ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700';
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded ${color}`} title={`${days} days since last update`}>
      {days}d stale
    </span>
  );
}

interface QuickViewData {
  app: Application;
  gap?: GapAnalysis | null;
}

function QuickViewPanel({ data, onClose }: { data: QuickViewData; onClose: () => void }) {
  const { app, gap } = data;
  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-white shadow-xl border-l border-gray-200 z-50 overflow-y-auto">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Application Details</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
      </div>
      <div className="p-4 space-y-4">
        <div>
          <h3 className="text-sm font-medium text-gray-500 mb-1">Company & Role</h3>
          <p className="text-base font-semibold text-gray-900">{app.company_name}</p>
          <p className="text-sm text-gray-700">{app.role}</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <p className="text-xs text-gray-500">Status</p>
            <span className={`inline-block mt-1 px-2 py-0.5 rounded-full text-xs font-medium ${statusColor[app.status || ''] || 'bg-gray-100'}`}>
              {app.status}
            </span>
          </div>
          <div>
            <p className="text-xs text-gray-500">Source</p>
            <p className="text-sm text-gray-800 mt-1">{app.source || '-'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Applied</p>
            <p className="text-sm text-gray-800 mt-1">{app.date_applied || '-'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Last Update</p>
            <p className="text-sm text-gray-800 mt-1">{app.last_status_change || '-'}</p>
          </div>
        </div>
        {app.contact_name && (
          <div>
            <p className="text-xs text-gray-500">Contact</p>
            <p className="text-sm text-gray-800">{app.contact_name} {app.contact_email ? `(${app.contact_email})` : ''}</p>
          </div>
        )}
        {app.jd_url && (
          <div>
            <p className="text-xs text-gray-500">JD URL</p>
            <a href={app.jd_url} target="_blank" rel="noreferrer" className="text-sm text-blue-600 hover:underline break-all">{app.jd_url}</a>
          </div>
        )}
        {app.resume_version && (
          <div>
            <p className="text-xs text-gray-500">Resume Version</p>
            <p className="text-sm text-gray-800">{app.resume_version}</p>
          </div>
        )}
        {app.notes && (
          <div>
            <p className="text-xs text-gray-500">Notes</p>
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{app.notes}</p>
          </div>
        )}
        {gap && (
          <div className="border-t border-gray-200 pt-3">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Gap Analysis</h3>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs text-gray-500">Overall Score:</span>
              <span className={`text-sm font-semibold ${(gap.overall_score ?? 0) >= 70 ? 'text-green-700' : (gap.overall_score ?? 0) >= 50 ? 'text-yellow-700' : 'text-red-700'}`}>
                {gap.overall_score ?? 'N/A'}
              </span>
            </div>
            {gap.recommendation && (
              <p className="text-xs text-gray-600">{gap.recommendation}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Applications() {
  const [filter, setFilter] = useState('All');
  const [viewMode, setViewMode] = useState<'table' | 'kanban'>('kanban');
  const [quickView, setQuickView] = useState<QuickViewData | null>(null);
  const qc = useQueryClient();

  const params = filter === 'All' || filter === 'Stale' ? '?limit=100' : `?status=${encodeURIComponent(filter)}&limit=100`;
  const { data, isLoading } = useQuery({
    queryKey: ['applications', filter === 'Stale' ? 'All' : filter],
    queryFn: () => applications.list(params),
  });

  const emailStatus = useQuery({
    queryKey: ['email-intel-status'],
    queryFn: () => emails.intelligenceStatus(),
  });
  const emailData: EmailIntelStatus | undefined = emailStatus.data;

  const { data: staleApps } = useQuery({
    queryKey: ['stale-applications'],
    queryFn: () => api.get<Application[]>('/applications/stale?days=14'),
  });

  const { data: gapData } = useQuery({
    queryKey: ['gap-analyses'],
    queryFn: () => gapAnalyses.list('?limit=100'),
  });

  const gapMap: Record<number, GapAnalysis> = {};
  (gapData ?? []).forEach((g: GapAnalysis) => {
    if (g.application_id) gapMap[g.application_id] = g;
  });

  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      applications.update(id, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['applications'] });
      qc.invalidateQueries({ queryKey: ['stale-applications'] });
    },
  });

  const detectGhosted = useMutation({
    mutationFn: () => api.post<{ updated: number }>('/pipeline/detect-ghosted', {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['applications'] });
      qc.invalidateQueries({ queryKey: ['stale-applications'] });
    },
  });

  const staleIds = new Set((staleApps ?? []).map((a: Application) => a.id));
  const allApps = data ?? [];
  const appList = filter === 'Stale' ? allApps.filter((a: Application) => staleIds.has(a.id)) : allApps;

  // Group by status for kanban
  const byStatus: Record<string, Application[]> = {};
  KANBAN_STATUSES.forEach(s => { byStatus[s] = []; });
  appList.forEach((app: Application) => {
    const s = app.status || 'Applied';
    if (byStatus[s]) byStatus[s].push(app);
  });

  function openQuickView(app: Application) {
    setQuickView({ app, gap: gapMap[app.id] ?? null });
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Applications</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={() => detectGhosted.mutate()}
            disabled={detectGhosted.isPending}
            className="px-3 py-1.5 bg-gray-700 text-white text-xs rounded hover:bg-gray-600 disabled:opacity-50"
          >
            {detectGhosted.isPending ? 'Detecting...' : 'Detect Ghosted'}
          </button>
          {detectGhosted.isSuccess && (
            <span className="text-xs text-green-600">
              {(detectGhosted.data as any)?.updated ?? 0} marked ghosted
            </span>
          )}
          <div className="flex border border-gray-200 rounded overflow-hidden">
            <button
              onClick={() => setViewMode('kanban')}
              className={`px-3 py-1.5 text-xs ${viewMode === 'kanban' ? 'bg-gray-900 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
            >
              Kanban
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={`px-3 py-1.5 text-xs ${viewMode === 'table' ? 'bg-gray-900 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
            >
              Table
            </button>
          </div>
          <span className="text-sm text-gray-500">{appList.length} results</span>
        </div>
      </div>

      {emailData && emailData.unlinked_categorized > 0 && (
        <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-center justify-between">
          <div className="text-sm text-amber-800">
            <span className="font-medium">{emailData.unlinked_categorized} categorized emails</span> not yet linked to applications.
            {' '}{emailData.scanned} of {emailData.total_emails.toLocaleString()} emails scanned
            {emailData.breakdown.interview ? ` (${emailData.breakdown.interview} interview-related)` : ''}.
          </div>
        </div>
      )}

      {/* Stale apps summary */}
      {(staleApps ?? []).length > 0 && (
        <div
          className="mb-4 p-3 bg-orange-50 border border-orange-200 rounded-lg cursor-pointer hover:bg-orange-100 transition-colors"
          onClick={() => { setFilter('Stale'); setViewMode('table'); }}
        >
          <div className="text-sm text-orange-800">
            <span className="font-medium">{(staleApps ?? []).length} stale applications</span> need follow-up (14+ days without status change).
            <span className="ml-2 text-xs underline">View all &rarr;</span>
          </div>
        </div>
      )}

      {viewMode === 'table' && (
        <>
          <div className="flex gap-2 mb-4 flex-wrap">
            {ALL_STATUSES.map((s) => (
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

          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Company</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Role</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Status</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Source</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Applied</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Gap</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody>
                {isLoading && (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
                )}
                {appList.map((app: Application) => (
                  <tr key={app.id} className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer" onClick={() => openQuickView(app)}>
                    <td className="px-4 py-3 font-medium text-gray-900">
                      <div className="flex items-center gap-2">
                        {app.company_name || '-'}
                        {staleIds.has(app.id) && <StaleBadge app={app} />}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{app.role || '-'}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor[app.status || ''] || 'bg-gray-100 text-gray-600'}`}>
                        {app.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{app.source || '-'}</td>
                    <td className="px-4 py-3 text-gray-500">{app.date_applied || '-'}</td>
                    <td className="px-4 py-3 text-gray-500">
                      {gapMap[app.id] ? (
                        <span className={`text-xs font-medium ${(gapMap[app.id].overall_score ?? 0) >= 70 ? 'text-green-600' : 'text-yellow-600'}`}>
                          {gapMap[app.id].overall_score}%
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <select
                        className="text-xs border border-gray-200 rounded px-2 py-1"
                        value=""
                        onChange={(e) => {
                          if (e.target.value) updateStatus.mutate({ id: app.id, status: e.target.value });
                        }}
                      >
                        <option value="">Move to...</option>
                        {KANBAN_STATUSES.filter(s => s !== app.status).map(s => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {viewMode === 'kanban' && (
        <div className="flex gap-3 overflow-x-auto pb-4">
          {KANBAN_STATUSES.map(status => (
            <div
              key={status}
              className={`flex-shrink-0 w-56 bg-gray-50 rounded-lg border border-gray-200 border-t-4 ${kanbanColumnColor[status] || 'border-t-gray-300'}`}
            >
              <div className="p-3 border-b border-gray-200">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">{status}</h3>
                  <span className="text-xs text-gray-400 bg-white rounded-full px-2 py-0.5">{byStatus[status].length}</span>
                </div>
              </div>
              <div className="p-2 space-y-2 max-h-[calc(100vh-300px)] overflow-y-auto">
                {isLoading && <p className="text-xs text-gray-400 p-2">Loading...</p>}
                {byStatus[status].map((app: Application) => (
                  <div
                    key={app.id}
                    className="bg-white rounded border border-gray-200 p-2.5 cursor-pointer hover:shadow-sm transition-shadow"
                    onClick={() => openQuickView(app)}
                  >
                    <p className="text-xs font-medium text-gray-900 truncate">{app.company_name || 'Unknown'}</p>
                    <p className="text-xs text-gray-600 truncate mt-0.5">{app.role || '-'}</p>
                    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                      {app.source && <span className="text-xs text-gray-400">{app.source}</span>}
                      {staleIds.has(app.id) && <StaleBadge app={app} />}
                      {gapMap[app.id] && (
                        <span className={`text-xs font-medium ${(gapMap[app.id].overall_score ?? 0) >= 70 ? 'text-green-600' : 'text-yellow-600'}`}>
                          {gapMap[app.id].overall_score}%
                        </span>
                      )}
                    </div>
                    <div className="mt-2" onClick={(e) => e.stopPropagation()}>
                      <select
                        className="text-xs border border-gray-200 rounded px-1.5 py-0.5 w-full bg-gray-50"
                        value=""
                        onChange={(e) => {
                          if (e.target.value) updateStatus.mutate({ id: app.id, status: e.target.value });
                        }}
                      >
                        <option value="">Move to...</option>
                        {KANBAN_STATUSES.filter(s => s !== status).map(s => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                ))}
                {!isLoading && byStatus[status].length === 0 && (
                  <p className="text-xs text-gray-400 italic p-2">None</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Quick View Panel */}
      {quickView && <QuickViewPanel data={quickView} onClose={() => setQuickView(null)} />}
    </div>
  );
}
