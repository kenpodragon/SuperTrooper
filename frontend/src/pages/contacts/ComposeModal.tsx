import { useState, useRef, useCallback, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { crm } from '../../api/client';
import type { Contact, SendMessagePayload, OutreachMessage } from '../../api/client';

type Channel = 'gmail' | 'linkedin';
type OutreachType = 'cold' | 'warm' | 'follow_up';

interface Props {
  contact: Contact & { linkedin_url?: string; email?: string };
  onClose: () => void;
  onSent: () => void;
  editDraft?: OutreachMessage | null;
  onDeleted?: () => void;
}

export default function ComposeModal({ contact, onClose, onSent, editDraft, onDeleted }: Props) {
  const hasEmail = !!contact.email;
  const hasLinkedIn = !!(contact as any).linkedin_url;
  const isEdit = !!editDraft;

  const defaultChannel: Channel = editDraft
    ? (editDraft.channel === 'linkedin' ? 'linkedin' : 'gmail')
    : hasEmail ? 'gmail' : 'linkedin';
  const [channel, setChannel] = useState<Channel>(defaultChannel);
  const [subject, setSubject] = useState(editDraft?.subject || '');
  const [body, setBody] = useState(editDraft?.body || '');
  const [outreachType, setOutreachType] = useState<OutreachType>('cold');
  const [useAi, setUseAi] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [genMode, setGenMode] = useState<string | null>(null);
  const [showHelp, setShowHelp] = useState(false);
  const [savedDraftId, setSavedDraftId] = useState<number | null>(editDraft?.id ?? null);
  const [autoSaveStatus, setAutoSaveStatus] = useState<string | null>(null);
  const autoSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSavedBody = useRef(editDraft?.body || '');
  const lastSavedSubject = useRef(editDraft?.subject || '');

  // Save draft immediately (used by auto-save timer and AI callbacks)
  const saveDraftNow = useCallback(async (newSubject?: string, newBody?: string) => {
    const s = newSubject ?? subject;
    const b = newBody ?? body;
    if (!b.trim()) return;

    try {
      if (savedDraftId) {
        await crm.updateDraft(savedDraftId, { subject: s, body: b, action: 'update' });
      } else {
        const res = await crm.sendMessage({
          contact_id: contact.id, channel, action: 'draft', subject: s, body: b,
        });
        if (res.outreach?.id) setSavedDraftId(res.outreach.id);
      }
      lastSavedBody.current = b;
      lastSavedSubject.current = s;
      setAutoSaveStatus('Draft saved');
      setTimeout(() => setAutoSaveStatus(null), 2000);
    } catch {
      // Silent fail
    }
  }, [subject, body, channel, contact.id, savedDraftId]);

  // Auto-save draft after 2s of inactivity when content changes
  const scheduleAutoSave = useCallback(() => {
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    autoSaveTimer.current = setTimeout(() => {
      const changed = body !== lastSavedBody.current || subject !== lastSavedSubject.current;
      if (changed) saveDraftNow();
    }, 2000);
  }, [body, subject, saveDraftNow]);

  useEffect(() => {
    if (body.trim() || subject.trim()) scheduleAutoSave();
    return () => { if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current); };
  }, [body, subject, scheduleAutoSave]);

  // Save on close if there's unsaved content
  const handleClose = async () => {
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    const hasContent = body.trim().length > 0;
    const changed = body !== lastSavedBody.current || subject !== lastSavedSubject.current;
    if (hasContent && changed) {
      try {
        if (savedDraftId) {
          await crm.updateDraft(savedDraftId, { subject, body, action: 'update' });
        } else {
          await crm.sendMessage({
            contact_id: contact.id, channel, action: 'draft', subject, body,
          });
        }
      } catch {}
    }
    onClose();
  };

  // --- Generate message (template) ---
  const generate = useMutation({
    mutationFn: () => crm.generateOutreach({
      contact_id: contact.id, type: outreachType, use_ai: useAi, channel,
    }),
    onSuccess: (data) => {
      const newSubject = data.outreach.subject || '';
      const newBody = data.outreach.body || '';
      setSubject(newSubject);
      setBody(newBody);
      setGenMode(data.outreach.mode === 'ai' ? 'ai' : 'template');
      if (newBody.trim()) saveDraftNow(newSubject, newBody);
    },
  });

  // --- Ask AI (with prompt, existing body, full context) ---
  const askAi = useMutation({
    mutationFn: () => crm.generateOutreach({
      contact_id: contact.id,
      type: outreachType,
      use_ai: true,
      channel,
      prompt: aiPrompt,
      existing_subject: subject,
      existing_body: body,
    }),
    onSuccess: (data) => {
      const newSubject = data.outreach.subject || subject;
      const newBody = data.outreach.body || '';
      setSubject(newSubject);
      setBody(newBody);
      setGenMode(data.outreach.mode === 'ai' ? 'ai' : 'template');
      if (newBody.trim()) saveDraftNow(newSubject, newBody);
    },
  });

  // --- AI Wordsmith (polish existing text) ---
  const wordsmith = useMutation({
    mutationFn: () => crm.wordsmith(body, contact.id, channel),
    onSuccess: (data) => {
      if (data.body) {
        setBody(data.body);
        setGenMode('wordsmith');
        saveDraftNow(subject, data.body);
      }
    },
  });

  // --- Send / save draft ---
  const send = useMutation({
    mutationFn: (action: 'send' | 'draft') => {
      if (isEdit && editDraft) {
        return crm.updateDraft(editDraft.id, { subject, body, action: action === 'send' ? 'send' : 'update' });
      }
      const payload: SendMessagePayload = { contact_id: contact.id, channel, action, subject, body };
      return crm.sendMessage(payload);
    },
    onSuccess: async (data) => {
      if (channel === 'linkedin' && data.result?.linkedin_url) {
        try { await navigator.clipboard.writeText(body); } catch {}
        window.open(data.result.linkedin_url, '_blank');
      }
      onSent();
    },
  });

  // --- Delete draft ---
  const deleteDraft = useMutation({
    mutationFn: () => {
      if (!editDraft) throw new Error('No draft');
      return crm.deleteDraft(editDraft.id);
    },
    onSuccess: () => (onDeleted || onSent)(),
  });

  const canSend = body.trim().length > 0 && (channel === 'linkedin' || subject.trim().length > 0);
  const isBusy = send.isPending || generate.isPending || askAi.isPending || wordsmith.isPending || deleteDraft.isPending;
  const anyError = send.error || generate.error || askAi.error || wordsmith.error || deleteDraft.error;

  return (
    <div className="fixed inset-0 bg-black/40 z-[60] flex items-center justify-center" onClick={handleClose}>
      <div className="bg-white rounded-lg shadow-2xl w-[580px] max-h-[90vh] flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>

        {/* Header */}
        <div className="p-4 border-b border-gray-200 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <div>
              <h2 className="text-base font-semibold text-gray-900">{isEdit ? 'Edit Draft' : 'Compose Message'}</h2>
              <p className="text-xs text-gray-500 mt-0.5">To: {contact.name}{contact.company ? ` at ${contact.company}` : ''}</p>
            </div>
            {autoSaveStatus && (
              <span className="text-[10px] text-green-600 bg-green-50 px-2 py-0.5 rounded-full">{autoSaveStatus}</span>
            )}
          </div>
          <button onClick={handleClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>

        <div className="overflow-y-auto flex-1">
          {/* Channel selector */}
          <div className="px-4 pt-3 flex items-center gap-3">
            <span className="text-xs text-gray-500 font-medium">Via:</span>
            <div className="flex border border-gray-200 rounded overflow-hidden">
              <button onClick={() => hasEmail && setChannel('gmail')} disabled={!hasEmail}
                className={`px-3 py-1.5 text-xs flex items-center gap-1.5 ${channel === 'gmail' ? 'bg-red-600 text-white' : hasEmail ? 'bg-white text-gray-600 hover:bg-gray-50' : 'bg-gray-50 text-gray-300 cursor-not-allowed'}`}>
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>
                Gmail
              </button>
              <button onClick={() => hasLinkedIn && setChannel('linkedin')} disabled={!hasLinkedIn}
                className={`px-3 py-1.5 text-xs flex items-center gap-1.5 ${channel === 'linkedin' ? 'bg-blue-700 text-white' : hasLinkedIn ? 'bg-white text-gray-600 hover:bg-gray-50' : 'bg-gray-50 text-gray-300 cursor-not-allowed'}`}>
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h14m-.5 15.5v-5.3a3.26 3.26 0 00-3.26-3.26c-.85 0-1.84.52-2.32 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 011.4 1.4v4.93h2.79M6.88 8.56a1.68 1.68 0 001.68-1.68c0-.93-.75-1.69-1.68-1.69a1.69 1.69 0 00-1.69 1.69c0 .93.76 1.68 1.69 1.68m1.39 9.94v-8.37H5.5v8.37h2.77z"/></svg>
                LinkedIn
              </button>
            </div>
          </div>

          {/* Template + AI toggle row */}
          <div className="px-4 pt-3 flex items-center gap-2 flex-wrap">
            {!isEdit && (
              <>
                <select value={outreachType} onChange={(e) => setOutreachType(e.target.value as OutreachType)}
                  className="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white text-gray-700">
                  <option value="cold">Cold outreach</option>
                  <option value="warm">Warm reconnect</option>
                  <option value="follow_up">Follow-up</option>
                </select>
                <button onClick={() => generate.mutate()} disabled={isBusy}
                  className={`text-xs px-3 py-1.5 rounded disabled:opacity-50 flex items-center gap-1.5 ${
                    useAi ? 'bg-purple-100 text-purple-700 hover:bg-purple-200' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}>
                  {generate.isPending && (
                    <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  )}
                  {generate.isPending
                    ? (useAi ? 'AI generating...' : 'Generating...')
                    : 'Generate Message'}
                </button>
              </>
            )}

            {/* AI toggle */}
            <label className="flex items-center gap-1.5 cursor-pointer select-none ml-auto">
              <div onClick={() => setUseAi(!useAi)}
                className={`relative w-8 h-[18px] rounded-full transition-colors ${useAi ? 'bg-purple-600' : 'bg-gray-300'}`}>
                <div className={`absolute top-[2px] w-[14px] h-[14px] rounded-full bg-white shadow transition-transform ${useAi ? 'translate-x-[16px]' : 'translate-x-[2px]'}`} />
              </div>
              <span className={`text-xs font-medium ${useAi ? 'text-purple-700' : 'text-gray-500'}`}>Use AI</span>
            </label>

            {genMode && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                genMode === 'ai' || genMode === 'wordsmith' ? 'bg-purple-50 text-purple-600' : 'bg-gray-100 text-gray-500'
              }`}>{genMode === 'ai' ? 'AI generated' : genMode === 'wordsmith' ? 'AI polished' : 'Template'}</span>
            )}
          </div>

          {/* AI Prompt Box — shown when Use AI is on */}
          {useAi && (
            <div className="px-4 pt-3">
              <div className="border border-purple-200 rounded-lg bg-purple-50/50 p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-purple-700">AI Instructions</span>
                  <button onClick={() => setShowHelp(!showHelp)} className="text-purple-400 hover:text-purple-600" title="How this works">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </button>
                </div>
                {showHelp && (
                  <p className="text-[11px] text-purple-600 mb-2 bg-purple-100 rounded px-2 py-1.5">
                    AI takes your current subject and message body plus these instructions, along with all contact data
                    (conversation history, LinkedIn profile, company info, active applications, saved jobs) to generate
                    or refine the message. Leave the email box empty to generate from scratch, or write a draft and ask
                    AI to improve it.
                  </p>
                )}
                <textarea
                  value={aiPrompt}
                  onChange={(e) => setAiPrompt(e.target.value)}
                  placeholder="e.g. Mention the VP Engineering role I applied for. Keep it short and reference our last conversation..."
                  rows={3}
                  className="w-full text-xs border border-purple-200 rounded px-3 py-2 resize-none bg-white focus:outline-none focus:ring-2 focus:ring-purple-400 focus:border-transparent placeholder-gray-400"
                />
                <div className="flex items-center justify-end mt-2">
                  <button
                    onClick={() => askAi.mutate()}
                    disabled={isBusy}
                    className="px-4 py-1.5 text-xs font-medium text-white bg-purple-600 rounded hover:bg-purple-700 disabled:opacity-50 flex items-center gap-1.5"
                  >
                    {askAi.isPending ? (
                      <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                    ) : (
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    )}
                    {askAi.isPending ? 'AI thinking...' : 'Ask AI'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Subject (Gmail only) */}
          {channel === 'gmail' && (
            <div className="px-4 pt-3">
              <input type="text" placeholder="Subject" value={subject} onChange={(e) => setSubject(e.target.value)}
                className="w-full text-sm border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
            </div>
          )}

          {/* Body */}
          <div className="px-4 pt-3 pb-2">
            <textarea
              placeholder={channel === 'linkedin' ? 'Type your LinkedIn message...' : 'Type your email...'}
              value={body} onChange={(e) => setBody(e.target.value)} rows={10}
              className="w-full text-sm border border-gray-200 rounded px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 shrink-0 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isEdit && (
              <button onClick={() => { if (confirm('Delete this draft?')) deleteDraft.mutate(); }} disabled={isBusy}
                className="p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded disabled:opacity-50" title="Delete draft">
                {deleteDraft.isPending ? (
                  <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                )}
              </button>
            )}
            {useAi && body.trim().length > 0 && (
              <button onClick={() => wordsmith.mutate()} disabled={isBusy}
                className="px-3 py-1.5 text-xs rounded bg-purple-50 text-purple-700 hover:bg-purple-100 disabled:opacity-50 flex items-center gap-1.5">
                {wordsmith.isPending ? (
                  <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : null}
                {wordsmith.isPending ? 'Polishing...' : 'AI Wordsmith'}
              </button>
            )}
            <span className="text-xs text-gray-400">
              {channel === 'gmail' && contact.email}
              {channel === 'linkedin' && 'Copies message, opens LinkedIn'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={handleClose} className="px-3 py-1.5 text-xs text-gray-600 hover:text-gray-800">Cancel</button>
            {channel === 'gmail' && (
              <button onClick={() => send.mutate('draft')} disabled={!canSend || isBusy}
                className="px-3 py-1.5 text-xs bg-gray-600 text-white rounded hover:bg-gray-500 disabled:opacity-50">
                {send.isPending ? '...' : isEdit ? 'Update Draft' : 'Save Draft'}
              </button>
            )}
            <button onClick={() => send.mutate('send')} disabled={!canSend || isBusy}
              className={`px-4 py-1.5 text-xs text-white rounded disabled:opacity-50 ${channel === 'gmail' ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-700 hover:bg-blue-800'}`}>
              {send.isPending ? 'Sending...' : channel === 'gmail' ? 'Send Email' : 'Send via LinkedIn'}
            </button>
          </div>
        </div>

        {/* Error display */}
        {anyError && (
          <div className="px-4 pb-3 shrink-0">
            <p className="text-xs text-red-600 bg-red-50 rounded px-3 py-2">
              {(anyError as any)?.message || 'Something went wrong'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
