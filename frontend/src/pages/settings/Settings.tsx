import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';

export default function Settings() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<{ status: string; db: string }>('/health'),
  });

  const kb = useQuery({
    queryKey: ['kb-counts'],
    queryFn: () => api.get<{ counts: Record<string, number> }>('/kb/export'),
    select: (d) => d.counts,
  });

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* System Status */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">System Status</h2>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">API</span>
              <span className={`text-sm font-medium ${health.data?.status === 'healthy' ? 'text-green-600' : 'text-red-600'}`}>
                {health.data?.status ?? 'checking...'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">Database</span>
              <span className="text-sm font-medium text-green-600">{health.data?.db ?? '...'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">Frontend</span>
              <span className="text-sm font-medium text-green-600">running</span>
            </div>
          </div>
        </div>

        {/* Data Counts */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Knowledge Base</h2>
          {kb.data && Object.entries(kb.data).map(([key, count]) => (
            <div key={key} className="flex justify-between py-1.5 border-b border-gray-100 last:border-0">
              <span className="text-sm text-gray-500">{key.replace(/_/g, ' ')}</span>
              <span className="text-sm font-medium text-gray-900">{count}</span>
            </div>
          ))}
          {kb.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
        </div>
      </div>
    </div>
  );
}
