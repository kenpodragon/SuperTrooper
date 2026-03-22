import { useQuery } from '@tanstack/react-query';
import { api, applications, interviews, savedJobs, staleApps, activity, emails } from '../../api/client';
import type { Application, Interview, SavedJob, ActivityItem, EmailIntelStatus } from '../../api/client';

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-semibold text-gray-900 mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

interface WeeklyDigest {
  period?: string;
  applications_sent?: number;
  interviews_scheduled?: number;
  offers_received?: number;
  rejections?: number;
  follow_ups_sent?: number;
  new_contacts?: number;
  summary?: string;
}

interface MarketSignal {
  id?: number;
  signal_type?: string;
  title?: string;
  description?: string;
  source?: string;
  relevance_score?: number;
  created_at?: string;
}

interface StaleApp {
  id: number;
  company_name?: string;
  role?: string;
  status?: string;
  days_stale?: number;
  follow_up_count?: number;
  last_status_change?: string;
}

export default function Dashboard() {
  const apps = useQuery({ queryKey: ['applications'], queryFn: () => applications.list('?limit=200') });
  const intv = useQuery({ queryKey: ['interviews-upcoming'], queryFn: () => interviews.list('?limit=10') });
  const jobs = useQuery({ queryKey: ['saved-jobs'], queryFn: () => savedJobs.list('?status=saved&limit=5') });
  const stale = useQuery({ queryKey: ['stale-apps'], queryFn: () => staleApps.list(14) });
  const recent = useQuery({ queryKey: ['activity-recent'], queryFn: () => activity.list('?limit=10&days=7') });
  const emailStatus = useQuery({ queryKey: ['email-intel-status'], queryFn: () => emails.intelligenceStatus() });

  const weeklyDigest = useQuery({
    queryKey: ['weekly-digest'],
    queryFn: () => api.get<WeeklyDigest>('/reporting/weekly-digest'),
  });

  const marketSignals = useQuery({
    queryKey: ['market-signals'],
    queryFn: () => api.get<MarketSignal[]>('/market-intelligence/signals?limit=5'),
  });

  const staleAlerts = useQuery({
    queryKey: ['stale-alerts'],
    queryFn: () => api.get<StaleApp[]>('/aging/stale-applications'),
  });

  const appData = apps.data ?? [];
  const emailData: EmailIntelStatus | undefined = emailStatus.data;
  const byStatus: Record<string, number> = {};
  appData.forEach((a: Application) => {
    const s = a.status || 'Unknown';
    byStatus[s] = (byStatus[s] || 0) + 1;
  });

  const activeStatuses = ['Applied', 'Phone Screen', 'Interview', 'Technical', 'Final'];
  const activeCount = activeStatuses.reduce((n, s) => n + (byStatus[s] || 0), 0);

  const digest = weeklyDigest.data;
  const signals: MarketSignal[] = Array.isArray(marketSignals.data) ? marketSignals.data : [];
  const staleList: StaleApp[] = Array.isArray(staleAlerts.data) ? staleAlerts.data : [];

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
        {/* Weekly Digest */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Weekly Digest</h2>
          {weeklyDigest.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
          {weeklyDigest.isError && <p className="text-sm text-gray-400">Weekly digest unavailable</p>}
          {digest && (
            <>
              {digest.period && <p className="text-xs text-gray-400 mb-2">{digest.period}</p>}
              <div className="grid grid-cols-3 gap-3 mb-3">
                {digest.applications_sent != null && (
                  <div className="text-center">
                    <p className="text-lg font-semibold text-gray-900">{digest.applications_sent}</p>
                    <p className="text-xs text-gray-500">Applied</p>
                  </div>
                )}
                {digest.interviews_scheduled != null && (
                  <div className="text-center">
                    <p className="text-lg font-semibold text-gray-900">{digest.interviews_scheduled}</p>
                    <p className="text-xs text-gray-500">Interviews</p>
                  </div>
                )}
                {digest.offers_received != null && (
                  <div className="text-center">
                    <p className="text-lg font-semibold text-green-600">{digest.offers_received}</p>
                    <p className="text-xs text-gray-500">Offers</p>
                  </div>
                )}
              </div>
              <div className="space-y-1">
                {digest.rejections != null && (
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span className="text-sm text-gray-500">Rejections</span>
                    <span className="text-sm text-gray-700">{digest.rejections}</span>
                  </div>
                )}
                {digest.follow_ups_sent != null && (
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span className="text-sm text-gray-500">Follow-ups Sent</span>
                    <span className="text-sm text-gray-700">{digest.follow_ups_sent}</span>
                  </div>
                )}
                {digest.new_contacts != null && (
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span className="text-sm text-gray-500">New Contacts</span>
                    <span className="text-sm text-gray-700">{digest.new_contacts}</span>
                  </div>
                )}
              </div>
              {digest.summary && <p className="text-sm text-gray-600 mt-2">{digest.summary}</p>}
            </>
          )}
          {!weeklyDigest.isLoading && !weeklyDigest.isError && !digest && (
            <p className="text-sm text-gray-400">No digest data available</p>
          )}
        </div>

        {/* Market Signals */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Market Signals</h2>
          {marketSignals.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
          {marketSignals.isError && <p className="text-sm text-gray-400">Market signals unavailable</p>}
          {signals.length > 0 && signals.map((sig, idx) => (
            <div key={sig.id ?? idx} className="py-2 border-b border-gray-100 last:border-0">
              <div className="flex justify-between items-start">
                <p className="text-sm font-medium text-gray-900">{sig.title || sig.signal_type}</p>
                {sig.relevance_score != null && (
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    sig.relevance_score >= 0.7 ? 'bg-green-100 text-green-700' :
                    sig.relevance_score >= 0.4 ? 'bg-yellow-100 text-yellow-700' :
                    'bg-gray-100 text-gray-500'
                  }`}>
                    {Math.round(sig.relevance_score * 100)}%
                  </span>
                )}
              </div>
              {sig.description && <p className="text-xs text-gray-500 mt-0.5">{sig.description}</p>}
              <div className="flex gap-2 mt-1">
                {sig.signal_type && <span className="text-xs bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">{sig.signal_type}</span>}
                {sig.source && <span className="text-xs text-gray-400">{sig.source}</span>}
              </div>
            </div>
          ))}
          {!marketSignals.isLoading && !marketSignals.isError && signals.length === 0 && (
            <p className="text-sm text-gray-400">No market signals available</p>
          )}
        </div>

        {/* Stale Applications Alert */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Stale Applications</h2>
          {staleAlerts.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
          {staleAlerts.isError && (
            // Fall back to existing stale data
            <>
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
            </>
          )}
          {staleList.length > 0 && staleList.slice(0, 7).map((a) => (
            <div key={a.id} className="flex justify-between py-1.5 border-b border-gray-100 last:border-0">
              <div>
                <p className="text-sm font-medium text-gray-700">{a.company_name}</p>
                <p className="text-xs text-gray-400">{a.role} - {a.status}</p>
              </div>
              <div className="text-right">
                <p className="text-xs text-red-500">{a.days_stale}d stale</p>
                <p className="text-xs text-gray-400">{a.follow_up_count ?? 0} follow-ups</p>
              </div>
            </div>
          ))}
          {!staleAlerts.isLoading && !staleAlerts.isError && staleList.length === 0 && (
            <p className="text-sm text-gray-400">No stale applications</p>
          )}
        </div>

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

        {/* Email Intelligence */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Email Intelligence</h2>
          {emailStatus.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
          {emailData && (
            <>
              <div className="flex justify-between py-1.5 border-b border-gray-100">
                <span className="text-sm text-gray-700">Total Emails</span>
                <span className="text-sm font-medium text-gray-900">{emailData.total_emails.toLocaleString()}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-gray-100">
                <span className="text-sm text-gray-700">Scanned</span>
                <span className="text-sm font-medium text-gray-900">{emailData.scanned}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-gray-100">
                <span className="text-sm text-gray-700">Unlinked</span>
                <span className="text-sm font-medium text-amber-600">{emailData.unlinked_categorized}</span>
              </div>
              {Object.entries(emailData.breakdown)
                .filter(([k]) => k !== 'scanned')
                .map(([cat, count]) => (
                  <div key={cat} className="flex justify-between py-1.5 border-b border-gray-100 last:border-0">
                    <span className="text-sm text-gray-500 capitalize pl-3">{cat}</span>
                    <span className="text-sm text-gray-700">{count}</span>
                  </div>
                ))}
            </>
          )}
          {!emailStatus.isLoading && !emailData && <p className="text-sm text-gray-400">No email data available</p>}
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
