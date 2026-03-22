import { useQuery } from '@tanstack/react-query';
import { api, emails } from '../../api/client';
import type { EmailIntelStatus } from '../../api/client';

interface FunnelStage {
  status: string;
  count: number;
}

interface VelocityData {
  total_applications?: number;
  response_rate?: number;
  avg_days_to_response?: number;
  weekly_applications?: number;
  interview_rate?: number;
  offer_rate?: number;
  rejection_rate?: number;
  // fields from /analytics/summary
  applied?: number;
  in_progress?: number;
  offers?: number;
  rejected?: number;
  ghosted?: number;
  total_interviews?: number;
  total_companies?: number;
  total_contacts?: number;
  total_emails?: number;
  unique_sources?: number;
}

interface SourceEntry {
  source: string;
  count: number;
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-semibold text-gray-900 mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="w-full bg-gray-100 rounded-full h-2 mt-1">
      <div
        className="bg-blue-500 h-2 rounded-full"
        style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
      />
    </div>
  );
}

export default function Analytics() {
  const funnel = useQuery({
    queryKey: ['analytics-funnel'],
    queryFn: () => api.get<FunnelStage[]>('/analytics/funnel'),
  });

  const velocity = useQuery({
    queryKey: ['analytics-velocity'],
    queryFn: () => api.get<VelocityData>('/analytics/summary'),
  });

  const sources = useQuery({
    queryKey: ['analytics-sources'],
    queryFn: () => api.get<SourceEntry[]>('/analytics/sources'),
  });

  const emailStatus = useQuery({
    queryKey: ['email-intel-status'],
    queryFn: () => emails.intelligenceStatus(),
  });
  const emailData: EmailIntelStatus | undefined = emailStatus.data;

  const funnelData = funnel.data ?? [];
  const velData: VelocityData = velocity.data ?? {};
  const sourceData = sources.data ?? [];

  const totalApps = velData.total_applications ?? funnelData.reduce((s: number, f: FunnelStage) => s + (f.count || 0), 0);
  const maxCount = funnelData.reduce((m: number, f: FunnelStage) => Math.max(m, f.count || 0), 1);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Analytics</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Applications" value={totalApps || '...'} />
        <StatCard
          label="Response Rate"
          value={velData.response_rate != null ? `${velData.response_rate}%` : '...'}
        />
        <StatCard
          label="Avg Days to Response"
          value={velData.avg_days_to_response != null ? `${velData.avg_days_to_response}d` : '...'}
        />
        <StatCard
          label="Top Source"
          value={sourceData[0]?.source ?? '...'}
          sub={sourceData[0]?.count ? `${sourceData[0].count} apps` : undefined}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Pipeline Funnel */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Pipeline Funnel</h2>
          {funnel.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
          {funnelData.map((stage: FunnelStage) => {
            const pct = maxCount > 0 ? Math.round((stage.count / maxCount) * 100) : 0;
            const ofTotal = totalApps > 0 ? Math.round((stage.count / totalApps) * 100) : 0;
            return (
              <div key={stage.status} className="mb-3">
                <div className="flex justify-between text-sm mb-0.5">
                  <span className="text-gray-700">{stage.status}</span>
                  <span className="text-gray-500 font-medium">{stage.count} <span className="text-gray-400 font-normal">({ofTotal}%)</span></span>
                </div>
                <ProgressBar pct={pct} />
              </div>
            );
          })}
          {!funnel.isLoading && funnelData.length === 0 && (
            <p className="text-sm text-gray-400">No funnel data yet.</p>
          )}
        </div>

        {/* Source Breakdown */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Applications by Source</h2>
          {sources.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
          {sourceData.map((s: SourceEntry) => {
            const pct = totalApps > 0 ? Math.round((s.count / totalApps) * 100) : 0;
            return (
              <div key={s.source} className="mb-3">
                <div className="flex justify-between text-sm mb-0.5">
                  <span className="text-gray-700">{s.source}</span>
                  <span className="text-gray-500 font-medium">{s.count} <span className="text-gray-400 font-normal">({pct}%)</span></span>
                </div>
                <ProgressBar pct={pct} />
              </div>
            );
          })}
          {!sources.isLoading && sourceData.length === 0 && (
            <p className="text-sm text-gray-400">No source data yet.</p>
          )}
        </div>

        {/* Velocity Metrics */}
        <div className="bg-white rounded-lg border border-gray-200 p-4 md:col-span-2">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Velocity Breakdown</h2>
          {velocity.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
          {!velocity.isLoading && Object.entries(velData).length === 0 && (
            <p className="text-sm text-gray-400">No velocity data yet.</p>
          )}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {velData.weekly_applications != null && (
              <div className="text-center">
                <p className="text-2xl font-semibold text-gray-900">{velData.weekly_applications}</p>
                <p className="text-xs text-gray-500 mt-1">Apps this week</p>
              </div>
            )}
            {velData.interview_rate != null && (
              <div className="text-center">
                <p className="text-2xl font-semibold text-gray-900">{velData.interview_rate}%</p>
                <p className="text-xs text-gray-500 mt-1">Interview Rate</p>
              </div>
            )}
            {velData.offer_rate != null && (
              <div className="text-center">
                <p className="text-2xl font-semibold text-gray-900">{velData.offer_rate}%</p>
                <p className="text-xs text-gray-500 mt-1">Offer Rate</p>
              </div>
            )}
            {velData.rejection_rate != null && (
              <div className="text-center">
                <p className="text-2xl font-semibold text-gray-900">{velData.rejection_rate}%</p>
                <p className="text-xs text-gray-500 mt-1">Rejection Rate</p>
              </div>
            )}
          </div>
        </div>

        {/* Email Intelligence */}
        <div className="bg-white rounded-lg border border-gray-200 p-4 md:col-span-2">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Email Intelligence</h2>
          {emailStatus.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
          {emailData && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <p className="text-2xl font-semibold text-gray-900">{emailData.total_emails.toLocaleString()}</p>
                <p className="text-xs text-gray-500 mt-1">Total Emails</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-semibold text-gray-900">{emailData.scanned}</p>
                <p className="text-xs text-gray-500 mt-1">Scanned</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-semibold text-amber-600">{emailData.unlinked_categorized}</p>
                <p className="text-xs text-gray-500 mt-1">Unlinked Categorized</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-semibold text-gray-900">
                  {emailData.total_emails > 0 ? Math.round((emailData.scanned / emailData.total_emails) * 100) : 0}%
                </p>
                <p className="text-xs text-gray-500 mt-1">Scan Coverage</p>
              </div>
              {Object.entries(emailData.breakdown)
                .filter(([k]) => k !== 'scanned')
                .map(([cat, count]) => (
                  <div key={cat} className="text-center">
                    <p className="text-xl font-semibold text-gray-900">{count}</p>
                    <p className="text-xs text-gray-500 mt-1 capitalize">{cat}</p>
                  </div>
                ))}
            </div>
          )}
          {!emailStatus.isLoading && !emailData && (
            <p className="text-sm text-gray-400">No email intelligence data yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
