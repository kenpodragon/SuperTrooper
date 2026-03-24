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
  providers?: { name: string; cli_command?: string; available: boolean; model?: string; version?: string }[];
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
  label: string;
  description: string;
  status: string;
  enabled: boolean;
  setup_required: boolean;
  config: Record<string, unknown>;
  services?: string[];
  providers?: { name: string; available: boolean; model?: string; version?: string }[];
}

type SettingsTab = 'general' | 'integrations' | 'backup';

interface IntegrationTestResult {
  status: string;
  message?: string;
  [key: string]: unknown;
}

const STATUS_COLORS: Record<string, string> = {
  connected: 'bg-green-500',
  available: 'bg-green-500',
  setup_required: 'bg-yellow-500',
  not_configured: 'bg-yellow-500',
  disconnected: 'bg-red-500',
  unavailable: 'bg-red-500',
  error: 'bg-red-500',
  disabled: 'bg-gray-300',
  not_installed: 'bg-gray-300',
};

const STATUS_LABELS: Record<string, string> = {
  connected: 'Connected',
  available: 'Available',
  setup_required: 'Setup Required',
  not_configured: 'Not Configured',
  disconnected: 'Disconnected',
  unavailable: 'Unavailable',
  error: 'Error',
  disabled: 'Disabled',
  not_installed: 'Not Installed',
};

function IntegrationCard({ intg, onTest, onConfigure }: {
  intg: Integration;
  onTest: (name: string) => void;
  onConfigure: (name: string) => void;
}) {
  return (
    <div className="p-4 border border-gray-200 rounded-lg">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`inline-block w-3 h-3 rounded-full ${STATUS_COLORS[intg.status] || 'bg-gray-300'}`} />
          <h3 className="font-medium text-gray-900">{intg.label}</h3>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full ${
          intg.status === 'connected' || intg.status === 'available'
            ? 'bg-green-100 text-green-700'
            : intg.status === 'setup_required' || intg.status === 'not_configured'
            ? 'bg-yellow-100 text-yellow-700'
            : 'bg-gray-100 text-gray-500'
        }`}>
          {STATUS_LABELS[intg.status] || intg.status}
        </span>
      </div>
      <p className="text-sm text-gray-500 mb-3">{intg.description}</p>
      {intg.services && (
        <div className="flex flex-wrap gap-1 mb-3">
          {intg.services.map(s => (
            <span key={s} className="text-xs px-2 py-0.5 bg-blue-50 text-blue-600 rounded">{s}</span>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <button
          onClick={() => onTest(intg.name)}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50"
        >
          Test Connection
        </button>
        <button
          onClick={() => onConfigure(intg.name)}
          className="px-3 py-1.5 text-sm bg-gray-900 text-white rounded hover:bg-gray-700"
        >
          Configure
        </button>
      </div>
    </div>
  );
}

export default function Settings() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<SettingsTab>('general');
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [newRule, setNewRule] = useState({ category: 'custom', rule_text: '' });
  const [quickSetup, setQuickSetup] = useState({ name: '', email: '', target_roles: '' });
  const [importText, setImportText] = useState('');
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const [wizardOpen, setWizardOpen] = useState<string | null>(null);
  const [intgTestResult, setIntgTestResult] = useState<Record<string, IntegrationTestResult>>({});
  const [intgTesting, setIntgTesting] = useState<string | null>(null);
  const [antiaiUrl, setAntiaiUrl] = useState('');
  const [googleStep, setGoogleStep] = useState<'quick' | 'auth' | 'done' | 'guide-0' | 'guide-1' | 'guide-2'>('quick');
  const [googleCredsJson, setGoogleCredsJson] = useState('');
  const [googleAuthUrl, setGoogleAuthUrl] = useState('');
  const [googleAuthCode, setGoogleAuthCode] = useState('');
  const [googleStatus, setGoogleStatus] = useState<string | null>(null);

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
    queryFn: () => api.get<{ integrations: Integration[] }>('/integrations'),
    select: (d) => d.integrations,
  });

  const voiceRules = useQuery({
    queryKey: ['voice-rules'],
    queryFn: () => api.get<{ rules: VoiceRule[]; count: number } | VoiceRule[]>('/voice-rules'),
    select: (d) => (Array.isArray(d) ? d : d.rules ?? []),
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

  // Auto-detect AI providers on load
  const aiProviders = useQuery({
    queryKey: ['ai-providers'],
    queryFn: () => api.post<TestResult>('/settings/test-ai', {}),
    staleTime: 60_000,
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
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Integrations</h2>
          {integrations.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {(integrations.data ?? []).map((intg) => (
              <IntegrationCard
                key={intg.name}
                intg={intg}
                onTest={async (name) => {
                  setIntgTesting(name);
                  try {
                    const res = await api.post<IntegrationTestResult>(`/integrations/${name}/test`, {});
                    setIntgTestResult(prev => ({ ...prev, [name]: res }));
                  } catch (e) {
                    setIntgTestResult(prev => ({ ...prev, [name]: { status: 'error', message: String(e) } }));
                  } finally {
                    setIntgTesting(null);
                  }
                }}
                onConfigure={(name) => {
                  if (name === 'antiai') {
                    const cfg = intg.config as { api_url?: string };
                    setAntiaiUrl(cfg.api_url || 'http://localhost:8066');
                  }
                  setWizardOpen(name);
                }}
              />
            ))}
          </div>

          {/* Test Results */}
          {Object.entries(intgTestResult).map(([name, result]) => (
            <div key={name} className={`p-3 rounded text-sm ${
              result.status === 'connected' || result.status === 'available'
                ? 'bg-green-50 border border-green-200'
                : result.status === 'setup_required' || result.status === 'not_configured'
                ? 'bg-yellow-50 border border-yellow-200'
                : 'bg-red-50 border border-red-200'
            }`}>
              <p className="font-medium capitalize">{name}: {result.status}</p>
              {result.message && <p className="text-gray-600 mt-1">{result.message}</p>}
            </div>
          ))}
          {intgTesting && <p className="text-sm text-gray-400 animate-pulse">Testing {intgTesting}...</p>}

          {/* === WIZARD MODALS === */}

          {/* Google Workspace — Quick connect + optional walkthrough */}
          {wizardOpen === 'google' && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setWizardOpen(null)}>
              <div className="bg-white rounded-lg p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">Google Workspace</h3>
                  <button onClick={() => setWizardOpen(null)} className="text-gray-400 hover:text-gray-600 text-lg">&times;</button>
                </div>

                <div className="space-y-4 text-sm text-gray-600">

                  {/* === QUICK FLOW: Upload JSON + Authorize === */}
                  {(googleStep === 'quick' || googleStep === 'auth' || googleStep === 'done') && (<>

                    {googleStep === 'quick' && (<>
                      {/* Re-authorize shortcut when already connected */}
                      {(integrations.data ?? []).find((i: Integration) => i.name === 'google' && (i.status === 'connected' || i.status === 'available')) && (
                        <div className="p-3 bg-blue-50 rounded border border-blue-200 space-y-2 mb-2">
                          <p className="text-sm font-medium text-blue-800">Google is connected. Need to update permissions?</p>
                          <p className="text-xs text-blue-600">If you enabled new APIs (like People API for contacts), re-authorize to grant the new scopes.</p>
                          <button
                            onClick={async () => {
                              setGoogleStatus(null);
                              try {
                                const authRes = await api.post<{auth_url: string}>('/integrations/google/auth-url', {});
                                setGoogleAuthUrl(authRes.auth_url);
                                setGoogleStep('auth');
                              } catch (e) {
                                setGoogleStatus(`Error: ${String(e)}`);
                              }
                            }}
                            className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
                          >
                            Re-authorize Google
                          </button>
                        </div>
                      )}

                      {/* Upload / paste credentials */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">1. Upload your Google OAuth credentials.json</label>
                        <div
                          className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-blue-400 transition cursor-pointer"
                          onClick={() => document.getElementById('google-creds-upload')?.click()}
                          onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add('border-blue-400', 'bg-blue-50'); }}
                          onDragLeave={e => { e.currentTarget.classList.remove('border-blue-400', 'bg-blue-50'); }}
                          onDrop={e => {
                            e.preventDefault();
                            e.currentTarget.classList.remove('border-blue-400', 'bg-blue-50');
                            const file = e.dataTransfer.files[0];
                            if (file) {
                              const reader = new FileReader();
                              reader.onload = ev => { if (ev.target?.result) setGoogleCredsJson(ev.target.result as string); };
                              reader.readAsText(file);
                            }
                          }}
                        >
                          <input
                            id="google-creds-upload"
                            type="file"
                            accept=".json,application/json"
                            className="hidden"
                            onChange={e => {
                              const file = e.target.files?.[0];
                              if (file) {
                                const reader = new FileReader();
                                reader.onload = ev => { if (ev.target?.result) setGoogleCredsJson(ev.target.result as string); };
                                reader.readAsText(file);
                              }
                            }}
                          />
                          <p className="text-sm text-gray-500">
                            {googleCredsJson ? '\u2713 Credentials loaded \u2014 click to replace' : 'Drop credentials.json here or click to browse'}
                          </p>
                        </div>
                        <details className="text-xs mt-2">
                          <summary className="text-gray-400 cursor-pointer hover:text-gray-600">Or paste JSON manually</summary>
                          <textarea
                            className="w-full border border-gray-300 rounded px-3 py-2 text-xs font-mono h-24 mt-2 focus:outline-none focus:ring-1 focus:ring-blue-400"
                            value={googleCredsJson}
                            onChange={e => setGoogleCredsJson(e.target.value)}
                            placeholder='{"installed":{"client_id":"...","client_secret":"...", ...}}'
                          />
                        </details>
                        {googleCredsJson && <p className="text-xs text-green-600 mt-1">{googleCredsJson.length} chars loaded</p>}
                      </div>

                      {googleStatus && <p className={`text-xs ${googleStatus.includes('Error') ? 'text-red-600' : 'text-green-600'}`}>{googleStatus}</p>}

                      <div className="p-3 bg-yellow-50 rounded border border-yellow-200">
                        <button
                          onClick={() => setGoogleStep('guide-0')}
                          className="text-sm text-yellow-800 font-medium hover:underline w-full text-left"
                        >
                          I don't have credentials yet &mdash; walk me through the setup &rarr;
                        </button>
                      </div>

                      <div className="flex items-center justify-between pt-1">
                        <div />
                        <button
                          onClick={async () => {
                            setGoogleStatus(null);
                            try {
                              const parsed = JSON.parse(googleCredsJson);
                              await api.post('/integrations/google/credentials', parsed);
                              const authRes = await api.post<{auth_url: string}>('/integrations/google/auth-url', {});
                              setGoogleAuthUrl(authRes.auth_url);
                              setGoogleStep('auth');
                              setGoogleStatus(null);
                            } catch (e) {
                              setGoogleStatus(`Error: ${String(e)}`);
                            }
                          }}
                          disabled={!googleCredsJson.trim()}
                          className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
                        >
                          Next: Authorize &rarr;
                        </button>
                      </div>
                    </>)}

                    {googleStep === 'auth' && (<>
                      <label className="block text-sm font-medium text-gray-700">2. Authorize with Google</label>
                      <div className="p-3 bg-gray-50 rounded border border-gray-200 space-y-2">
                        <p className="text-xs">Click below to open Google's authorization page. Sign in, grant access, then copy the code Google gives you.</p>
                        <a href={googleAuthUrl} target="_blank" rel="noreferrer" className="inline-block px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
                          Open Google Authorization
                        </a>
                        <p className="text-[10px] text-gray-400">You may see "Google hasn't verified this app" \u2014 click <strong>Continue</strong>. This is normal for personal projects.</p>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Paste the authorization code:</label>
                        <input
                          type="text"
                          className="w-full border border-gray-300 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-blue-400"
                          value={googleAuthCode}
                          onChange={e => setGoogleAuthCode(e.target.value)}
                          placeholder="4/0Abc..."
                        />
                      </div>
                      {googleStatus && <p className={`text-xs ${googleStatus.includes('Error') ? 'text-red-600' : 'text-green-600'}`}>{googleStatus}</p>}
                      <div className="flex gap-2">
                        <button onClick={() => setGoogleStep('quick')} className="px-4 py-2 border border-gray-300 rounded text-sm hover:bg-gray-50">
                          &larr; Back
                        </button>
                        <button
                          onClick={async () => {
                            setGoogleStatus(null);
                            try {
                              await api.post('/integrations/google/exchange', { code: googleAuthCode });
                              queryClient.invalidateQueries({ queryKey: ['integrations'] });
                              setGoogleStep('done');
                            } catch (e) {
                              setGoogleStatus(`Error: ${String(e)}`);
                            }
                          }}
                          disabled={!googleAuthCode.trim()}
                          className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
                        >
                          Connect
                        </button>
                      </div>
                    </>)}

                    {googleStep === 'done' && (<>
                      <div className="p-4 bg-green-50 rounded border border-green-200 text-center">
                        <p className="text-lg font-semibold text-green-800 mb-1">Connected!</p>
                        <p className="text-green-700">Gmail, Calendar, and Drive are now available.</p>
                      </div>
                      <div className="flex gap-2 justify-center">
                        <button
                          onClick={async () => {
                            setIntgTesting('google');
                            try {
                              const res = await api.post<IntegrationTestResult>('/integrations/google/test', {});
                              setIntgTestResult(prev => ({ ...prev, google: res }));
                            } catch (e) {
                              setIntgTestResult(prev => ({ ...prev, google: { status: 'error', message: String(e) } }));
                            } finally { setIntgTesting(null); }
                          }}
                          className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
                        >
                          Test Connection
                        </button>
                        <button onClick={() => {
                          setWizardOpen(null); setGoogleStep('quick'); setGoogleCredsJson(''); setGoogleAuthCode('');
                        }} className="px-4 py-2 bg-gray-900 text-white rounded text-sm hover:bg-gray-700">
                          Done
                        </button>
                      </div>
                    </>)}

                  </>)}

                  {/* === GUIDED WALKTHROUGH === */}

                  {/* Guide Step 0: Create project */}
                  {googleStep === 'guide-0' && (<>
                    <div className="p-3 bg-blue-50 rounded border border-blue-200">
                      <p className="font-medium text-blue-800 mb-1">Works with any Google account</p>
                      <p>Personal Gmail works fine... no paid Google Workspace needed.</p>
                    </div>
                    <p className="font-medium text-gray-800">Create a Google Cloud project:</p>
                    <ol className="space-y-3 text-xs">
                      <li className="flex gap-2">
                        <span className="font-bold text-blue-600 flex-shrink-0">1.</span>
                        <div>
                          Go to <a href="https://console.cloud.google.com/" target="_blank" rel="noreferrer" className="text-blue-600 underline font-medium">console.cloud.google.com</a>
                          <p className="text-gray-400 mt-0.5">Sign in with the Google account you want to connect. Accept terms if prompted... no billing needed.</p>
                        </div>
                      </li>
                      <li className="flex gap-2">
                        <span className="font-bold text-blue-600 flex-shrink-0">2.</span>
                        <div>
                          Click the project dropdown at top left &rarr; <strong>New Project</strong> &rarr; name it anything &rarr; <strong>Create</strong>
                        </div>
                      </li>
                      <li className="flex gap-2">
                        <span className="font-bold text-blue-600 flex-shrink-0">3.</span>
                        <div>Make sure your new project is selected in the top dropdown.</div>
                      </li>
                    </ol>
                    <div className="flex gap-2 pt-2">
                      <button onClick={() => setGoogleStep('quick')} className="px-4 py-2 border border-gray-300 rounded text-sm hover:bg-gray-50">
                        &larr; I already have credentials
                      </button>
                      <button onClick={() => setGoogleStep('guide-1')} className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
                        Next &rarr;
                      </button>
                    </div>
                  </>)}

                  {/* Guide Step 1: Consent screen + APIs + Data Access */}
                  {googleStep === 'guide-1' && (<>
                    <p className="font-medium text-gray-800">Set up consent screen, APIs, and permissions:</p>
                    <ol className="space-y-3 text-xs">
                      <li className="flex gap-2">
                        <span className="font-bold text-blue-600 flex-shrink-0">1.</span>
                        <div>
                          Go to <a href="https://console.cloud.google.com/auth/overview" target="_blank" rel="noreferrer" className="text-blue-600 underline font-medium">Google Auth Platform</a> &rarr; <strong>App name</strong> + <strong>email</strong> &rarr; Next
                        </div>
                      </li>
                      <li className="flex gap-2">
                        <span className="font-bold text-blue-600 flex-shrink-0">2.</span>
                        <div><strong>Audience:</strong> External &rarr; Next</div>
                      </li>
                      <li className="flex gap-2">
                        <span className="font-bold text-blue-600 flex-shrink-0">3.</span>
                        <div><strong>Contact:</strong> your email &rarr; Next &rarr; Agree &rarr; <strong>Create</strong></div>
                      </li>
                      <li className="flex gap-2">
                        <span className="font-bold text-blue-600 flex-shrink-0">4.</span>
                        <div>
                          Sidebar &rarr; <a href="https://console.cloud.google.com/auth/audience" target="_blank" rel="noreferrer" className="text-blue-600 underline">Audience</a> &rarr; <strong>+ Add users</strong> &rarr; your Gmail &rarr; Save
                        </div>
                      </li>
                      <li className="flex gap-2">
                        <span className="font-bold text-blue-600 flex-shrink-0">5.</span>
                        <div>
                          <strong>Enable APIs.</strong> Click each button below to open the API page, then click the blue "Enable" button on each:
                          <div className="flex flex-col gap-2 mt-2">
                            <a href="https://console.cloud.google.com/apis/library/gmail.googleapis.com" target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-2 bg-blue-50 border border-blue-200 rounded hover:bg-blue-100 transition text-blue-700 font-medium text-xs">
                              <span>&#x2192;</span> Click to enable Gmail API
                            </a>
                            <a href="https://console.cloud.google.com/apis/library/calendar-json.googleapis.com" target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-2 bg-blue-50 border border-blue-200 rounded hover:bg-blue-100 transition text-blue-700 font-medium text-xs">
                              <span>&#x2192;</span> Click to enable Google Calendar API
                            </a>
                            <a href="https://console.cloud.google.com/apis/library/drive.googleapis.com" target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-2 bg-blue-50 border border-blue-200 rounded hover:bg-blue-100 transition text-blue-700 font-medium text-xs">
                              <span>&#x2192;</span> Click to enable Google Drive API
                            </a>
                            <a href="https://console.cloud.google.com/apis/library/people.googleapis.com" target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-2 bg-blue-50 border border-blue-200 rounded hover:bg-blue-100 transition text-blue-700 font-medium text-xs">
                              <span>&#x2192;</span> Click to enable People API (Contacts)
                            </a>
                          </div>
                          <p className="text-gray-400 mt-1">Make sure your project is selected at the top of each page. Click the blue "Enable" button on each.</p>
                        </div>
                      </li>
                      <li className="flex gap-2">
                        <span className="font-bold text-blue-600 flex-shrink-0">6.</span>
                        <div>
                          Sidebar &rarr; <a href="https://console.cloud.google.com/auth/scopes" target="_blank" rel="noreferrer" className="text-blue-600 underline">Data Access</a> &rarr; <strong>Add or remove scopes</strong> &rarr; scroll to bottom &rarr; paste into "Manually add scopes":
                          <code className="block bg-gray-900 text-green-400 p-2 rounded text-[10px] break-all select-all mt-1">https://www.googleapis.com/auth/gmail.readonly, https://www.googleapis.com/auth/gmail.send, https://www.googleapis.com/auth/gmail.compose, https://www.googleapis.com/auth/calendar.readonly, https://www.googleapis.com/auth/calendar.events, https://www.googleapis.com/auth/drive.readonly, https://www.googleapis.com/auth/drive.file, https://www.googleapis.com/auth/contacts.readonly</code>
                          <p className="text-gray-400 mt-1">Click "Add to table" &rarr; "Update" &rarr; "Save"</p>
                        </div>
                      </li>
                    </ol>
                    <div className="flex gap-2 pt-2">
                      <button onClick={() => setGoogleStep('guide-0')} className="px-4 py-2 border border-gray-300 rounded text-sm hover:bg-gray-50">&larr; Back</button>
                      <button onClick={() => setGoogleStep('guide-2')} className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">Next &rarr;</button>
                    </div>
                  </>)}

                  {/* Guide Step 2: Create client + download JSON → back to quick flow */}
                  {googleStep === 'guide-2' && (<>
                    <p className="font-medium text-gray-800">Create OAuth client & download credentials:</p>
                    <ol className="space-y-3 text-xs">
                      <li className="flex gap-2">
                        <span className="font-bold text-blue-600 flex-shrink-0">1.</span>
                        <div>Sidebar &rarr; <a href="https://console.cloud.google.com/auth/clients" target="_blank" rel="noreferrer" className="text-blue-600 underline font-medium">Clients</a></div>
                      </li>
                      <li className="flex gap-2">
                        <span className="font-bold text-blue-600 flex-shrink-0">2.</span>
                        <div><strong>+ Create Client</strong> &rarr; Desktop app &rarr; any name &rarr; <strong>Create</strong></div>
                      </li>
                      <li className="flex gap-2">
                        <span className="font-bold text-blue-600 flex-shrink-0">3.</span>
                        <div>Click <strong>Download JSON</strong> from the popup.</div>
                      </li>
                    </ol>
                    <div className="flex gap-2 pt-2">
                      <button onClick={() => setGoogleStep('guide-1')} className="px-4 py-2 border border-gray-300 rounded text-sm hover:bg-gray-50">&larr; Back</button>
                      <button onClick={() => setGoogleStep('quick')} className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
                        I have the JSON &rarr; Connect
                      </button>
                    </div>
                  </>)}

                </div>
              </div>
            </div>
          )}

          {/* AntiAI Wizard */}
          {wizardOpen === 'antiai' && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setWizardOpen(null)}>
              <div className="bg-white rounded-lg p-6 max-w-lg w-full mx-4" onClick={e => e.stopPropagation()}>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">AntiAI / GhostBusters Setup</h3>
                <div className="space-y-4 text-sm text-gray-600">
                  <p>Connect to a running GhostBusters instance to scan generated content for AI patterns and humanize flagged text.</p>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">API URL</label>
                    <input
                      type="text"
                      value={antiaiUrl}
                      onChange={e => setAntiaiUrl(e.target.value)}
                      className="w-full border border-gray-300 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-blue-400"
                      placeholder="http://localhost:8066"
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={async () => {
                        // Save config first
                        await api.put(`/integrations/antiai/config`, { api_url: antiaiUrl, enabled: true });
                        // Then test
                        setIntgTesting('antiai');
                        try {
                          const res = await api.post<IntegrationTestResult>('/integrations/antiai/test', {});
                          setIntgTestResult(prev => ({ ...prev, antiai: res }));
                          queryClient.invalidateQueries({ queryKey: ['integrations'] });
                        } catch (e) {
                          setIntgTestResult(prev => ({ ...prev, antiai: { status: 'error', message: String(e) } }));
                        } finally {
                          setIntgTesting(null);
                        }
                      }}
                      className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
                    >
                      Save & Test
                    </button>
                    <button
                      onClick={async () => {
                        await api.put(`/integrations/antiai/config`, { enabled: false, api_url: '' });
                        queryClient.invalidateQueries({ queryKey: ['integrations'] });
                        setWizardOpen(null);
                      }}
                      className="px-4 py-2 border border-red-300 text-red-600 rounded text-sm hover:bg-red-50"
                    >
                      Disconnect
                    </button>
                    <button onClick={() => setWizardOpen(null)} className="px-4 py-2 border border-gray-300 rounded text-sm hover:bg-gray-50">
                      Close
                    </button>
                  </div>
                  <p className="text-xs text-gray-400">GhostBusters is a separate tool. Install it from its own repository and start it before connecting.</p>
                </div>
              </div>
            </div>
          )}

          {/* Indeed Wizard */}
          {wizardOpen === 'indeed' && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setWizardOpen(null)}>
              <div className="bg-white rounded-lg p-6 max-w-lg w-full mx-4" onClick={e => e.stopPropagation()}>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Indeed Integration</h3>
                <div className="space-y-4 text-sm text-gray-600">
                  <div className="p-3 bg-blue-50 rounded border border-blue-200">
                    <p className="font-medium text-blue-800">Automatic via AI Provider</p>
                    <p className="mt-1">Indeed access works through the Claude CLI tunnel. No separate setup needed.</p>
                  </div>
                  <p>Requirements:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Claude CLI installed and authenticated</li>
                    <li>AI Provider set to "Claude" and enabled</li>
                    <li>Indeed MCP connected in your Claude session</li>
                  </ul>
                  <div className="flex gap-2">
                    <button
                      onClick={async () => {
                        setIntgTesting('indeed');
                        try {
                          const res = await api.post<IntegrationTestResult>('/integrations/indeed/test', {});
                          setIntgTestResult(prev => ({ ...prev, indeed: res }));
                        } catch (e) {
                          setIntgTestResult(prev => ({ ...prev, indeed: { status: 'error', message: String(e) } }));
                        } finally {
                          setIntgTesting(null);
                        }
                      }}
                      className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
                    >
                      Test Connection
                    </button>
                    <button onClick={() => setWizardOpen(null)} className="px-4 py-2 border border-gray-300 rounded text-sm hover:bg-gray-50">
                      Close
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* AI Provider Wizard */}
          {wizardOpen === 'ai_provider' && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setWizardOpen(null)}>
              <div className="bg-white rounded-lg p-6 max-w-lg w-full mx-4" onClick={e => e.stopPropagation()}>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">AI Provider Setup</h3>
                <div className="space-y-4 text-sm text-gray-600">
                  <p>The AI provider powers enhanced features like smart resume parsing, JD analysis, and content generation.</p>
                  <p>Configure the provider in the <strong>General</strong> tab under "AI Provider". The provider must have its CLI tool installed in the backend container.</p>
                  <div className="p-3 bg-gray-50 rounded border border-gray-200">
                    <p className="font-medium text-gray-800 mb-2">Supported providers:</p>
                    <ul className="space-y-1">
                      <li><strong>Claude</strong> — Full support, all 40 AI endpoints. Requires Claude CLI.</li>
                      <li><strong>Gemini</strong> — Stub (coming soon). Requires Gemini CLI.</li>
                      <li><strong>OpenAI</strong> — Stub (coming soon). Requires OpenAI CLI.</li>
                    </ul>
                  </div>
                  <button onClick={() => { setWizardOpen(null); setActiveTab('general'); }} className="px-4 py-2 bg-gray-900 text-white rounded text-sm hover:bg-gray-700">
                    Go to General Settings
                  </button>
                </div>
              </div>
            </div>
          )}
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

      {/* Onboarding Checklist — collapsible, auto-collapsed when complete */}
      {onboard && (
      <details className="bg-white rounded-lg border border-gray-200 mb-6 group" open={onboard.completion_pct !== 100}>
        <summary className="p-4 cursor-pointer list-none flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-gray-900">Onboarding Checklist</h2>
            {onboard.completion_pct === 100 && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">Complete</span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {onboard.completion_pct != null && (
              <span className="text-xs text-gray-500">{onboard.completed_count}/{onboard.total_steps}</span>
            )}
            <span className="text-gray-400 group-open:rotate-180 transition-transform">&#x25BC;</span>
          </div>
        </summary>
        <div className="px-4 pb-4">
          {onboard.completion_pct != null && (
            <div className="mb-3">
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${onboard.completion_pct === 100 ? 'bg-green-500' : 'bg-blue-600'}`}
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
        </div>
      </details>
      )}
      {onboardStatus.isLoading && <p className="text-sm text-gray-400 mb-6">Loading checklist...</p>}

      {/* Profile Link */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Profile</h2>
            <p className="text-sm text-gray-500 mt-1">Manage your name, contact info, target roles, and salary preferences.</p>
          </div>
          <a href="/profile" className="px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700">
            Go to Profile
          </a>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* System Status */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">System Status</h2>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">API</span>
              <span className={`text-sm font-medium ${health.data?.status === 'ok' || health.data?.status === 'healthy' ? 'text-green-600' : 'text-red-600'}`}>
                {health.data?.status === 'ok' ? 'healthy' : health.data?.status ?? 'checking...'}
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

            {/* Auto-detected provider status */}
            {aiProviders.data?.providers && (
              <div className="flex flex-wrap gap-2">
                {aiProviders.data.providers.map((p) => (
                  <div key={p.name} className="flex items-center gap-1.5 text-xs px-2 py-1 rounded bg-gray-50 border border-gray-200">
                    <span className={`inline-block w-2 h-2 rounded-full ${p.available ? 'bg-green-500' : 'bg-gray-300'}`} />
                    <span className="capitalize">{p.name}</span>
                    {p.available && p.model && <span className="text-gray-400">({p.model})</span>}
                  </div>
                ))}
              </div>
            )}

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
