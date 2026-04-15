import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, recipes, API_BASE } from '../../api/client';
import type { Recipe } from '../../api/client';
import TemplatesBrowser from './TemplatesBrowser';

interface RecipeDetail {
  id: number;
  name: string;
  description?: string;
  headline?: string;
  template_id: number;
  is_active?: boolean;
  sections?: { section_name: string; bullet_ids: number[] }[];
  created_at?: string;
}

interface GenerateResult {
  status: string;
  output_path?: string;
  message?: string;
}

interface KeywordMatch {
  keyword: string;
  found: boolean;
  jd_count?: number;
  resume_count?: number;
}

interface AiAnalysis {
  overall_assessment?: string;
  strengths?: string[];
  weaknesses?: string[];
  suggestions?: string[];
  ai_score?: number;
}

interface AtsScoreResult {
  ats_score?: number;
  score?: number;
  keyword_matches?: KeywordMatch[];
  missing_keywords?: string[];
  feedback?: string[];
  match_percentage?: number;
  keywords_found?: number;
  keywords_checked?: number;
  formatting_flags?: { ats_safe?: boolean; issues?: string[] };
  analysis_mode?: string;
  ai_analysis?: AiAnalysis;
  ai_error?: string;
}

const PAGE_SIZE = 25;

export default function Resumes() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [tab, setTab] = useState<'recipes' | 'templates' | 'ats'>('recipes');
  const [view, setView] = useState<'list' | 'detail'>('list');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [atsResult, setAtsResult] = useState<AtsScoreResult | null>(null);
  const [genResult, setGenResult] = useState<GenerateResult | null>(null);
  const [createForm, setCreateForm] = useState({ name: '', description: '', template_id: 1 });
  const [atsForm, setAtsForm] = useState({ resume_text: '', jd_text: '', use_ai: false });
  const [jdUrl, setJdUrl] = useState('');
  const [jdFetching, setJdFetching] = useState(false);

  // Search, sort, pagination state
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'date'>('date');
  const [page, setPage] = useState(1);

  const { data: recipeList, isLoading: loadingRecipes } = useQuery({
    queryKey: ['recipes'],
    queryFn: () => recipes.list(),
  });

  const recipeDetail = useQuery({
    queryKey: ['recipe-detail', selectedId],
    queryFn: () => api.get<RecipeDetail>(`/resume/recipes/${selectedId}`),
    enabled: selectedId != null && view === 'detail',
  });

  const recipeItems: Recipe[] = Array.isArray(recipeList) ? recipeList : (recipeList as unknown as { recipes?: Recipe[] })?.recipes ?? [];

  // Filtered + sorted + paginated recipes
  const filtered = useMemo(() => {
    let items = [...recipeItems];
    if (search.trim()) {
      const q = search.toLowerCase();
      items = items.filter(r =>
        r.name.toLowerCase().includes(q) ||
        (r.description || '').toLowerCase().includes(q)
      );
    }
    if (sortBy === 'name') {
      items.sort((a, b) => a.name.localeCompare(b.name));
    } else {
      items.sort((a, b) => (b.id - a.id)); // newest first by id
    }
    return items;
  }, [recipeItems, search, sortBy]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // Reset page when search changes
  const handleSearch = (v: string) => { setSearch(v); setPage(1); };

  const createRecipe = useMutation({
    mutationFn: (data: typeof createForm) => api.post<Recipe>('/resume/recipes', data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recipes'] });
      setShowCreate(false);
      setCreateForm({ name: '', description: '', template_id: 1 });
    },
    onError: (err: any) => alert(err?.response?.data?.error || 'Failed to create recipe'),
  });

  const cloneRecipe = useMutation({
    mutationFn: (id: number) => api.post<Recipe>(`/resume/recipes/${id}/clone`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['recipes'] }),
    onError: (err: any) => alert(err?.response?.data?.error || 'Failed to clone recipe'),
  });

  const deleteRecipe = useMutation({
    mutationFn: (id: number) => api.del(`/resume/recipes/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recipes'] });
      if (selectedId === deleteRecipe.variables) {
        setView('list');
        setSelectedId(null);
      }
    },
    onError: (err: any) => alert(err?.response?.data?.error || 'Failed to delete recipe'),
  });

  const generateResume = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`${API_BASE}/resume/recipes/${id}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(err.error || 'Generation failed');
      }
      const contentType = res.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        return res.json() as Promise<GenerateResult>;
      }
      const blob = await res.blob();
      const disposition = res.headers.get('content-disposition') || '';
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] || `resume_${id}.docx`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      return { status: 'ok', output_path: filename, message: 'Resume downloaded' } as GenerateResult;
    },
    onSuccess: (data) => setGenResult(data),
    onError: (err: any) => alert(err?.message || 'Failed to generate resume'),
  });

  const runAtsScore = useMutation({
    mutationFn: (data: typeof atsForm) => api.post<AtsScoreResult>('/resume/ats-score', data),
    onSuccess: (data) => setAtsResult(data),
    onError: (err: any) => alert(err?.response?.data?.error || 'ATS scoring failed'),
  });

  const fetchJdFromUrl = async (url: string) => {
    setJdFetching(true);
    try {
      const result = await api.post<{ text: string; error?: string }>('/jd/fetch-url', { url });
      if (result.text) {
        setAtsForm(p => ({ ...p, jd_text: result.text }));
      }
    } catch (err: any) {
      alert(err?.response?.data?.error || 'Failed to fetch JD from URL');
    } finally {
      setJdFetching(false);
    }
  };

  // Detail view
  if (view === 'detail' && selectedId != null) {
    const detail = recipeDetail.data;
    return (
      <div>
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => { setView('list'); setGenResult(null); }} className="text-sm text-blue-600 hover:underline">&larr; Back</button>
          <h1 className="text-2xl font-bold text-gray-900">{detail?.name || 'Recipe Detail'}</h1>
        </div>

        {recipeDetail.isLoading && <p className="text-sm text-gray-400">Loading...</p>}

        {detail && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <p className="text-sm text-gray-500">{detail.description || 'No description'}</p>
                  {detail.headline && <p className="text-sm text-gray-700 mt-1 italic">{detail.headline}</p>}
                </div>
                <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">Template #{detail.template_id}</span>
              </div>

              <h3 className="text-sm font-semibold text-gray-900 mt-4 mb-2">Sections</h3>
              {(detail.sections ?? []).length === 0 && <p className="text-sm text-gray-400">No sections configured</p>}
              {(detail.sections ?? []).map((s, idx) => (
                <div key={idx} className="py-2 border-b border-gray-100 last:border-0">
                  <p className="text-sm font-medium text-gray-700">{s.section_name}</p>
                  <p className="text-xs text-gray-400">{s.bullet_ids?.length || 0} bullets selected</p>
                </div>
              ))}
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => generateResume.mutate(selectedId)}
                disabled={generateResume.isPending}
                className="px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-50"
              >
                {generateResume.isPending ? 'Generating...' : 'Generate Resume'}
              </button>
              <button
                onClick={() => cloneRecipe.mutate(selectedId)}
                disabled={cloneRecipe.isPending}
                className="px-4 py-2 bg-blue-50 text-blue-600 text-sm rounded hover:bg-blue-100 disabled:opacity-50"
              >
                Clone
              </button>
              <button
                onClick={() => { if (confirm('Delete this recipe?')) deleteRecipe.mutate(selectedId); }}
                className="px-4 py-2 bg-red-50 text-red-600 text-sm rounded hover:bg-red-100"
              >
                Delete
              </button>
            </div>

            {genResult && (
              <div className={`p-4 rounded-lg border ${genResult.status === 'ok' || genResult.output_path ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                <p className="text-sm font-medium">{genResult.status === 'ok' || genResult.output_path ? 'Resume Generated' : 'Generation Failed'}</p>
                {genResult.output_path && <p className="text-sm text-gray-700 mt-1">File: {genResult.output_path}</p>}
                {genResult.message && <p className="text-sm text-gray-600 mt-1">{genResult.message}</p>}
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // List view
  return (
    <div>
      {/* Tab Bar — 3 tabs */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border, #e5e7eb)', marginBottom: 24 }}>
        {(['recipes', 'templates', 'ats'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '10px 20px',
              fontSize: 14,
              fontWeight: tab === t ? 600 : 400,
              color: tab === t ? 'var(--accent, #3b82f6)' : 'var(--text-secondary, #6b7280)',
              background: 'none',
              border: 'none',
              borderBottom: tab === t ? '2px solid var(--accent, #3b82f6)' : '2px solid transparent',
              cursor: 'pointer',
              marginBottom: -1,
            }}
          >
            {t === 'ats' ? 'ATS Checker' : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Templates tab */}
      {tab === 'templates' && <TemplatesBrowser />}

      {/* ATS Checker tab */}
      {tab === 'ats' && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">ATS Score Checker</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Resume Text</label>
              <div className="flex gap-2 mb-2">
                <select
                  className="flex-1 border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                  defaultValue=""
                  onChange={async (e) => {
                    const id = Number(e.target.value);
                    if (!id) return;
                    try {
                      const detail = await api.get<{ resolved_preview?: Record<string, unknown> }>(`/resume/recipes/${id}?resolve=true`);
                      if (detail.resolved_preview) {
                        const rp = detail.resolved_preview;
                        const lines: string[] = [];
                        for (const [key, val] of Object.entries(rp)) {
                          if (Array.isArray(val)) {
                            lines.push(`${key}:`);
                            val.forEach(v => lines.push(`  - ${typeof v === 'string' ? v : JSON.stringify(v)}`));
                          } else if (typeof val === 'string') {
                            lines.push(`${key}: ${val}`);
                          }
                        }
                        setAtsForm(p => ({ ...p, resume_text: lines.join('\n') }));
                      }
                    } catch {
                      alert('Failed to load recipe content');
                    }
                  }}
                >
                  <option value="">Select a recipe to load...</option>
                  {recipeItems.map((r: Recipe) => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
                </select>
              </div>
              <textarea
                rows={5}
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={atsForm.resume_text}
                onChange={e => setAtsForm(p => ({ ...p, resume_text: e.target.value }))}
                placeholder="Select a recipe above or paste resume text..."
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Job Description</label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  className="flex-1 border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                  value={jdUrl}
                  onChange={e => setJdUrl(e.target.value)}
                  placeholder="Paste JD URL to auto-fetch..."
                />
                <button
                  onClick={() => fetchJdFromUrl(jdUrl)}
                  disabled={jdFetching || !jdUrl.trim()}
                  className="px-3 py-1.5 bg-blue-50 text-blue-600 text-xs rounded hover:bg-blue-100 disabled:opacity-50 whitespace-nowrap"
                >
                  {jdFetching ? 'Fetching...' : 'Fetch JD'}
                </button>
              </div>
              <textarea
                rows={5}
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={atsForm.jd_text}
                onChange={e => setAtsForm(p => ({ ...p, jd_text: e.target.value }))}
                placeholder="Paste job description or use URL above..."
              />
            </div>
          </div>
          <div className="mt-3 flex items-center gap-4">
            <button
              onClick={() => runAtsScore.mutate(atsForm)}
              disabled={runAtsScore.isPending || !atsForm.resume_text || !atsForm.jd_text}
              className="px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-50"
            >
              {runAtsScore.isPending ? 'Scoring...' : 'Check ATS Score'}
            </button>
            <label className="flex items-center gap-2 cursor-pointer">
              <button
                type="button"
                onClick={() => setAtsForm(p => ({ ...p, use_ai: !p.use_ai }))}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                  atsForm.use_ai ? 'bg-blue-500' : 'bg-gray-300'
                }`}
              >
                <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                  atsForm.use_ai ? 'translate-x-4' : 'translate-x-0.5'
                }`} />
              </button>
              <span className="text-xs text-gray-600">Use AI</span>
            </label>
          </div>

          {atsResult && (
            <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
              {(atsResult.ats_score ?? atsResult.score) != null && (
                <div className="flex items-center gap-4 mb-3">
                  <p className="text-lg font-semibold text-gray-900">
                    ATS Score: {atsResult.ats_score ?? atsResult.score}/100
                  </p>
                  {atsResult.match_percentage != null && (
                    <span className="text-sm text-gray-500">
                      ({atsResult.keywords_found}/{atsResult.keywords_checked} keywords, {atsResult.match_percentage}% match)
                    </span>
                  )}
                </div>
              )}
              {atsResult.keyword_matches && atsResult.keyword_matches.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs font-medium text-green-600 mb-1">Found Keywords</p>
                  <div className="flex flex-wrap gap-1">
                    {atsResult.keyword_matches.filter(k => k.found).map(k => (
                      <span key={k.keyword} className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">
                        {k.keyword}{k.resume_count && k.resume_count > 1 ? ` (${k.resume_count}x)` : ''}
                      </span>
                    ))}
                  </div>
                  {atsResult.keyword_matches.some(k => !k.found) && (
                    <>
                      <p className="text-xs font-medium text-red-600 mb-1 mt-2">Missing Keywords</p>
                      <div className="flex flex-wrap gap-1">
                        {atsResult.keyword_matches.filter(k => !k.found).map(k => (
                          <span key={k.keyword} className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded">
                            {k.keyword}
                          </span>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )}
              {atsResult.formatting_flags && (
                <div className="mt-2">
                  <p className="text-xs font-medium text-gray-500 mb-1">
                    Formatting: {atsResult.formatting_flags.ats_safe ? '✓ ATS Safe' : '⚠ Issues Found'}
                  </p>
                  {atsResult.formatting_flags.issues && atsResult.formatting_flags.issues.length > 0 && (
                    <ul className="list-disc list-inside text-xs text-gray-600 space-y-0.5">
                      {atsResult.formatting_flags.issues.map((f, i) => <li key={i}>{f}</li>)}
                    </ul>
                  )}
                </div>
              )}
              {atsResult.missing_keywords && atsResult.missing_keywords.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs font-medium text-gray-500 mb-1">Missing Keywords</p>
                  <div className="flex flex-wrap gap-1">
                    {atsResult.missing_keywords.map(k => (
                      <span key={k} className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded">{k}</span>
                    ))}
                  </div>
                </div>
              )}
              {atsResult.feedback && atsResult.feedback.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs font-medium text-gray-500 mb-1">Feedback</p>
                  <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                    {atsResult.feedback.map((f, i) => <li key={i}>{f}</li>)}
                  </ul>
                </div>
              )}

              {atsResult.ai_analysis && (
                <div className="mt-3 border-t border-gray-200 pt-3">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-bold text-blue-600 uppercase">AI Analysis</span>
                    {atsResult.ai_analysis.ai_score != null && (
                      <span className="text-xs text-gray-500">AI Score: {atsResult.ai_analysis.ai_score}/100</span>
                    )}
                  </div>
                  {atsResult.ai_analysis.overall_assessment && (
                    <p className="text-sm text-gray-700 mb-3">{atsResult.ai_analysis.overall_assessment}</p>
                  )}
                  {atsResult.ai_analysis.strengths && atsResult.ai_analysis.strengths.length > 0 && (
                    <div className="mb-2">
                      <p className="text-xs font-medium text-green-600 mb-1">Strengths</p>
                      <ul className="list-disc list-inside text-xs text-gray-600 space-y-0.5">
                        {atsResult.ai_analysis.strengths.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                    </div>
                  )}
                  {atsResult.ai_analysis.weaknesses && atsResult.ai_analysis.weaknesses.length > 0 && (
                    <div className="mb-2">
                      <p className="text-xs font-medium text-red-600 mb-1">Gaps</p>
                      <ul className="list-disc list-inside text-xs text-gray-600 space-y-0.5">
                        {atsResult.ai_analysis.weaknesses.map((w, i) => <li key={i}>{w}</li>)}
                      </ul>
                    </div>
                  )}
                  {atsResult.ai_analysis.suggestions && atsResult.ai_analysis.suggestions.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-blue-600 mb-1">Suggestions</p>
                      <ul className="list-disc list-inside text-xs text-gray-600 space-y-0.5">
                        {atsResult.ai_analysis.suggestions.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              {atsResult.ai_error && (
                <p className="mt-2 text-xs text-amber-600">AI unavailable, showing keyword analysis only: {atsResult.ai_error}</p>
              )}
              {atsResult.analysis_mode && (
                <p className="mt-2 text-xs text-gray-400 text-right">
                  Analysis: {atsResult.analysis_mode === 'ai' ? 'AI + Keywords' : 'Keywords only'}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Recipes tab */}
      {tab === 'recipes' && <>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900">Resume Builder</h1>
        <div className="flex gap-2">
          <button
            onClick={() => navigate('/resume-builder')}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
          >
            Build New
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700"
          >
            + New Recipe
          </button>
        </div>
      </div>

      {/* Search + Sort */}
      <div className="flex items-center gap-3 mb-4">
        <input
          type="text"
          className="flex-1 max-w-sm border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
          value={search}
          onChange={e => handleSearch(e.target.value)}
          placeholder="Search recipes..."
        />
        <select
          className="border border-gray-200 rounded px-2 py-1.5 text-sm"
          value={sortBy}
          onChange={e => setSortBy(e.target.value as 'name' | 'date')}
        >
          <option value="date">Newest first</option>
          <option value="name">Name A-Z</option>
        </select>
        <span className="text-xs text-gray-400">{filtered.length} recipes</span>
      </div>

      {/* Create Form */}
      {showCreate && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 mb-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Create Recipe</h2>
          <div className="grid grid-cols-2 gap-4 max-w-lg">
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-1">Name</label>
              <input
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={createForm.name}
                onChange={e => setCreateForm(p => ({ ...p, name: e.target.value }))}
                placeholder="e.g., Tech Lead - FAANG"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-1">Description</label>
              <input
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={createForm.description}
                onChange={e => setCreateForm(p => ({ ...p, description: e.target.value }))}
                placeholder="Target role and focus areas"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Template ID</label>
              <input
                type="number"
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={createForm.template_id}
                onChange={e => setCreateForm(p => ({ ...p, template_id: parseInt(e.target.value) || 1 }))}
              />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button
              onClick={() => createRecipe.mutate(createForm)}
              disabled={createRecipe.isPending || !createForm.name}
              className="px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-50"
            >
              {createRecipe.isPending ? 'Creating...' : 'Create'}
            </button>
            <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Recipe List */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        {loadingRecipes && <p className="text-sm text-gray-400">Loading...</p>}
        {paginated.map((r: Recipe) => (
          <div key={r.id} className="flex justify-between py-2 border-b border-gray-100 last:border-0">
            <div
              className="cursor-pointer hover:text-blue-600"
              onClick={() => navigate(`/resume-builder/${r.id}`)}
            >
              <p className="text-sm font-medium text-gray-900">{r.name}</p>
              <p className="text-xs text-gray-400">{r.description || 'No description'}</p>
            </div>
            <div className="flex gap-2 items-center">
              <button
                onClick={() => generateResume.mutate(r.id)}
                disabled={generateResume.isPending}
                className="text-xs bg-blue-50 text-blue-600 px-3 py-1 rounded hover:bg-blue-100"
              >
                Generate
              </button>
              <button
                onClick={() => cloneRecipe.mutate(r.id)}
                className="text-xs bg-gray-50 text-gray-600 px-2 py-1 rounded hover:bg-gray-100"
              >
                Clone
              </button>
              <button
                onClick={() => { if (confirm('Delete?')) deleteRecipe.mutate(r.id); }}
                className="text-xs bg-red-50 text-red-500 px-2 py-1 rounded hover:bg-red-100"
              >
                Del
              </button>
            </div>
          </div>
        ))}
        {!loadingRecipes && filtered.length === 0 && <p className="text-sm text-gray-400">{search ? 'No recipes match your search' : 'No recipes found'}</p>}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-100">
            <span className="text-xs text-gray-400">
              Showing {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length}
            </span>
            <div className="flex gap-1">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-2 py-1 text-xs border rounded hover:bg-gray-50 disabled:opacity-30"
              >
                Prev
              </button>
              {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                const p = i + 1;
                return (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={`px-2 py-1 text-xs border rounded ${page === p ? 'bg-blue-50 text-blue-600 border-blue-200' : 'hover:bg-gray-50'}`}
                  >
                    {p}
                  </button>
                );
              })}
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-2 py-1 text-xs border rounded hover:bg-gray-50 disabled:opacity-30"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Generation Result Toast */}
      {genResult && (
        <div className={`fixed bottom-4 right-4 p-4 rounded-lg shadow-lg border ${genResult.output_path ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
          <div className="flex items-center gap-3">
            <div>
              <p className="text-sm font-medium">{genResult.output_path ? 'Resume Generated' : 'Generation Failed'}</p>
              {genResult.output_path && <p className="text-xs text-gray-600">{genResult.output_path}</p>}
              {genResult.message && <p className="text-xs text-gray-600">{genResult.message}</p>}
            </div>
            <button onClick={() => setGenResult(null)} className="text-xs text-gray-400 hover:text-gray-600">Dismiss</button>
          </div>
        </div>
      )}
      </>}
    </div>
  );
}
