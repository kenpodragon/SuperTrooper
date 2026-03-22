import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface Contact {
  id: number;
  name: string;
  company?: string;
  relationship_stage?: string;
  last_touchpoint_at?: string;
  health_score?: number;
}

interface PipelineStage {
  count: number;
  contacts: Contact[];
}

interface PipelineData {
  cold: PipelineStage;
  warm: PipelineStage;
  active: PipelineStage;
  close: PipelineStage;
  dormant: PipelineStage;
}

interface HealthEntry {
  id: number;
  health_score: number;
}

interface NetworkingTask {
  id: number;
  contact_name: string;
  contact_company?: string;
  task_type: string;
  title?: string;
  due_date?: string;
}

interface TouchpointResponse {
  id: number;
  contact_id: number;
  note: string;
  type: string;
}

const STAGES = ['cold', 'warm', 'active', 'close', 'dormant'];

const STAGE_COLORS: Record<string, string> = {
  cold: 'bg-gray-100',
  warm: 'bg-yellow-50',
  active: 'bg-orange-50',
  close: 'bg-green-50',
  dormant: 'bg-gray-50',
};

function HealthDot({ score }: { score?: number }) {
  if (score == null) return null;
  const color = score >= 70 ? 'bg-green-500' : score >= 40 ? 'bg-yellow-500' : 'bg-red-400';
  return (
    <span title={`Health: ${score}`} className={`inline-block w-2.5 h-2.5 rounded-full ${color}`} />
  );
}

export default function Networking() {
  const qc = useQueryClient();
  const [touchpointForm, setTouchpointForm] = useState<{
    contact_id: number | null; note: string; type: string;
  }>({ contact_id: null, note: '', type: 'email' });
  const [showTouchpoint, setShowTouchpoint] = useState(false);

  const pipeline = useQuery({
    queryKey: ['crm-pipeline'],
    queryFn: () => api.get<PipelineData>('/crm/pipeline'),
  });

  const health = useQuery({
    queryKey: ['crm-health'],
    queryFn: () => api.get<HealthEntry[]>('/crm/health'),
  });

  const tasks = useQuery({
    queryKey: ['networking-tasks'],
    queryFn: () => api.get<NetworkingTask[]>('/crm/tasks/upcoming'),
  });

  const logTouchpoint = useMutation({
    mutationFn: (data: typeof touchpointForm) => {
      if (!data.contact_id) throw new Error('contact_id required');
      return api.post<TouchpointResponse>(`/crm/contacts/${data.contact_id}/touchpoints`, { note: data.note, type: data.type });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['crm-pipeline'] });
      qc.invalidateQueries({ queryKey: ['crm-health'] });
      qc.invalidateQueries({ queryKey: ['networking-tasks'] });
      setShowTouchpoint(false);
      setTouchpointForm({ contact_id: null, note: '', type: 'email' });
    },
    onError: (error: Error) => {
      console.error('Failed to log touchpoint:', error.message);
    },
  });

  const pipelineData = pipeline.data ?? {} as PipelineData;
  const healthMap: Record<number, number> = {};
  (health.data ?? []).forEach((h: HealthEntry) => { healthMap[h.id] = h.health_score; });

  // Flatten all contacts from pipeline for the touchpoint selector
  const allContacts: Contact[] = STAGES.flatMap(s => (pipelineData as any)[s]?.contacts ?? []);

  const byStage: Record<string, Contact[]> = {};
  STAGES.forEach(s => { byStage[s] = (pipelineData as any)[s]?.contacts ?? []; });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Networking Hub</h1>
        <button
          onClick={() => setShowTouchpoint(true)}
          className="px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700"
        >
          + Log Touchpoint
        </button>
      </div>

      {showTouchpoint && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
          <h2 className="text-base font-semibold text-gray-900 mb-3">Log a Touchpoint</h2>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Contact</label>
              <select
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={touchpointForm.contact_id ?? ''}
                onChange={e => setTouchpointForm(p => ({ ...p, contact_id: Number(e.target.value) || null }))}
              >
                <option value="">Select a contact...</option>
                {allContacts.map((r: Contact) => (
                  <option key={r.id} value={r.id}>
                    {r.name}{r.company ? ` — ${r.company}` : ''}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Type</label>
              <select
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none"
                value={touchpointForm.type}
                onChange={e => setTouchpointForm(p => ({ ...p, type: e.target.value }))}
              >
                {['email', 'linkedin', 'call', 'meeting', 'coffee', 'referral'].map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Note</label>
              <input
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={touchpointForm.note}
                onChange={e => setTouchpointForm(p => ({ ...p, note: e.target.value }))}
              />
            </div>
          </div>
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => logTouchpoint.mutate(touchpointForm)}
              disabled={logTouchpoint.isPending || !touchpointForm.contact_id}
              className="px-3 py-1.5 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-50"
            >
              {logTouchpoint.isPending ? 'Saving...' : 'Save'}
            </button>
            <button onClick={() => setShowTouchpoint(false)} className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Stage columns */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        {STAGES.map(stage => (
          <div key={stage} className={`rounded-lg border border-gray-200 p-3 ${STAGE_COLORS[stage]}`}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide capitalize">{stage}</h3>
              <span className="text-xs text-gray-500">{byStage[stage].length}</span>
            </div>
            {pipeline.isLoading && <p className="text-xs text-gray-400">Loading...</p>}
            {byStage[stage].map((r: Contact) => (
              <div key={r.id} className="bg-white rounded border border-gray-100 p-2 mb-2 last:mb-0">
                <div className="flex items-center gap-1.5">
                  <HealthDot score={healthMap[r.id]} />
                  <p className="text-xs font-medium text-gray-800 truncate">{r.name}</p>
                </div>
                <p className="text-xs text-gray-500 truncate">{r.company}</p>
                {r.last_touchpoint_at && (
                  <p className="text-xs text-gray-400 mt-0.5">
                    {new Date(r.last_touchpoint_at).toLocaleDateString()}
                  </p>
                )}
              </div>
            ))}
            {!pipeline.isLoading && byStage[stage].length === 0 && (
              <p className="text-xs text-gray-400 italic">None</p>
            )}
          </div>
        ))}
      </div>

      {/* Networking Tasks */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Upcoming Networking Tasks</h2>
        {tasks.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
        {!tasks.isLoading && (tasks.data ?? []).length === 0 && (
          <p className="text-sm text-gray-400">No networking tasks due.</p>
        )}
        {(tasks.data ?? []).map((t: NetworkingTask) => (
          <div key={t.id} className="flex justify-between py-2 border-b border-gray-100 last:border-0">
            <div>
              <p className="text-sm font-medium text-gray-800">{t.title ?? t.task_type}</p>
              <p className="text-xs text-gray-500">{t.contact_name}{t.contact_company ? ` — ${t.contact_company}` : ''} &mdash; {t.task_type}</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-gray-500">{t.due_date ? new Date(t.due_date).toLocaleDateString() : 'No date'}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
