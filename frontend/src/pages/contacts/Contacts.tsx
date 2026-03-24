import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, crm } from '../../api/client';
import type { Contact, OutreachMessage } from '../../api/client';
import ComposeModal from './ComposeModal';

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

const channelIcon: Record<string, string> = {
  gmail: 'text-red-500',
  email: 'text-red-500',
  linkedin: 'text-blue-600',
  linkedin_message: 'text-blue-600',
  phone: 'text-green-600',
  other: 'text-gray-500',
};

function DetailPanel({
  contact,
  healthScore,
  onClose,
}: {
  contact: Contact;
  healthScore?: number;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [showCompose, setShowCompose] = useState(false);
  const [editingDraft, setEditingDraft] = useState<OutreachMessage | null>(null);
  const [viewingMessage, setViewingMessage] = useState<OutreachMessage | null>(null);
  const [convTab, setConvTab] = useState<'messages' | 'touchpoints'>('messages');

  const { data: detail } = useQuery({
    queryKey: ['contact-detail', contact.id],
    queryFn: () => api.get<ContactDetail>(`/contacts/${contact.id}`),
  });

  const { data: conversations } = useQuery({
    queryKey: ['conversations', contact.id],
    queryFn: () => crm.conversations(contact.id),
  });

  const d = detail ?? (contact as any);
  const msgs = conversations?.messages ?? [];
  const tps = conversations?.touchpoints ?? [];

  const handleSent = () => {
    setShowCompose(false);
    setEditingDraft(null);
    queryClient.invalidateQueries({ queryKey: ['conversations', contact.id] });
    queryClient.invalidateQueries({ queryKey: ['contact-detail', contact.id] });
    queryClient.invalidateQueries({ queryKey: ['crm-health'] });
  };

  const openEditDraft = (msg: OutreachMessage) => {
    setEditingDraft(msg);
    setShowCompose(true);
  };

  const handleDeleteDraft = async (msg: OutreachMessage) => {
    if (!confirm('Delete this draft? This also removes it from Gmail.')) return;
    try {
      await crm.deleteDraft(msg.id);
      queryClient.invalidateQueries({ queryKey: ['conversations', contact.id] });
    } catch (e: any) {
      alert(e?.message || 'Failed to delete draft');
    }
  };

  return (
    <>
      <div className="fixed inset-y-0 right-0 w-[440px] bg-white shadow-xl border-l border-gray-200 z-50 overflow-y-auto">
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

          {/* Compose Message Button */}
          <div className="border-t border-gray-200 pt-3">
            <button
              onClick={() => setShowCompose(true)}
              className="w-full px-3 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              Compose Message
            </button>
          </div>

          {/* Conversation History */}
          <div className="border-t border-gray-200 pt-3">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-700">Conversation History</h3>
              <div className="flex border border-gray-200 rounded overflow-hidden">
                <button
                  onClick={() => setConvTab('messages')}
                  className={`px-2 py-1 text-[11px] ${convTab === 'messages' ? 'bg-gray-800 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'}`}
                >
                  Messages ({msgs.length})
                </button>
                <button
                  onClick={() => setConvTab('touchpoints')}
                  className={`px-2 py-1 text-[11px] ${convTab === 'touchpoints' ? 'bg-gray-800 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'}`}
                >
                  Touchpoints ({tps.length})
                </button>
              </div>
            </div>

            {convTab === 'messages' && (
              <div className="space-y-2 max-h-72 overflow-y-auto">
                {msgs.length === 0 && (
                  <p className="text-xs text-gray-400 py-2">No messages yet</p>
                )}
                {msgs.map((m: OutreachMessage) => {
                  const isDraft = (m as any).status === 'draft' || (!m.sent_at && m.channel === 'gmail');
                  const isSent = m.direction === 'sent' && !isDraft;
                  const isReceived = m.direction !== 'sent' && !isDraft;

                  const borderColor = isDraft
                    ? 'border-yellow-200'
                    : isSent ? 'border-green-200' : 'border-orange-200';
                  const bgColor = isDraft
                    ? 'bg-yellow-50'
                    : isSent ? 'bg-green-50' : 'bg-orange-50';
                  const leftAccent = isDraft
                    ? 'border-l-yellow-400'
                    : isSent ? 'border-l-green-500' : 'border-l-orange-500';

                  return (
                    <div
                      key={m.id}
                      onClick={() => isDraft ? openEditDraft(m) : setViewingMessage(m)}
                      className={`rounded border border-l-[3px] ${borderColor} ${leftAccent} ${bgColor} p-2.5 cursor-pointer hover:opacity-80 transition-opacity`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-1.5">
                          <span className={`text-[10px] font-medium uppercase px-1.5 py-0.5 rounded ${
                            m.channel === 'gmail' || m.channel === 'email'
                              ? 'bg-red-50 text-red-600'
                              : 'bg-blue-50 text-blue-600'
                          }`}>
                            {m.channel === 'gmail' ? 'Email' : m.channel}
                          </span>
                          {isDraft ? (
                            <span className="text-[10px] font-medium text-yellow-600 bg-yellow-100 px-1.5 py-0.5 rounded">Draft</span>
                          ) : (
                            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                              isSent ? 'text-green-700 bg-green-100' : 'text-orange-700 bg-orange-100'
                            }`}>
                              {isSent ? 'Sent' : 'Received'}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          {isDraft && (
                            <button
                              onClick={(e) => { e.stopPropagation(); handleDeleteDraft(m); }}
                              className="text-[10px] text-red-400 hover:text-red-600"
                              title="Delete draft"
                            >
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          )}
                          <span className="text-[10px] text-gray-400">
                            {m.sent_at ? new Date(m.sent_at).toLocaleDateString() : m.created_at ? new Date(m.created_at).toLocaleDateString() : ''}
                          </span>
                        </div>
                      </div>
                      {m.subject && (
                        <p className="text-xs font-medium text-gray-700 mb-0.5">{m.subject}</p>
                      )}
                      <p className="text-xs text-gray-600 whitespace-pre-wrap line-clamp-3">{m.body}</p>
                    </div>
                  );
                })}
              </div>
            )}

            {convTab === 'touchpoints' && (
              <div className="space-y-2 max-h-72 overflow-y-auto">
                {tps.length === 0 && (
                  <p className="text-xs text-gray-400 py-2">No touchpoints yet</p>
                )}
                {tps.map((tp: any) => (
                  <div key={tp.id} className="flex items-start gap-2 text-xs">
                    <span className="text-gray-400 shrink-0 mt-0.5">
                      {tp.logged_at ? new Date(tp.logged_at).toLocaleDateString() : ''}
                    </span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 ${
                      tp.type === 'email' ? 'bg-red-50 text-red-600'
                        : tp.type === 'linkedin_message' ? 'bg-blue-50 text-blue-600'
                        : 'bg-gray-100 text-gray-600'
                    }`}>
                      {tp.type}
                    </span>
                    <span className="text-gray-400 text-[10px]">{tp.direction}</span>
                    <span className="text-gray-700">{tp.notes}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Compose Modal */}
      {showCompose && (
        <ComposeModal
          contact={d}
          onClose={() => {
            setShowCompose(false);
            setEditingDraft(null);
            // Always refresh conversations on close (auto-save may have created/updated drafts)
            queryClient.invalidateQueries({ queryKey: ['conversations', contact.id] });
          }}
          onSent={handleSent}
          editDraft={editingDraft}
          onDeleted={handleSent}
        />
      )}

      {/* Read-only message popup */}
      {viewingMessage && (
        <div className="fixed inset-0 bg-black/40 z-[60] flex items-center justify-center" onClick={() => setViewingMessage(null)}>
          <div className="bg-white rounded-lg shadow-2xl w-[500px] max-h-[70vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`text-[10px] font-medium uppercase px-1.5 py-0.5 rounded ${
                  viewingMessage.channel === 'gmail' || viewingMessage.channel === 'email' ? 'bg-red-50 text-red-600' : 'bg-blue-50 text-blue-600'
                }`}>{viewingMessage.channel === 'gmail' ? 'Email' : viewingMessage.channel}</span>
                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                  viewingMessage.direction === 'sent' ? 'bg-green-50 text-green-700' : 'bg-orange-50 text-orange-700'
                }`}>{viewingMessage.direction === 'sent' ? 'Sent' : 'Received'}</span>
                <span className="text-[10px] text-gray-400">
                  {viewingMessage.sent_at ? new Date(viewingMessage.sent_at).toLocaleString() : viewingMessage.created_at ? new Date(viewingMessage.created_at).toLocaleString() : ''}
                </span>
              </div>
              <button onClick={() => setViewingMessage(null)} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
            </div>
            <div className="p-4 overflow-y-auto">
              {viewingMessage.subject && <p className="text-sm font-medium text-gray-800 mb-2">{viewingMessage.subject}</p>}
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{viewingMessage.body}</p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

interface ContactsResponse {
  contacts: Contact[];
  total: number;
  limit: number;
  offset: number;
}

const PAGE_SIZE = 50;

const sortLabels: Record<string, string> = {
  name: 'Name', '-name': 'Name',
  company: 'Company', '-company': 'Company',
  '-last_contact': 'Last Contact', last_contact: 'Last Contact',
  '-created': 'Created', created: 'Created',
  strength: 'Strength', '-strength': 'Strength',
};

export default function Contacts() {
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [strengthFilter, setStrengthFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [sort, setSort] = useState('-last_contact');
  const [page, setPage] = useState(0);

  // Debounce search
  const searchTimer = useState<ReturnType<typeof setTimeout> | null>(null);
  const handleSearch = (val: string) => {
    setSearch(val);
    if (searchTimer[0]) clearTimeout(searchTimer[0]);
    searchTimer[1] = setTimeout(() => {
      setDebouncedSearch(val);
      setPage(0);
    }, 300);
  };

  // Build query string
  const params = new URLSearchParams();
  if (debouncedSearch) params.set('q', debouncedSearch);
  if (strengthFilter) params.set('strength', strengthFilter);
  if (sourceFilter) params.set('source', sourceFilter);
  params.set('sort', sort);
  params.set('limit', String(PAGE_SIZE));
  params.set('offset', String(page * PAGE_SIZE));
  const qs = `?${params.toString()}`;

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['contacts', qs],
    queryFn: () => api.get<ContactsResponse>(`/contacts${qs}`),
    placeholderData: (prev: any) => prev,
  });

  const contactList = data?.contacts ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  const toggleSort = (col: string) => {
    if (sort === col) setSort(`-${col}`);
    else if (sort === `-${col}`) setSort(col);
    else setSort(`-${col}`);
    setPage(0);
  };

  const sortIcon = (col: string) => {
    if (sort === col) return ' \u25B2';
    if (sort === `-${col}`) return ' \u25BC';
    return '';
  };

  const clearFilters = () => {
    setSearch(''); setDebouncedSearch(''); setStrengthFilter(''); setSourceFilter(''); setSort('-last_contact'); setPage(0);
  };
  const hasFilters = debouncedSearch || strengthFilter || sourceFilter;

  const queryClient = useQueryClient();
  const [importProgress, setImportProgress] = useState<{ imported: number; updated: number; skipped: number; fetched: number; done: boolean } | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState(false);

  const startImport = async () => {
    setImportProgress({ imported: 0, updated: 0, skipped: 0, fetched: 0, done: false });
    setImportError(null);
    setIsImporting(true);

    let pageToken = '';
    let totals = { imported: 0, updated: 0, skipped: 0, fetched: 0 };

    try {
      while (true) {
        const res = await api.post<{
          imported: number; updated: number; skipped: number;
          total_fetched: number; next_page_token: string; errors: string[];
        }>('/contacts/import-google', { page_token: pageToken });

        totals.imported += res.imported;
        totals.updated += res.updated;
        totals.skipped += res.skipped;
        totals.fetched += res.total_fetched;
        setImportProgress({ ...totals, done: false });

        pageToken = res.next_page_token;
        if (!pageToken) break;
      }

      setImportProgress({ ...totals, done: true });
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
    } catch (e: any) {
      setImportError(e?.message || 'Import failed');
      setImportProgress(prev => prev ? { ...prev, done: true } : null);
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">Contacts</h1>
          <button
            onClick={startImport}
            disabled={isImporting}
            className="px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-50 flex items-center gap-1.5"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            {isImporting ? 'Importing...' : 'Import Google Contacts'}
          </button>
        </div>
        <span className="text-sm text-gray-500">
          {total.toLocaleString()} contact{total !== 1 ? 's' : ''}
          {hasFilters && <span className="text-gray-400"> (filtered)</span>}
          {isFetching && !isLoading && <span className="ml-2 text-gray-300">...</span>}
        </span>
      </div>

      {/* Import progress / result banner */}
      {importProgress && (
        <div className={`mb-4 px-4 py-3 rounded-lg border flex items-center justify-between ${
          importProgress.done ? 'bg-green-50 border-green-200' : 'bg-blue-50 border-blue-200'
        }`}>
          <div className="flex items-center gap-3">
            {!importProgress.done && (
              <svg className="w-4 h-4 text-blue-600 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            <span className={`text-sm ${importProgress.done ? 'text-green-800' : 'text-blue-800'}`}>
              {importProgress.done ? 'Import complete: ' : 'Importing... '}
              <strong>{importProgress.imported}</strong> new
              {importProgress.updated > 0 && <>, <strong>{importProgress.updated}</strong> updated</>}
              {importProgress.skipped > 0 && <>, {importProgress.skipped} unchanged</>}
              {' '}({importProgress.fetched} fetched from Google)
            </span>
          </div>
          {importProgress.done && (
            <button onClick={() => setImportProgress(null)} className="text-green-600 hover:text-green-800 text-lg leading-none">&times;</button>
          )}
        </div>
      )}
      {importError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center justify-between">
          <span>Import failed: {importError}</span>
          <button onClick={() => setImportError(null)} className="text-red-600 hover:text-red-800 text-lg leading-none">&times;</button>
        </div>
      )}

      {/* Search & Filters */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <input
            type="text"
            placeholder="Search name, company, title, email..."
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            className="w-full text-sm border border-gray-200 rounded-lg pl-9 pr-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <svg className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <select
          value={strengthFilter}
          onChange={(e) => { setStrengthFilter(e.target.value); setPage(0); }}
          className="text-xs border border-gray-200 rounded px-2 py-2 bg-white text-gray-700"
        >
          <option value="">All strengths</option>
          <option value="strong">Strong</option>
          <option value="warm">Warm</option>
          <option value="cold">Cold</option>
        </select>
        <select
          value={sourceFilter}
          onChange={(e) => { setSourceFilter(e.target.value); setPage(0); }}
          className="text-xs border border-gray-200 rounded px-2 py-2 bg-white text-gray-700"
        >
          <option value="">All sources</option>
          <option value="linkedin">LinkedIn</option>
          <option value="manual">Manual</option>
          <option value="import">Import</option>
          <option value="email">Email</option>
        </select>
        {hasFilters && (
          <button onClick={clearFilters} className="text-xs text-gray-500 hover:text-gray-700 underline">
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {[
                { key: 'name', label: 'Name' },
                { key: 'company', label: 'Company' },
                { key: 'title', label: 'Title', sortable: false },
                { key: 'strength', label: 'Strength' },
                { key: 'last_contact', label: 'Last Contact' },
              ].map(({ key, label, sortable }) => (
                <th
                  key={key}
                  onClick={sortable !== false ? () => toggleSort(key) : undefined}
                  className={`text-left px-4 py-3 font-medium text-gray-500 ${sortable !== false ? 'cursor-pointer hover:text-gray-700 select-none' : ''}`}
                >
                  {label}{sortable !== false ? sortIcon(key) : ''}
                </th>
              ))}
              <th className="text-left px-4 py-3 font-medium text-gray-500">Source</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
            )}
            {!isLoading && contactList.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                {hasFilters ? 'No contacts match your filters' : 'No contacts yet'}
              </td></tr>
            )}
            {contactList.map((c: any) => (
              <tr
                key={c.id}
                className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                onClick={() => setSelectedContact(c)}
              >
                <td className="px-4 py-3 font-medium text-gray-900">
                  <div className="flex items-center gap-1.5">
                    {c.name}
                    {c.is_reference && <span className="text-yellow-500 text-sm" title="Reference">&#9733;</span>}
                  </div>
                  {c.email && <p className="text-[11px] text-gray-400 truncate max-w-[200px]">{c.email}</p>}
                </td>
                <td className="px-4 py-3 text-gray-700">{c.company || '-'}</td>
                <td className="px-4 py-3 text-gray-500 truncate max-w-[180px]">{c.title || '-'}</td>
                <td className="px-4 py-3">
                  {c.relationship_strength ? (
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${strengthColor[c.relationship_strength] || 'bg-gray-100 text-gray-600'}`}>
                      {c.relationship_strength}
                    </span>
                  ) : <span className="text-xs text-gray-400">-</span>}
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {c.last_contact ? new Date(c.last_contact).toLocaleDateString() : '-'}
                </td>
                <td className="px-4 py-3">
                  <span className="text-[10px] text-gray-400">{c.source || '-'}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-4 py-3 border-t border-gray-200 bg-gray-50 flex items-center justify-between">
            <span className="text-xs text-gray-500">
              Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total.toLocaleString()}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage(0)}
                disabled={page === 0}
                className="px-2 py-1 text-xs rounded border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                First
              </button>
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-2 py-1 text-xs rounded border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Prev
              </button>
              <span className="px-3 py-1 text-xs text-gray-600">
                Page {page + 1} of {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="px-2 py-1 text-xs rounded border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Next
              </button>
              <button
                onClick={() => setPage(totalPages - 1)}
                disabled={page >= totalPages - 1}
                className="px-2 py-1 text-xs rounded border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Last
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Detail Panel */}
      {selectedContact && (
        <DetailPanel
          contact={selectedContact}
          healthScore={(selectedContact as any).health_score}
          onClose={() => setSelectedContact(null)}
        />
      )}
    </div>
  );
}
