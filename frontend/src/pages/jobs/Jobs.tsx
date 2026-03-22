import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

// ── Types ──────────────────────────────────────────────────────────────────

interface FreshJob {
  id: number;
  title: string;
  company: string;
  location?: string;
  salary_range?: string;
  source: string;
  url?: string;
  fit_score?: number;
  posted_date?: string;
  jd_snippet?: string;
}

interface SearchHistoryEntry {
  id: number;
  query: string;
  location?: string;
  source: string;
  result_count: number;
  created_at: string;
}

interface TitleVariation {
  original: string;
  variations: string[];
}

// ── Helpers ────────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="w-6 h-6 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
    </div>
  );
}

const FIT_COLORS: Record<string, string> = {
  high: 'text-green-600',
  medium: 'text-yellow-600',
  low: 'text-red-600',
};

function fitColor(score?: number): string {
  if (score == null) return 'text-gray-400';
  if (score >= 7) return FIT_COLORS.high;
  if (score >= 5) return FIT_COLORS.medium;
  return FIT_COLORS.low;
}

// ── Search Sources ─────────────────────────────────────────────────────────

const SOURCES = ['all', 'indeed', 'saved', 'fresh'] as const;
type Source = (typeof SOURCES)[number];

// ── Main Component ─────────────────────────────────────────────────────────

export default function Jobs() {
  const qc = useQueryClient();
  const [query, setQuery] = useState('');
  const [location, setLocation] = useState('');
  const [source, setSource] = useState<Source>('all');
  const [showVariations, setShowVariations] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  // Fresh jobs from DB
  const freshJobs = useQuery({
    queryKey: ['fresh-jobs', source],
    queryFn: () => {
      const params = source !== 'all' && source !== 'saved' ? `?source=${source}` : '';
      return api.get<FreshJob[]>(`/fresh-jobs${params}`);
    },
  });

  // Search results (triggered by mutation)
  const searchMutation = useMutation({
    mutationFn: (params: { query: string; location?: string; source?: string }) =>
      api.post<{ jobs: FreshJob[]; count: number; search_id?: number }>('/jobs/search', params),
  });

  // Title variations
  const variationsMutation = useMutation({
    mutationFn: (title: string) =>
      api.post<TitleVariation>('/jobs/title-variations', { title }),
  });

  // Search history
  const searchHistory = useQuery({
    queryKey: ['search-history'],
    queryFn: () => api.get<SearchHistoryEntry[]>('/jobs/search-history?limit=20'),
    enabled: showHistory,
  });

  // Save job
  const saveJob = useMutation({
    mutationFn: (job: FreshJob) =>
      api.post<any>('/saved-jobs', {
        url: job.url,
        title: job.title,
        company: job.company,
        location: job.location,
        salary_range: job.salary_range,
        source: job.source,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['saved-jobs'] });
    },
  });

  function handleSearch() {
    if (!query.trim()) return;
    searchMutation.mutate({
      query: query.trim(),
      location: location.trim() || undefined,
      source: source === 'all' ? undefined : source,
    });
  }

  function handleVariations() {
    if (!query.trim()) return;
    variationsMutation.mutate(query.trim());
    setShowVariations(true);
  }

  function useVariation(variation: string) {
    setQuery(variation);
    setShowVariations(false);
  }

  function replaySearch(entry: SearchHistoryEntry) {
    setQuery(entry.query);
    if (entry.location) setLocation(entry.location);
    setShowHistory(false);
    searchMutation.mutate({
      query: entry.query,
      location: entry.location || undefined,
      source: entry.source || undefined,
    });
  }

  // Display either search results or fresh jobs
  const displayJobs = searchMutation.data?.jobs ?? freshJobs.data ?? [];
  const isSearching = searchMutation.isPending;
  const hasSearched = searchMutation.data != null;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Job Search</h1>
        <button
          onClick={() => setShowHistory(!showHistory)}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          {showHistory ? 'Hide History' : 'Search History'}
        </button>
      </div>

      {/* Search Bar */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 mb-4">
        <div className="flex gap-3 mb-3">
          <input
            className="flex-1 border border-gray-300 rounded-lg px-4 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="Job title, keywords, or company..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
          <input
            className="w-48 border border-gray-300 rounded-lg px-4 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="Location..."
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
          <button
            onClick={handleSearch}
            disabled={isSearching || !query.trim()}
            className="bg-gray-900 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-gray-700 disabled:opacity-50"
          >
            {isSearching ? 'Searching...' : 'Search'}
          </button>
        </div>

        <div className="flex items-center justify-between">
          {/* Source filter */}
          <div className="flex gap-2">
            {SOURCES.map((s) => (
              <button
                key={s}
                onClick={() => setSource(s)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                  source === s
                    ? 'bg-gray-900 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {s === 'all' ? 'All Sources' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>

          {/* Title variations */}
          <button
            onClick={handleVariations}
            disabled={!query.trim() || variationsMutation.isPending}
            className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50"
          >
            {variationsMutation.isPending ? 'Generating...' : 'Suggest Title Variations'}
          </button>
        </div>
      </div>

      {/* Title Variations Panel */}
      {showVariations && variationsMutation.data && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-blue-900">
              Title Variations for "{variationsMutation.data.original}"
            </h3>
            <button onClick={() => setShowVariations(false)} className="text-xs text-blue-500">&times; Close</button>
          </div>
          <div className="flex flex-wrap gap-2">
            {variationsMutation.data.variations.map((v, i) => (
              <button
                key={i}
                onClick={() => useVariation(v)}
                className="px-3 py-1.5 bg-white border border-blue-200 rounded-full text-xs text-blue-700 hover:bg-blue-100"
              >
                {v}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Search History Panel */}
      {showHistory && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Recent Searches</h3>
          {searchHistory.isLoading && <Spinner />}
          {searchHistory.data && searchHistory.data.length === 0 && (
            <p className="text-xs text-gray-400">No search history yet.</p>
          )}
          <div className="space-y-2">
            {(searchHistory.data ?? []).map((entry) => (
              <button
                key={entry.id}
                onClick={() => replaySearch(entry)}
                className="w-full text-left bg-white border border-gray-200 rounded-lg p-3 hover:shadow-sm transition-shadow"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-800 font-medium">{entry.query}</span>
                  <span className="text-xs text-gray-400">
                    {new Date(entry.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="flex gap-3 mt-1 text-xs text-gray-500">
                  {entry.location && <span>{entry.location}</span>}
                  <span>{entry.source}</span>
                  <span>{entry.result_count} results</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Results header */}
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm text-gray-500">
          {hasSearched
            ? `${searchMutation.data?.count ?? 0} results found`
            : `${displayJobs.length} fresh jobs`}
        </p>
      </div>

      {/* Job Results */}
      <div className="space-y-3">
        {(freshJobs.isLoading || isSearching) && <Spinner />}
        {displayJobs.map((job) => (
          <div
            key={job.id}
            className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-sm transition-shadow"
          >
            <div className="flex justify-between items-start">
              <div className="flex-1 min-w-0">
                <h3 className="font-medium text-gray-900">{job.title}</h3>
                <p className="text-sm text-gray-500">
                  {job.company}
                  {job.location ? ` - ${job.location}` : ''}
                </p>
                <div className="flex gap-3 mt-2 text-xs text-gray-400 flex-wrap">
                  {job.source && (
                    <span className="bg-gray-100 px-2 py-0.5 rounded">{job.source}</span>
                  )}
                  {job.salary_range && (
                    <span className="text-green-600 font-medium">{job.salary_range}</span>
                  )}
                  {job.fit_score != null && (
                    <span className={`font-medium ${fitColor(job.fit_score)}`}>
                      Fit: {job.fit_score}/10
                    </span>
                  )}
                  {job.posted_date && (
                    <span>{new Date(job.posted_date).toLocaleDateString()}</span>
                  )}
                </div>
                {job.jd_snippet && (
                  <p className="text-xs text-gray-400 mt-2 line-clamp-2">{job.jd_snippet}</p>
                )}
              </div>
              <div className="flex gap-2 shrink-0 ml-4">
                {job.url && (
                  <a
                    href={job.url}
                    target="_blank"
                    rel="noreferrer"
                    className="px-3 py-1 bg-gray-100 text-gray-600 text-xs rounded hover:bg-gray-200"
                  >
                    View
                  </a>
                )}
                <button
                  onClick={() => saveJob.mutate(job)}
                  className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700"
                >
                  Save
                </button>
              </div>
            </div>
          </div>
        ))}

        {!freshJobs.isLoading && !isSearching && displayJobs.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-400">
              {hasSearched
                ? 'No results found. Try different keywords or broaden your search.'
                : 'No fresh jobs yet. Search for jobs above to get started.'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
