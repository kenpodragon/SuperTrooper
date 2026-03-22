import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';

interface MarketSignal {
  id: number;
  title?: string;
  content?: string;
  source?: string;
  signal_type?: string;
  severity: string;
  company?: string;
  captured_at?: string;
  data_source?: string;
  metric_value?: number;
}

interface MarketSummary {
  total_signals?: number;
  critical?: number;
  high?: number;
  source_count?: number;
  trend_direction?: string;
}

interface TrendData {
  month: string;
  count: number;
}

interface CompanyActivity {
  company: string;
  signal_count: number;
  latest_signal?: string;
  severity?: string;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-800',
  high: 'bg-orange-100 text-orange-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-gray-100 text-gray-700',
};

const SOURCE_COLORS: Record<string, string> = {
  linkedin: 'bg-blue-100 text-blue-700',
  news: 'bg-purple-100 text-purple-700',
  glassdoor: 'bg-green-100 text-green-700',
  twitter: 'bg-sky-100 text-sky-700',
  manual: 'bg-gray-100 text-gray-700',
  bls: 'bg-indigo-100 text-indigo-700',
  jolts: 'bg-teal-100 text-teal-700',
};

function StatCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`text-2xl font-semibold mt-1 ${color || 'text-gray-900'}`}>{value}</p>
    </div>
  );
}

function TrendBar({ data }: { data: TrendData[] }) {
  if (!data.length) return null;
  const max = Math.max(...data.map(d => d.count), 1);
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="text-sm font-medium text-gray-700 mb-3">Signal Trend (Monthly)</h3>
      <div className="flex items-end gap-1 h-24">
        {data.map(d => (
          <div key={d.month} className="flex-1 flex flex-col items-center gap-1">
            <div
              className="w-full bg-blue-400 rounded-t transition-all"
              style={{ height: `${(d.count / max) * 100}%`, minHeight: d.count > 0 ? '4px' : '0' }}
            />
            <span className="text-xs text-gray-400 -rotate-45 origin-left whitespace-nowrap">{d.month}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function CompanyTimeline({ activities }: { activities: CompanyActivity[] }) {
  if (!activities.length) return null;
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="text-sm font-medium text-gray-700 mb-3">Company Hiring Activity</h3>
      <div className="space-y-2">
        {activities.slice(0, 10).map(a => (
          <div key={a.company} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-800">{a.company}</span>
              {a.severity && (
                <span className={`text-xs px-1.5 py-0.5 rounded ${SEVERITY_COLORS[a.severity] || 'bg-gray-100'}`}>
                  {a.severity}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <div className="w-24 bg-gray-100 rounded-full h-2">
                <div
                  className="bg-blue-500 rounded-full h-2 transition-all"
                  style={{ width: `${Math.min((a.signal_count / Math.max(...activities.map(x => x.signal_count), 1)) * 100, 100)}%` }}
                />
              </div>
              <span className="text-xs text-gray-500 w-6 text-right">{a.signal_count}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function MarketIntel() {
  const [sourceFilter, setSourceFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [viewMode, setViewMode] = useState<'signals' | 'trends' | 'companies'>('signals');

  const params = new URLSearchParams();
  if (sourceFilter) params.set('source', sourceFilter);
  if (typeFilter) params.set('signal_type', typeFilter);
  if (severityFilter) params.set('severity', severityFilter);
  const qs = params.toString() ? `?${params.toString()}` : '';

  const { data: signals, isLoading } = useQuery({
    queryKey: ['market-signals', sourceFilter, typeFilter, severityFilter],
    queryFn: () => api.get<MarketSignal[]>(`/market-intelligence${qs}`),
  });

  const { data: summary } = useQuery({
    queryKey: ['market-summary'],
    queryFn: () => api.get<MarketSummary>('/market-intelligence/summary'),
  });

  const { data: trends } = useQuery({
    queryKey: ['market-trends'],
    queryFn: () => api.get<TrendData[]>('/market-intelligence/trends'),
  });

  const signalList = signals ?? [];
  const summaryData: MarketSummary = summary ?? {};
  const trendData = trends ?? [];

  const sources = Array.from(new Set(signalList.map((s: MarketSignal) => s.source).filter(Boolean)));
  const types = Array.from(new Set(signalList.map((s: MarketSignal) => s.signal_type).filter(Boolean)));

  // Build company activity from signals
  const companyMap: Record<string, CompanyActivity> = {};
  signalList.forEach((s: MarketSignal) => {
    if (s.company) {
      if (!companyMap[s.company]) {
        companyMap[s.company] = { company: s.company, signal_count: 0, severity: s.severity };
      }
      companyMap[s.company].signal_count++;
      if (!companyMap[s.company].latest_signal || (s.captured_at && s.captured_at > (companyMap[s.company].latest_signal || ''))) {
        companyMap[s.company].latest_signal = s.captured_at;
      }
    }
  });
  const companyActivities = Object.values(companyMap).sort((a, b) => b.signal_count - a.signal_count);

  // BLS/JOLTS signals
  const blsSignals = signalList.filter((s: MarketSignal) =>
    s.source === 'bls' || s.source === 'jolts' || s.data_source === 'bls' || s.data_source === 'jolts'
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Market Intelligence</h1>
        <div className="flex border border-gray-200 rounded overflow-hidden">
          {(['signals', 'trends', 'companies'] as const).map(m => (
            <button
              key={m}
              onClick={() => setViewMode(m)}
              className={`px-3 py-1.5 text-xs capitalize ${viewMode === m ? 'bg-gray-900 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Total Signals" value={summaryData.total_signals ?? signalList.length} />
        <StatCard label="Critical" value={summaryData.critical ?? '...'} color="text-red-600" />
        <StatCard label="High Priority" value={summaryData.high ?? '...'} color="text-orange-600" />
        <StatCard label="Sources" value={summaryData.source_count ?? sources.length} />
      </div>

      {/* BLS/JOLTS data summary */}
      {blsSignals.length > 0 && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4 mb-4">
          <h3 className="text-sm font-medium text-indigo-800 mb-2">BLS/JOLTS Data ({blsSignals.length} signals)</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {blsSignals.slice(0, 4).map((s: MarketSignal) => (
              <div key={s.id} className="flex items-center justify-between bg-white rounded p-2 border border-indigo-100">
                <span className="text-xs text-gray-700">{s.title || s.content?.slice(0, 60)}</span>
                {s.metric_value != null && (
                  <span className="text-xs font-semibold text-indigo-700">{s.metric_value}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 mb-4 flex flex-wrap gap-3 items-center">
        <span className="text-sm text-gray-600 font-medium">Filter:</span>
        <select
          className="border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none"
          value={sourceFilter}
          onChange={e => setSourceFilter(e.target.value)}
        >
          <option value="">All Sources</option>
          {['linkedin', 'news', 'glassdoor', 'twitter', 'manual', 'bls', 'jolts', ...sources.filter(s => !['linkedin','news','glassdoor','twitter','manual','bls','jolts'].includes(s))].map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          className="border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none"
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
        >
          <option value="">All Types</option>
          {types.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <select
          className="border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none"
          value={severityFilter}
          onChange={e => setSeverityFilter(e.target.value)}
        >
          <option value="">All Severities</option>
          {['critical', 'high', 'medium', 'low'].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        {(sourceFilter || typeFilter || severityFilter) && (
          <button
            onClick={() => { setSourceFilter(''); setTypeFilter(''); setSeverityFilter(''); }}
            className="text-xs text-gray-500 hover:text-gray-800"
          >
            Clear filters
          </button>
        )}
      </div>

      {viewMode === 'trends' && (
        <div className="space-y-4">
          <TrendBar data={trendData} />
          {/* Industry comparison - aggregate by type */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Signals by Type</h3>
            <div className="space-y-2">
              {types.map(type => {
                const count = signalList.filter((s: MarketSignal) => s.signal_type === type).length;
                return (
                  <div key={type} className="flex items-center justify-between">
                    <span className="text-sm text-gray-700 capitalize">{type}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-32 bg-gray-100 rounded-full h-2">
                        <div
                          className="bg-purple-500 rounded-full h-2"
                          style={{ width: `${Math.min((count / Math.max(signalList.length, 1)) * 100, 100)}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500 w-6 text-right">{count}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {viewMode === 'companies' && (
        <CompanyTimeline activities={companyActivities} />
      )}

      {viewMode === 'signals' && (
        <>
          {isLoading && <p className="text-sm text-gray-400">Loading...</p>}
          {!isLoading && signalList.length === 0 && (
            <p className="text-sm text-gray-400">No signals found.</p>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {signalList.map((signal: MarketSignal) => (
              <div key={signal.id} className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <p className="text-sm font-medium text-gray-900 flex-1">{signal.title ?? signal.content?.slice(0, 80)}</p>
                  <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${SEVERITY_COLORS[signal.severity] ?? 'bg-gray-100 text-gray-600'}`}>
                    {signal.severity}
                  </span>
                </div>
                {signal.content && signal.title && (
                  <p className="text-xs text-gray-600 mb-2 line-clamp-2">{signal.content}</p>
                )}
                <div className="flex items-center gap-2 flex-wrap">
                  {signal.source && (
                    <span className={`text-xs px-2 py-0.5 rounded-full ${SOURCE_COLORS[signal.source] ?? 'bg-gray-100 text-gray-600'}`}>
                      {signal.source}
                    </span>
                  )}
                  {signal.signal_type && (
                    <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full">
                      {signal.signal_type}
                    </span>
                  )}
                  {signal.company && (
                    <span className="text-xs text-gray-500">{signal.company}</span>
                  )}
                  <span className="text-xs text-gray-400 ml-auto">
                    {signal.captured_at ? new Date(signal.captured_at).toLocaleDateString() : ''}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
