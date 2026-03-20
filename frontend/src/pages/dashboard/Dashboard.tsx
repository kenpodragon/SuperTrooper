import { useQuery } from '@tanstack/react-query';
import { applications, interviews, savedJobs, staleApps, activity } from '../../api/client';
import type { Application, Interview, SavedJob, ActivityItem } from '../../api/client';

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-semibold text-gray-900 mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

export default function Dashboard() {
  const apps = useQuery({ queryKey: ['applications'], queryFn: () => applications.list('?limit=200') });
  const intv = useQuery({ queryKey: ['interviews-upcoming'], queryFn: () => interviews.list('?limit=10') });
  const jobs = useQuery({ queryKey: ['saved-jobs'], queryFn: () => savedJobs.list('?status=saved&limit=5') });
  const stale = useQuery({ queryKey: ['stale-apps'], queryFn: () => staleApps.list(14) });
  const recent = useQuery({ queryKey: ['activity-recent'], queryFn: () => activity.list('?limit=10&days=7') });

  const appData = apps.data ?? [];
  const byStatus: Record<string, number> = {};
  appData.forEach((a: Application) => {
    const s = a.status || 'Unknown';
    byStatus[s] = (byStatus[s] || 0) + 1;
  });

  const activeStatuses = ['Applied', 'Phone Screen', 'Interview', 'Technical', 'Final'];
  const activeCount = activeStatuses.reduce((n, s) => n + (byStatus[s] || 0), 0);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Applications" value={appData.length} />
        <StatCard label="Active Pipeline" value={activeCount} sub={activeStatuses.filter(s => byStatus[s]).map(s => `${s}: ${byStatus[s]}`).join(', ')} />
        <StatCard label="Saved Jobs" value={jobs.data?.length ?? '...'} sub="Awaiting evaluation" />
        <StatCard label="Stale (14d+)" value={stale.data?.length ?? '...'} sub="Need follow-up" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Status Breakdown */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Pipeline by Status</h2>
          {Object.entries(byStatus).sort((a, b) => b[1] - a[1]).map(([status, count]) => (
            <div key={status} className="flex justify-between py-1.5 border-b border-gray-100 last:border-0">
              <span className="text-sm text-gray-700">{status}</span>
              <span className="text-sm font-medium text-gray-900">{count}</span>
            </div>
          ))}
          {apps.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
        </div>

        {/* Upcoming Interviews */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Recent Interviews</h2>
          {(intv.data ?? []).slice(0, 5).map((i: Interview) => (
            <div key={i.id} className="flex justify-between py-1.5 border-b border-gray-100 last:border-0">
              <div>
                <p className="text-sm font-medium text-gray-700">{i.company_name}</p>
                <p className="text-xs text-gray-400">{i.type} - {i.role}</p>
              </div>
              <div className="text-right">
                <p className="text-xs text-gray-500">{i.date ? new Date(i.date).toLocaleDateString() : '-'}</p>
                <p className="text-xs text-gray-400">{i.outcome || 'pending'}</p>
              </div>
            </div>
          ))}
          {intv.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
          {!intv.isLoading && (intv.data ?? []).length === 0 && <p className="text-sm text-gray-400">No interviews found</p>}
        </div>

        {/* Stale Applications */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Needs Follow-up</h2>
          {(stale.data ?? []).slice(0, 5).map((a: Application & { days_stale?: number; follow_up_count?: number }) => (
            <div key={a.id} className="flex justify-between py-1.5 border-b border-gray-100 last:border-0">
              <div>
                <p className="text-sm font-medium text-gray-700">{a.company_name}</p>
                <p className="text-xs text-gray-400">{a.role}</p>
              </div>
              <div className="text-right">
                <p className="text-xs text-red-500">{a.days_stale}d stale</p>
                <p className="text-xs text-gray-400">{a.follow_up_count} follow-ups</p>
              </div>
            </div>
          ))}
          {stale.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
        </div>

        {/* Recent Activity */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Recent Activity</h2>
          {(recent.data ?? []).slice(0, 8).map((a: ActivityItem) => (
            <div key={a.id} className="py-1.5 border-b border-gray-100 last:border-0">
              <p className="text-sm text-gray-700">{a.action.replace(/_/g, ' ')}</p>
              <p className="text-xs text-gray-400">{a.entity_type} #{a.entity_id} - {a.created_at ? new Date(a.created_at).toLocaleString() : ''}</p>
            </div>
          ))}
          {recent.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
          {!recent.isLoading && (recent.data ?? []).length === 0 && <p className="text-sm text-gray-400">No recent activity</p>}
        </div>
      </div>
    </div>
  );
}
