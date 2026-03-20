import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface SettingsData {
  ai_provider: string;
  ai_enabled: boolean;
  ai_model: string | null;
  default_template_id: number | null;
  duplicate_threshold: number;
}

interface TestResult {
  status: string;
  provider?: string;
  message?: string;
  health?: { available: boolean; version: string };
  providers?: { name: string; cli_command: string; available: boolean }[];
}

export default function Settings() {
  const queryClient = useQueryClient();
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);

  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<{ status: string; db: string }>('/health'),
  });

  const kb = useQuery({
    queryKey: ['kb-counts'],
    queryFn: () => api.get<{ counts: Record<string, number> }>('/kb/export'),
    select: (d) => d.counts,
  });

  const { data: settings, isLoading } = useQuery<SettingsData>({
    queryKey: ['settings'],
    queryFn: () => api.get<SettingsData>('/settings'),
  });

  const mutation = useMutation({
    mutationFn: (data: Partial<SettingsData>) => api.patch<SettingsData>('/settings', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings'] }),
  });

  const testAi = async (provider?: string) => {
    setTestResult(null);
    setTesting(true);
    try {
      const res = await api.post<TestResult>('/settings/test-ai', provider ? { provider } : {});
      setTestResult(res);
    } catch (e) {
      setTestResult({ status: 'error', message: String(e) });
    } finally {
      setTesting(false);
    }
  };

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

      {/* AI Configuration */}
      {!isLoading && settings && (
        <div className="mt-6 bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">AI Provider</h2>

          <div className="space-y-4 max-w-md">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Provider</label>
              <select
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                value={settings.ai_provider}
                onChange={(e) => mutation.mutate({ ai_provider: e.target.value })}
              >
                <option value="none">None (rule-based only)</option>
                <option value="claude">Claude</option>
                <option value="gemini">Gemini</option>
                <option value="openai">OpenAI</option>
              </select>
            </div>

            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-gray-700">Enable AI Parsing</label>
              <input
                type="checkbox"
                checked={settings.ai_enabled}
                onChange={(e) => mutation.mutate({ ai_enabled: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model Override (optional)</label>
              <input
                type="text"
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                value={settings.ai_model || ''}
                placeholder="e.g., claude-3-opus"
                onBlur={(e) => mutation.mutate({ ai_model: e.target.value || null })}
              />
            </div>

            <button
              onClick={() => testAi(settings.ai_provider !== 'none' ? settings.ai_provider : undefined)}
              disabled={testing}
              className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {testing ? 'Testing...' : 'Test Connection'}
            </button>

            {testResult && (
              <div className={`p-3 rounded text-sm ${testResult.status === 'ok' ? 'bg-green-50 border border-green-200' : testResult.status === 'disabled' ? 'bg-yellow-50 border border-yellow-200' : 'bg-red-50 border border-red-200'}`}>
                <p className="font-medium">
                  {testResult.status === 'ok'
                    ? `Connected: ${testResult.provider} (${testResult.health?.version})`
                    : testResult.status === 'disabled'
                    ? 'AI is disabled'
                    : `Error: ${testResult.message || JSON.stringify(testResult.health)}`}
                </p>
                {testResult.providers && (
                  <ul className="mt-2 space-y-1">
                    {testResult.providers.map((p) => (
                      <li key={p.name} className="flex items-center gap-2">
                        <span className={`inline-block w-2 h-2 rounded-full ${p.available ? 'bg-green-500' : 'bg-gray-300'}`} />
                        {p.name}: {p.available ? 'available' : 'not found'}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Resume Defaults */}
      {!isLoading && settings && (
        <div className="mt-6 bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Resume Defaults</h2>

          <div className="max-w-md">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Duplicate Sensitivity: {settings.duplicate_threshold}
            </label>
            <input
              type="range"
              min="0.5"
              max="1.0"
              step="0.05"
              value={settings.duplicate_threshold}
              onChange={(e) => mutation.mutate({ duplicate_threshold: parseFloat(e.target.value) })}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>Loose (0.5)</span>
              <span>Strict (1.0)</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
