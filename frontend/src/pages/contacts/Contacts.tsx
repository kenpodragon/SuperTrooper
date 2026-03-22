import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { contacts, api } from '../../api/client';
import type { Contact } from '../../api/client';

const strengthColor: Record<string, string> = {
  strong: 'bg-green-100 text-green-700',
  warm: 'bg-yellow-100 text-yellow-700',
  cold: 'bg-blue-100 text-blue-700',
  stale: 'bg-gray-100 text-gray-500',
};

const healthColor = (score: number) =>
  score >= 70 ? 'text-green-600 bg-green-50' : score >= 40 ? 'text-yellow-600 bg-yellow-50' : 'text-red-600 bg-red-50';

const healthDot = (score: number) =>
  score >= 70 ? 'bg-green-500' : score >= 40 ? 'bg-yellow-500' : 'bg-red-400';

interface HealthEntry {
  id: number;
  health_score: number;
  days_since_contact?: number;
}

interface ContactDetail {
  id: number;
  name: string;
  company?: string;
  title?: string;
  email?: string;
  phone?: string;
  linkedin_url?: string;
  relationship?: string;
  relationship_strength?: string;
  is_reference?: boolean;
  notes?: string;
  touchpoints?: Touchpoint[];
}

interface Touchpoint {
  id: number;
  type: string;
  note?: string;
  created_at?: string;
}

interface OutreachDraft {
  subject?: string;
  body?: string;
}

function DetailPanel({
  contact,
  healthScore,
  onClose,
}: {
  contact: Contact;
  healthScore?: number;
  onClose: () => void;
}) {
  const { data: detail } = useQuery({
    queryKey: ['contact-detail', contact.id],
    queryFn: () => api.get<ContactDetail>(`/contacts/${contact.id}`),
  });

  const [showOutreach, setShowOutreach] = useState(false);
  const outreach = useQuery({
    queryKey: ['contact-outreach', contact.id],
    queryFn: () => api.post<OutreachDraft>('/crm/generate-outreach', { contact_id: contact.id }),
    enabled: showOutreach,
  });

  const d = detail ?? (contact as any);

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-white shadow-xl border-l border-gray-200 z-50 overflow-y-auto">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">{d.name}</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
      </div>
      <div className="p-4 space-y-4">
        {/* Header info */}
        <div className="flex items-center gap-2">
          {d.is_reference && (
            <span className="text-yellow-500 text-lg" title="Reference">&#9733;</span>
          )}
          {healthScore != null && (
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${healthColor(healthScore)}`}>
              Health: {healthScore}
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <p className="text-xs text-gray-500">Company</p>
            <p className="text-sm text-gray-800">{d.company || '-'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Title</p>
            <p className="text-sm text-gray-800">{d.title || '-'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Email</p>
            <p className="text-sm text-gray-800">{d.email || '-'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Phone</p>
            <p className="text-sm text-gray-800">{d.phone || '-'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Relationship</p>
            <p className="text-sm text-gray-800">{d.relationship || '-'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Strength</p>
            {d.relationship_strength ? (
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${strengthColor[d.relationship_strength] || 'bg-gray-100'}`}>
                {d.relationship_strength}
              </span>
            ) : <span className="text-sm text-gray-400">-</span>}
          </div>
        </div>

        {d.linkedin_url && (
          <div>
            <p className="text-xs text-gray-500">LinkedIn</p>
            <a href={d.linkedin_url} target="_blank" rel="noreferrer" className="text-sm text-blue-600 hover:underline break-all">
              {d.linkedin_url}
            </a>
          </div>
        )}

        {d.notes && (
          <div>
            <p className="text-xs text-gray-500">Notes</p>
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{d.notes}</p>
          </div>
        )}

        {/* Generate Outreach */}
        <div className="border-t border-gray-200 pt-3">
          <button
            onClick={() => setShowOutreach(true)}
            className="px-3 py-1.5 bg-gray-900 text-white text-xs rounded hover:bg-gray-700"
          >
            Generate Outreach
          </button>
          {outreach.isLoading && <p className="text-xs text-gray-400 mt-2">Generating...</p>}
          {outreach.data && (
            <div className="mt-2 bg-gray-50 rounded border border-gray-200 p-3">
              {outreach.data.subject && (
                <p className="text-xs font-medium text-gray-700 mb-1">Subject: {outreach.data.subject}</p>
              )}
              <p className="text-xs text-gray-600 whitespace-pre-wrap">{outreach.data.body}</p>
            </div>
          )}
        </div>

        {/* Touchpoint History */}
        {d.touchpoints && d.touchpoints.length > 0 && (
          <div className="border-t border-gray-200 pt-3">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Touchpoint History</h3>
            <div className="space-y-2">
              {d.touchpoints.map((tp: Touchpoint) => (
                <div key={tp.id} className="flex items-start gap-2 text-xs">
                  <span className="text-gray-400 shrink-0 mt-0.5">
                    {tp.created_at ? new Date(tp.created_at).toLocaleDateString() : ''}
                  </span>
                  <span className="px-1.5 py-0.5 bg-gray-100 rounded text-gray-600 shrink-0">{tp.type}</span>
                  <span className="text-gray-700">{tp.note}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function Contacts() {
  const [viewMode, setViewMode] = useState<'list' | 'company'>('list');
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['contacts'],
    queryFn: () => contacts.list('?limit=200'),
  });

  const { data: healthData } = useQuery({
    queryKey: ['crm-health'],
    queryFn: () => api.get<HealthEntry[]>('/crm/health'),
  });

  const healthMap: Record<number, number> = {};
  (healthData ?? []).forEach((h: HealthEntry) => { healthMap[h.id] = h.health_score; });

  const contactList = data ?? [];

  // Group by company
  const byCompany: Record<string, Contact[]> = {};
  contactList.forEach((c: Contact) => {
    const key = c.company || 'Unknown';
    if (!byCompany[key]) byCompany[key] = [];
    byCompany[key].push(c);
  });
  const companyGroups = Object.entries(byCompany).sort((a, b) => b[1].length - a[1].length);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Contacts</h1>
        <div className="flex items-center gap-3">
          <div className="flex border border-gray-200 rounded overflow-hidden">
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-1.5 text-xs ${viewMode === 'list' ? 'bg-gray-900 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
            >
              List
            </button>
            <button
              onClick={() => setViewMode('company')}
              className={`px-3 py-1.5 text-xs ${viewMode === 'company' ? 'bg-gray-900 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
            >
              By Company
            </button>
          </div>
          <span className="text-sm text-gray-500">{contactList.length} contacts</span>
        </div>
      </div>

      {viewMode === 'list' && (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Name</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Company</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Title</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Relationship</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Health</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Last Contact</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
              )}
              {contactList.map((c: Contact) => (
                <tr
                  key={c.id}
                  className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                  onClick={() => setSelectedContact(c)}
                >
                  <td className="px-4 py-3 font-medium text-gray-900">
                    <div className="flex items-center gap-1.5">
                      {c.name}
                      {(c as any).is_reference && (
                        <span className="text-yellow-500 text-sm" title="Reference">&#9733;</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-700">{c.company || '-'}</td>
                  <td className="px-4 py-3 text-gray-500">{c.title || '-'}</td>
                  <td className="px-4 py-3">
                    {c.relationship_strength && (
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${strengthColor[c.relationship_strength] || 'bg-gray-100 text-gray-600'}`}>
                        {c.relationship_strength}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {healthMap[c.id] != null ? (
                      <div className="flex items-center gap-1.5">
                        <span className={`inline-block w-2.5 h-2.5 rounded-full ${healthDot(healthMap[c.id])}`} />
                        <span className="text-xs text-gray-600">{healthMap[c.id]}</span>
                      </div>
                    ) : (
                      <span className="text-xs text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{c.last_contact || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {viewMode === 'company' && (
        <div className="space-y-4">
          {companyGroups.map(([company, contacts]) => (
            <div key={company} className="bg-white rounded-lg border border-gray-200">
              <div className="p-3 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-800">{company}</h3>
                <span className="text-xs text-gray-500">{contacts.length} contact{contacts.length !== 1 ? 's' : ''}</span>
              </div>
              <div className="divide-y divide-gray-100">
                {contacts.map((c: Contact) => (
                  <div
                    key={c.id}
                    className="p-3 flex items-center justify-between cursor-pointer hover:bg-gray-50"
                    onClick={() => setSelectedContact(c)}
                  >
                    <div className="flex items-center gap-2">
                      {healthMap[c.id] != null && (
                        <span className={`inline-block w-2.5 h-2.5 rounded-full ${healthDot(healthMap[c.id])}`} />
                      )}
                      <div>
                        <p className="text-sm font-medium text-gray-900 flex items-center gap-1">
                          {c.name}
                          {(c as any).is_reference && <span className="text-yellow-500" title="Reference">&#9733;</span>}
                        </p>
                        <p className="text-xs text-gray-500">{c.title || '-'}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {c.relationship_strength && (
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${strengthColor[c.relationship_strength] || 'bg-gray-100'}`}>
                          {c.relationship_strength}
                        </span>
                      )}
                      <span className="text-xs text-gray-400">{c.last_contact || ''}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Detail Panel */}
      {selectedContact && (
        <DetailPanel
          contact={selectedContact}
          healthScore={healthMap[selectedContact.id]}
          onClose={() => setSelectedContact(null)}
        />
      )}
    </div>
  );
}
