import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import AiInstructionModal from './AiInstructionModal';
import { HIGHLIGHTS_ID } from './MoveCloneModal';

interface Synopsis {
  id: number;
  career_history_id: number;
  text: string;
  type: string;
  display_order: number;
  is_default?: boolean;
}

interface SynopsisEditorProps {
  jobId: number;
  aiEnabled: boolean;
  label?: string;
}

export default function SynopsisEditor({ jobId, aiEnabled, label }: SynopsisEditorProps) {
  const [activeTab, setActiveTab] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState('');
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [showWordsmithModal, setShowWordsmithModal] = useState(false);
  const [inlineAiLoading, setInlineAiLoading] = useState(false);
  const [showInlineAiInput, setShowInlineAiInput] = useState(false);
  const [inlineAiInstruction, setInlineAiInstruction] = useState('');
  const queryClient = useQueryClient();

  const isHighlights = jobId === HIGHLIGHTS_ID;
  const chIdParam = isHighlights ? 'none' : String(jobId);
  const chIdPayload = isHighlights ? null : jobId;

  const { data: synopses = [], isLoading } = useQuery<Synopsis[]>({
    queryKey: ['synopses', jobId],
    queryFn: () => api.get(`/bullets?career_history_id=${chIdParam}&type=synopsis`),
  });

  const active = synopses.find((s) => s.id === activeTab) || synopses[0] || null;

  const createMutation = useMutation({
    mutationFn: () =>
      api.post('/bullets', {
        career_history_id: chIdPayload,
        type: 'synopsis',
        text: '',
        display_order: 0,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['synopses', jobId] }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      api.patch(`/bullets/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['synopses', jobId] });
      setEditing(false);
    },
  });

  const generateMutation = useMutation({
    mutationFn: (prompt: string) =>
      api.post('/bullets/generate', {
        career_history_id: chIdPayload,
        type: 'synopsis',
        instruction: prompt,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['synopses', jobId] });
      setShowGenerateModal(false);
    },
  });

  const wordsmithWithInstructionMutation = useMutation({
    mutationFn: ({ id, instruction }: { id: number; instruction: string }) =>
      api.post(`/bullets/${id}/wordsmith`, { instruction }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['synopses', jobId] });
      setShowWordsmithModal(false);
    },
  });

  const handleSetDefault = (id: number) => {
    const currentDefault = synopses.find((s) => s.is_default);
    if (currentDefault && currentDefault.id !== id) {
      updateMutation.mutate({ id: currentDefault.id, data: { is_default: false } });
    }
    updateMutation.mutate({ id, data: { is_default: true } });
  };

  const startEdit = () => {
    if (active) {
      setEditText(active.text);
      setEditing(true);
    }
  };

  const saveEdit = () => {
    if (active) {
      updateMutation.mutate({ id: active.id, data: { text: editText } });
    }
  };

  const inlineAiImprove = async (instruction: string) => {
    if (!active) return;
    setInlineAiLoading(true);
    try {
      const result = await api.post<{ updated?: string; text?: string }>(`/bullets/${active.id}/wordsmith`, { instruction });
      const improved = result.updated || result.text || '';
      if (improved) setEditText(improved);
    } catch { /* silent */ }
    finally { setInlineAiLoading(false); }
  };

  if (isLoading) {
    return <div className="p-4 text-gray-500 text-sm">Loading synopses...</div>;
  }

  return (
    <div className="border-b border-blue-800 bg-blue-900/30">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-blue-800/50">
        <span className="text-xs font-semibold text-blue-400 uppercase tracking-wider">
          {label || (isHighlights ? 'Professional Summary' : 'Synopsis')}
        </span>
        <span className="bg-blue-500/20 text-blue-300 text-xs px-1.5 py-0.5 rounded-full">
          {synopses.length}
        </span>
        <div className="flex-1" />
        {aiEnabled && (
          <button
            onClick={() => setShowGenerateModal(true)}
            className="text-xs px-2 py-1 bg-purple-600/30 text-purple-300 hover:bg-purple-600/50 rounded"
          >
            Generate
          </button>
        )}
        <button
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isPending}
          className="text-xs px-2 py-1 bg-blue-600/30 text-blue-300 hover:bg-blue-600/50 rounded"
        >
          + New Variant
        </button>
      </div>

      {/* Generate Modal */}
      <AiInstructionModal
        isOpen={showGenerateModal}
        onClose={() => setShowGenerateModal(false)}
        onSubmit={(instruction) => generateMutation.mutate(instruction)}
        title="Generate Synopsis"
        placeholder="Describe the synopsis you want generated..."
        loading={generateMutation.isPending}
      />

      {/* Wordsmith Modal */}
      <AiInstructionModal
        isOpen={showWordsmithModal}
        onClose={() => setShowWordsmithModal(false)}
        onSubmit={(instruction) => {
          if (active) wordsmithWithInstructionMutation.mutate({ id: active.id, instruction });
        }}
        title="Wordsmith Synopsis"
        placeholder="How should this synopsis be reworded?"
        loading={wordsmithWithInstructionMutation.isPending}
      />

      {synopses.length === 0 ? (
        <div className="px-4 py-6 text-center text-gray-500 text-sm">
          No synopsis. Click + New Variant to add one.
        </div>
      ) : (
        <>
          {/* Variant tabs */}
          <div className="flex gap-1 px-4 pt-2 overflow-x-auto">
            {synopses.map((s, i) => (
              <button
                key={s.id}
                onClick={() => { setActiveTab(s.id); setEditing(false); }}
                className={`text-xs px-3 py-1 rounded-t whitespace-nowrap ${
                  active?.id === s.id
                    ? 'bg-gray-800 text-blue-300 border border-b-0 border-blue-800'
                    : 'bg-gray-900/50 text-gray-500 hover:text-gray-300'
                }`}
              >
                {s.is_default && <span className="mr-1 text-yellow-400">★</span>}
                Variant {i + 1}
              </button>
            ))}
          </div>

          {/* Active variant content */}
          {active && (
            <div className="px-4 py-3">
              {editing ? (
                <div className="space-y-2">
                  <textarea
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    rows={4}
                    className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-gray-100 focus:border-blue-400 focus:outline-none"
                  />
                  <div className="flex gap-2 items-center">
                    <button
                      onClick={saveEdit}
                      disabled={updateMutation.isPending}
                      className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded disabled:opacity-50"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditing(false)}
                      className="px-3 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded"
                    >
                      Cancel
                    </button>
                    {aiEnabled && (
                      <>
                        <div className="w-px h-4 bg-gray-600 mx-1" />
                        <button
                          onClick={() => inlineAiImprove('Polish this synopsis. Make it compelling and concise.')}
                          disabled={inlineAiLoading || !editText.trim()}
                          className="px-3 py-1 bg-purple-600/30 hover:bg-purple-600/50 text-purple-300 text-xs rounded disabled:opacity-50 flex items-center gap-1"
                        >
                          {inlineAiLoading ? '✨ Improving...' : '✨ AI Improve'}
                        </button>
                        <button
                          onClick={() => setShowInlineAiInput(!showInlineAiInput)}
                          disabled={inlineAiLoading || !editText.trim()}
                          className={`px-2 py-1 text-xs rounded disabled:opacity-50 ${showInlineAiInput ? 'bg-purple-600/50 text-purple-200' : 'bg-purple-600/20 hover:bg-purple-600/40 text-purple-300'}`}
                          title="Custom AI instruction"
                        >
                          🤖
                        </button>
                      </>
                    )}
                  </div>
                  {showInlineAiInput && aiEnabled && (
                    <div className="flex gap-2 items-center mt-1">
                      <input
                        value={inlineAiInstruction}
                        onChange={(e) => setInlineAiInstruction(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && inlineAiInstruction.trim()) {
                            inlineAiImprove(inlineAiInstruction.trim());
                            setShowInlineAiInput(false);
                            setInlineAiInstruction('');
                          }
                          if (e.key === 'Escape') { setShowInlineAiInput(false); setInlineAiInstruction(''); }
                        }}
                        placeholder="e.g., focus on leadership impact, add metrics..."
                        autoFocus
                        className="flex-1 bg-gray-900 border border-purple-600/50 rounded px-2 py-1 text-xs text-gray-100 placeholder-gray-500 focus:border-purple-400 focus:outline-none"
                      />
                      <button
                        onClick={() => {
                          if (inlineAiInstruction.trim()) {
                            inlineAiImprove(inlineAiInstruction.trim());
                            setShowInlineAiInput(false);
                            setInlineAiInstruction('');
                          }
                        }}
                        disabled={!inlineAiInstruction.trim()}
                        className="px-2 py-1 bg-purple-600 hover:bg-purple-500 text-white text-xs rounded disabled:opacity-50"
                      >
                        Go
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <div
                    onClick={startEdit}
                    className="text-sm text-gray-200 whitespace-pre-wrap cursor-pointer hover:bg-gray-800/50 rounded p-2 min-h-[40px]"
                  >
                    {active.text || <span className="text-gray-500 italic">Click to edit...</span>}
                  </div>
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={startEdit}
                      className="text-xs text-blue-400 hover:text-blue-300"
                    >
                      ✏️ Edit
                    </button>
                    {aiEnabled && (
                      <button
                        onClick={() => setShowWordsmithModal(true)}
                        disabled={wordsmithWithInstructionMutation.isPending}
                        className="text-xs text-purple-400 hover:text-purple-300 disabled:opacity-50"
                      >
                        ✨ Wordsmith
                      </button>
                    )}
                    <button
                      onClick={() => handleSetDefault(active.id)}
                      className={`text-xs ${
                        active.is_default
                          ? 'text-yellow-400'
                          : 'text-gray-500 hover:text-yellow-400'
                      }`}
                    >
                      ★ {active.is_default ? 'Default' : 'Set Default'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
