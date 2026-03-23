import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface Contact {
  id: number;
  name: string;
  company?: string;
  title?: string;
  relationship_stage?: string;
  last_touchpoint_at?: string;
  health_score?: number;
  is_reference?: boolean;
  drip_sequence_status?: string;
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

interface OutreachDraft {
  subject?: string;
  body?: string;
}

const STAGES = ['cold', 'warm', 'active', 'close', 'dormant'];
const STAGE_LABELS: Record<string, string> = {
  cold: 'Lead',
  warm: 'Warm',
  active: 'Active',
  close: 'Champion',
  dormant: 'Dormant',
};

const STAGE_COLORS: Record<string, string> = {
  cold: 'bg-gray-50 border-t-gray-400',
  warm: 'bg-yellow-50 border-t-yellow-400',
  active: 'bg-orange-50 border-t-orange-400',
  close: 'bg-green-50 border-t-green-400',
  dormant: 'bg-gray-50 border-t-gray-300',
};

const DRIP_COLORS: Record<string, string> = {
  active: 'bg-blue-100 text-blue-700',
  paused: 'bg-yellow-100 text-yellow-700',
  completed: 'bg-green-100 text-green-700',
  none: 'bg-gray-100 text-gray-500',
};

function HealthDot({ score }: { score?: number }) {
  if (score == null) return null;
  const color = score >= 70 ? 'bg-green-500' : score >= 40 ? 'bg-yellow-500' : 'bg-red-400';
  return (
    <span title={`Health: ${score}`} className={`inline-block w-2.5 h-2.5 rounded-full ${color}`} />
  );
}

function ContactCard({
  contact,
  healthScore,
  onLogTouchpoint,
  onGenerateOutreach,
}: {
  contact: Contact;
  healthScore?: number;
  onLogTouchpoint: (id: number) => void;
  onGenerateOutreach: (id: number) => void;
}) {
  return (
    <div className="bg-white rounded border border-gray-100 p-2.5 mb-2 last:mb-0">
      <div className="flex items-center gap-1.5">
        <HealthDot score={healthScore} />
        <p className="text-xs font-medium text-gray-800 truncate flex-1">{contact.name}</p>
        {contact.is_reference && (
          <span className="text-yellow-500 text-xs" title="Reference">&#9733;</span>
        )}
      </div>
      <p className="text-xs text-gray-500 truncate">{contact.company}</p>
      {contact.title && <p className="text-xs text-gray-400 truncate">{contact.title}</p>}
      <div className="flex items-center gap-1.5 mt-1 flex-wrap">
        {contact.last_touchpoint_at && (
          <span className="text-xs text-gray-400">
            {new Date(contact.last_touchpoint_at).toLocaleDateString()}
          </span>
        )}
        {contact.drip_sequence_status && contact.drip_sequence_status !== 'none' && (
          <span className={`text-xs px-1.5 py-0.5 rounded ${DRIP_COLORS[contact.drip_sequence_status] || DRIP_COLORS.none}`}>
            drip: {contact.drip_sequence_status}
          </span>
        )}
      </div>
      {/* Quick actions */}
      <div className="flex gap-1 mt-2">
        <button
          onClick={() => onLogTouchpoint(contact.id)}
          className="text-xs px-1.5 py-0.5 border border-gray-200 text-gray-600 rounded hover:bg-gray-50"
          title="Log touchpoint"
        >
          Log
        </button>
        <button
          onClick={() => onGenerateOutreach(contact.id)}
          className="text-xs px-1.5 py-0.5 border border-blue-200 text-blue-600 rounded hover:bg-blue-50"
          title="Generate outreach"
        >
          Outreach
        </button>
      </div>
    </div>
  );
}

export default function Networking() {
  const qc = useQueryClient();
  const [touchpointForm, setTouchpointForm] = useState<{
    contact_id: number | null; note: string; type: string;
  }>({ contact_id: null, note: '', type: 'email' });
  const [showTouchpoint, setShowTouchpoint] = useState(false);
  const [outreachContactId, setOutreachContactId] = useState<number | null>(null);
  const [outreachData, setOutreachData] = useState<OutreachDraft | null>(null);
  const [filterStage, setFilterStage] = useState<string>('all');
  const [filterSearch, setFilterSearch] = useState('');

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

  const outreach = useMutation({
    mutationFn: (contactId: number) => api.post<OutreachDraft>('/crm/generate-outreach', { contact_id: contactId }),
    onSuccess: (data) => setOutreachData(data),
    onError: (err: any) => alert(err?.response?.data?.error || 'Failed to generate outreach'),
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
    onError: (err: any) => alert(err?.response?.data?.error || 'Failed to log touchpoint'),
  });

  const pipelineData = pipeline.data ?? {} as PipelineData;
  const healthMap: Record<number, number> = {};
  (health.data ?? []).forEach((h: HealthEntry) => { healthMap[h.id] = h.health_score; });

  const allContacts: Contact[] = STAGES.flatMap(s => (pipelineData as any)[s]?.contacts ?? []);
  const byStage: Record<string, Contact[]> = {};
  STAGES.forEach(s => { byStage[s] = (pipelineData as any)[s]?.contacts ?? []; });

  function openTouchpoint(contactId: number) {
    setTouchpointForm({ contact_id: contactId, note: '', type: 'email' });
    setShowTouchpoint(true);
  }

  function openOutreach(contactId: number) {
    setOutreachContactId(contactId);
    setOutreachData(null);
    outreach.mutate(contactId);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Networking Hub</h1>
        <button
          onClick={() => { setTouchpointForm({ contact_id: null, note: '', type: 'email' }); setShowTouchpoint(true); }}
          className="px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700"
        >
          + Log Touchpoint
        </button>
      </div>

      {/* Outreach Draft Modal */}
      {outreachContactId != null && (
        <div className="mb-4 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-blue-900">Outreach Draft</h3>
            <button onClick={() => { setOutreachContactId(null); setOutreachData(null); }} className="text-blue-400 hover:text-blue-600">&times;</button>
          </div>
          {outreach.isPending && <p className="text-xs text-blue-600">Generating...</p>}
          {outreachData && (
            <div className="bg-white rounded border border-blue-100 p-3">
              {outreachData.subject && (
                <p className="text-xs font-medium text-gray-700 mb-1">Subject: {outreachData.subject}</p>
              )}
              <p className="text-xs text-gray-600 whitespace-pre-wrap">{outreachData.body}</p>
            </div>
          )}
        </div>
      )}

      {/* Touchpoint form */}
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
                    {r.name}{r.company ? ` - ${r.company}` : ''}
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

      {/* Filter Bar */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <input
          type="text"
          placeholder="Search contacts..."
          value={filterSearch}
          onChange={e => setFilterSearch(e.target.value)}
          className="border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400 w-48"
        />
        <select
          value={filterStage}
          onChange={e => setFilterStage(e.target.value)}
          className="border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none"
        >
          <option value="all">All Stages</option>
          {STAGES.map(s => (
            <option key={s} value={s}>{STAGE_LABELS[s]}</option>
          ))}
        </select>
        <span className="text-xs text-gray-400">
          {allContacts.length} contacts
        </span>
        {(filterStage !== 'all' || filterSearch) && (
          <button
            onClick={() => { setFilterStage('all'); setFilterSearch(''); }}
            className="text-xs text-blue-600 hover:underline"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Kanban columns with stage labels */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        {STAGES.filter(stage => filterStage === 'all' || filterStage === stage).map(stage => {
          const searchLower = filterSearch.toLowerCase();
          const filtered = byStage[stage].filter((c: Contact) =>
            !filterSearch ||
            c.name.toLowerCase().includes(searchLower) ||
            (c.company ?? '').toLowerCase().includes(searchLower) ||
            (c.title ?? '').toLowerCase().includes(searchLower)
          );
          return (
            <div key={stage} className={`rounded-lg border border-gray-200 border-t-4 p-3 ${STAGE_COLORS[stage]}`}>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
                  {STAGE_LABELS[stage]}
                </h3>
                <span className="text-xs text-gray-500">{filtered.length}</span>
              </div>
              {pipeline.isLoading && <p className="text-xs text-gray-400">Loading...</p>}
              {filtered.map((r: Contact) => (
                <ContactCard
                  key={r.id}
                  contact={r}
                  healthScore={healthMap[r.id]}
                  onLogTouchpoint={openTouchpoint}
                  onGenerateOutreach={openOutreach}
                />
              ))}
              {!pipeline.isLoading && filtered.length === 0 && (
                <p className="text-xs text-gray-400 italic">None</p>
              )}
            </div>
          );
        })}
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
              <p className="text-xs text-gray-500">
                {t.contact_name}{t.contact_company ? ` - ${t.contact_company}` : ''} &mdash; {t.task_type}
              </p>
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
