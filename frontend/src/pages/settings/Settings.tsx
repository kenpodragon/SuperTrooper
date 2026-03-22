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

interface OnboardStatus {
  steps?: { name: string; completed: boolean; description?: string; skipped?: boolean; key?: string }[];
  completion_pct?: number;
  completed_count?: number;
  total_steps?: number;
  next_steps?: string[];
}

interface VoiceRule {
  id: number;
  category: string;
  rule_text: string;
  severity?: string;
}

interface Integration {
  name: string;
  key: string;
  description: string;
  connected: boolean;
  icon: string;
}

type SettingsTab = 'general' | 'integrations' | 'backup';

export default function Settings() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<SettingsTab>('general');
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [newRule, setNewRule] = useState({ category: 'custom', rule_text: '' });
  const [quickSetup, setQuickSetup] = useState({ name: '', email: '', target_roles: '' });
  const [importText, setImportText] = useState('');
  const [importStatus, setImportStatus] = useState<string | null>(null);

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

  const onboardStatus = useQuery({
    queryKey: ['onboard-status'],
    queryFn: () => api.get<OnboardStatus>('/onboard/checklist'),
  });

  const integrations = useQuery({
    queryKey: ['integrations'],
    queryFn: () => api.get<{ integrations: Integration[] }>('/settings/integrations'),
    select: (d) => d.integrations,
  });

  const voiceRules = useQuery({
    queryKey: ['voice-rules'],
    queryFn: () => api.get<VoiceRule[]>('/voice-rules'),
  });

  const mutation = useMutation({
    mutationFn: (data: Partial<SettingsData>) => api.patch<SettingsData>('/settings', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings'] }),
  });

  const addVoiceRule = useMutation({
    mutationFn: (data: typeof newRule) => api.post<VoiceRule>('/voice-rules', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['voice-rules'] });
      setNewRule({ category: 'custom', rule_text: '' });
    },
  });

  const deleteVoiceRule = useMutation({
    mutationFn: (id: number) => api.del(`/voice-rules/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['voice-rules'] }),
  });

  const saveQuickSetup = useMutation({
    mutationFn: (data: typeof quickSetup) => api.post<{ status: string }>('/onboard/quick-setup', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['onboard-status'] });
      setQuickSetup({ name: '', email: '', target_roles: '' });
    },
  });

  const skipStep = useMutation({
    mutationFn: (stepKey: string) => api.post('/onboard/skip-step', { step_key: stepKey }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['onboard-status'] }),
  });

  const handleExport = async () => {
    try {
      const data = await api.get('/settings/export');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `supertroopers-settings-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Export failed:', e);
    }
  };

  const handleImport = async () => {
    try {
      const parsed = JSON.parse(importText);
      await api.post('/settings/import', parsed);
      setImportStatus('Settings imported successfully');
      setImportText('');
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      queryClient.invalidateQueries({ queryKey: ['voice-rules'] });
    } catch (e) {
      setImportStatus(`Import failed: ${String(e)}`);
    }
  };

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

  const onboard = onboardStatus.data;
  const rules: VoiceRule[] = Array.isArray(voiceRules.data) ? voiceRules.data : [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Settings</h1>

      {/* Tab Navigation */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {([['general', 'General'], ['integrations', 'Integrations'], ['backup', 'Export / Import']] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition ${
              activeTab === key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* === INTEGRATIONS TAB === */}
      {activeTab === 'integrations' && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Available Integrations</h2>
          {integrations.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {(integrations.data ?? []).map((intg) => (
              <div key={intg.key} className="flex items-start gap-3 p-3 border border-gray-100 rounded-lg">
                <span className={`mt-1 inline-block w-3 h-3 rounded-full ${intg.connected ? 'bg-green-500' : 'bg-gray-300'}`} />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-gray-900">{intg.name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      intg.connected ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                    }`}>
                      {intg.connected ? 'Connected' : 'Not Connected'}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">{intg.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* === EXPORT / IMPORT TAB === */}
      {activeTab === 'backup' && (
        <div className="space-y-6">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Export Settings</h2>
            <p className="text-sm text-gray-500 mb-3">Download all settings, voice rules, and preferences as a JSON backup file.</p>
            <button onClick={handleExport} className="px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700">
              Download Backup
            </button>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Import Settings</h2>
            <p className="text-sm text-gray-500 mb-3">Paste the contents of a settings backup JSON to restore.</p>
            <textarea
              className="w-full border border-gray-200 rounded px-3 py-2 text-sm font-mono h-32 focus:outline-none focus:ring-1 focus:ring-blue-400"
              value={importText}
              onChange={e => setImportText(e.target.value)}
              placeholder='Paste exported JSON here...'
            />
            <button
              onClick={handleImport}
              disabled={!importText.trim()}
              className="mt-2 px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
            >
              Import
            </button>
            {importStatus && (
              <p className={`mt-2 text-sm ${importStatus.includes('failed') ? 'text-red-600' : 'text-green-600'}`}>
                {importStatus}
              </p>
            )}
          </div>
        </div>
      )}

      {/* === GENERAL TAB === */}
      {activeTab === 'general' && <>

      {/* Onboarding Checklist */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Onboarding Checklist</h2>
        {onboardStatus.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
        {onboardStatus.isError && <p className="text-sm text-gray-400">Onboarding status unavailable</p>}
        {onboard && (
          <>
            {onboard.completion_pct != null && (
              <div className="mb-3">
                <div className="flex justify-between text-xs text-gray-500 mb-1">
                  <span>Completion ({onboard.completed_count ?? 0}/{onboard.total_steps ?? 0})</span>
                  <span>{onboard.completion_pct}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all"
                    style={{ width: `${onboard.completion_pct}%` }}
                  />
                </div>
              </div>
            )}
            {(onboard.steps ?? []).map((step, idx) => (
              <div key={idx} className="flex items-center gap-2 py-1.5 border-b border-gray-100 last:border-0">
                <span className={`inline-block w-4 h-4 rounded-full text-xs text-center leading-4 font-medium ${
                  step.completed ? 'bg-green-100 text-green-700' :
                  step.skipped ? 'bg-yellow-100 text-yellow-600' :
                  'bg-gray-100 text-gray-400'
                }`}>
                  {step.completed ? '\u2713' : step.skipped ? 'S' : '\u2022'}
                </span>
                <span className={`text-sm flex-1 ${
                  step.completed ? 'text-gray-500 line-through' :
                  step.skipped ? 'text-gray-400 italic' :
                  'text-gray-900'
                }`}>{step.name}</span>
                {step.description && <span className="text-xs text-gray-400 hidden md:inline">{step.description}</span>}
                {!step.completed && !step.skipped && step.key && (
                  <button
                    onClick={() => skipStep.mutate(step.key!)}
                    className="text-xs text-gray-400 hover:text-yellow-600 ml-2"
                  >
                    Skip
                  </button>
                )}
              </div>
            ))}
          </>
        )}
      </div>

      {/* Quick Setup */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Quick Setup</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Name</label>
            <input
              className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              value={quickSetup.name}
              onChange={e => setQuickSetup(p => ({ ...p, name: e.target.value }))}
              placeholder="Full name"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Email</label>
            <input
              type="email"
              className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              value={quickSetup.email}
              onChange={e => setQuickSetup(p => ({ ...p, email: e.target.value }))}
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Target Roles</label>
            <input
              className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              value={quickSetup.target_roles}
              onChange={e => setQuickSetup(p => ({ ...p, target_roles: e.target.value }))}
              placeholder="e.g., VP Engineering, CTO"
            />
          </div>
        </div>
        <button
          onClick={() => saveQuickSetup.mutate(quickSetup)}
          disabled={saveQuickSetup.isPending || !quickSetup.name}
          className="mt-3 px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-50"
        >
          {saveQuickSetup.isPending ? 'Saving...' : 'Save Setup'}
        </button>
      </div>

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

      {/* Voice Rules Management */}
      <div className="mt-6 bg-white rounded-lg border border-gray-200 p-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Voice Rules</h2>
        {voiceRules.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
        {voiceRules.isError && <p className="text-sm text-gray-400">Voice rules unavailable</p>}

        {/* Add Rule */}
        <div className="flex gap-2 mb-4 max-w-2xl">
          <select
            className="border border-gray-200 rounded px-2 py-1.5 text-sm"
            value={newRule.category}
            onChange={e => setNewRule(p => ({ ...p, category: e.target.value }))}
          >
            <option value="custom">Custom</option>
            <option value="banned_word">Banned Word</option>
            <option value="banned_pattern">Banned Pattern</option>
            <option value="resume_rule">Resume Rule</option>
            <option value="style">Style</option>
          </select>
          <input
            className="flex-1 border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            value={newRule.rule_text}
            onChange={e => setNewRule(p => ({ ...p, rule_text: e.target.value }))}
            placeholder="Rule text..."
          />
          <button
            onClick={() => addVoiceRule.mutate(newRule)}
            disabled={addVoiceRule.isPending || !newRule.rule_text}
            className="px-3 py-1.5 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-50"
          >
            Add
          </button>
        </div>

        {/* Rules List */}
        <div className="max-h-64 overflow-y-auto">
          {rules.map((r) => (
            <div key={r.id} className="flex justify-between items-center py-1.5 border-b border-gray-100 last:border-0">
              <div className="flex gap-2 items-center">
                <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">{r.category}</span>
                <span className="text-sm text-gray-700">{r.rule_text}</span>
              </div>
              <button
                onClick={() => deleteVoiceRule.mutate(r.id)}
                className="text-xs text-red-400 hover:text-red-600"
              >
                Remove
              </button>
            </div>
          ))}
          {rules.length === 0 && !voiceRules.isLoading && (
            <p className="text-sm text-gray-400">No voice rules loaded</p>
          )}
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

      </>}
    </div>
  );
}
