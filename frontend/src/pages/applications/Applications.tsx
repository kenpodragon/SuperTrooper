import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { applications, emails } from '../../api/client';
import type { Application, EmailIntelStatus } from '../../api/client';

const STATUSES = ['All', 'Applied', 'Phone Screen', 'Interview', 'Technical', 'Final', 'Offer', 'Accepted', 'Rejected', 'Ghosted', 'Withdrawn', 'Rescinded'];

const statusColor: Record<string, string> = {
  Applied: 'bg-blue-100 text-blue-700',
  'Phone Screen': 'bg-purple-100 text-purple-700',
  Interview: 'bg-indigo-100 text-indigo-700',
  Technical: 'bg-cyan-100 text-cyan-700',
  Final: 'bg-amber-100 text-amber-700',
  Offer: 'bg-green-100 text-green-700',
  Accepted: 'bg-green-200 text-green-800',
  Rejected: 'bg-red-100 text-red-700',
  Ghosted: 'bg-gray-100 text-gray-500',
  Withdrawn: 'bg-gray-100 text-gray-500',
  Rescinded: 'bg-red-200 text-red-800',
};

export default function Applications() {
  const [filter, setFilter] = useState('All');
  const qc = useQueryClient();

  const params = filter === 'All' ? '?limit=100' : `?status=${encodeURIComponent(filter)}&limit=100`;
  const { data, isLoading } = useQuery({
    queryKey: ['applications', filter],
    queryFn: () => applications.list(params),
  });

  const emailStatus = useQuery({
    queryKey: ['email-intel-status'],
    queryFn: () => emails.intelligenceStatus(),
  });
  const emailData: EmailIntelStatus | undefined = emailStatus.data;

  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      applications.update(id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['applications'] }),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Applications</h1>
        <span className="text-sm text-gray-500">{data?.length ?? 0} results</span>
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

      <div className="flex gap-2 mb-4 flex-wrap">
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

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Company</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Role</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Status</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Source</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Applied</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
            )}
            {(data ?? []).map((app: Application) => (
              <tr key={app.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{app.company_name || '-'}</td>
                <td className="px-4 py-3 text-gray-700">{app.role || '-'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor[app.status || ''] || 'bg-gray-100 text-gray-600'}`}>
                    {app.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500">{app.source || '-'}</td>
                <td className="px-4 py-3 text-gray-500">{app.date_applied || '-'}</td>
                <td className="px-4 py-3">
                  <select
                    className="text-xs border border-gray-200 rounded px-2 py-1"
                    value=""
                    onChange={(e) => {
                      if (e.target.value) updateStatus.mutate({ id: app.id, status: e.target.value });
                    }}
                  >
                    <option value="">Move to...</option>
                    {STATUSES.filter(s => s !== 'All' && s !== app.status).map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
