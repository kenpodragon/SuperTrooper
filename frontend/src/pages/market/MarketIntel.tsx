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
}

interface MarketSummary {
  total_signals?: number;
  critical?: number;
  high?: number;
  source_count?: number;
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
};

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-semibold text-gray-900 mt-1">{value}</p>
    </div>
  );
}

export default function MarketIntel() {
  const [sourceFilter, setSourceFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');

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

  const signalList = signals ?? [];
  const summaryData: MarketSummary = summary ?? {};

  const sources = Array.from(new Set(signalList.map((s: MarketSignal) => s.source).filter(Boolean)));
  const types = Array.from(new Set(signalList.map((s: MarketSignal) => s.signal_type).filter(Boolean)));

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Market Intelligence</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Total Signals" value={summaryData.total_signals ?? signalList.length} />
        <StatCard label="Critical" value={summaryData.critical ?? '...'} />
        <StatCard label="High Priority" value={summaryData.high ?? '...'} />
        <StatCard label="Sources" value={summaryData.source_count ?? sources.length} />
      </div>

      {/* Filter Bar */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 mb-4 flex flex-wrap gap-3 items-center">
        <span className="text-sm text-gray-600 font-medium">Filter:</span>
        <select
          className="border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none"
          value={sourceFilter}
          onChange={e => setSourceFilter(e.target.value)}
        >
          <option value="">All Sources</option>
          {['linkedin', 'news', 'glassdoor', 'twitter', 'manual', ...sources.filter(s => !['linkedin','news','glassdoor','twitter','manual'].includes(s))].map(s => (
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
    </div>
  );
}
