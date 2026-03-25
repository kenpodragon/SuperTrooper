import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import AiInstructionModal from './AiInstructionModal';
import DuplicateWarning from './DuplicateWarning';

export interface Bullet {
  id: number;
  career_history_id: number;
  text: string;
  type: string;
  tags?: string[];
  display_order: number;
  ai_analysis?: {
    strength: 'strong' | 'moderate' | 'weak';
    star_check?: Record<string, boolean>;
    feedback?: string;
    suggested_skills?: string[];
    content_hash_at_analysis?: string;
  };
  ai_analyzed_at?: string;
  content_hash?: string;
  is_default?: boolean;
  updated_at?: string;
  created_at?: string;
}

interface DuplicateMatch {
  id: number;
  text: string;
  similarity: number;
  employer?: string;
  title?: string;
}

interface DuplicateCheckResult {
  has_duplicates: boolean;
  within_job: DuplicateMatch[];
  cross_job: DuplicateMatch[];
  summary?: string;
}

interface BulletCardProps {
  bullet: Bullet;
  aiEnabled: boolean;
  onRefresh: () => void;
  onDragStart: (e: React.DragEvent, id: number) => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent, id: number) => void;
}

const strengthColors: Record<string, string> = {
  strong: 'bg-green-500/20 text-green-300',
  moderate: 'bg-yellow-500/20 text-yellow-300',
  weak: 'bg-red-500/20 text-red-300',
};

export default function BulletCard({
  bullet,
  aiEnabled,
  onRefresh,
  onDragStart,
  onDragOver,
  onDrop,
}: BulletCardProps) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState('');
  const [aiModal, setAiModal] = useState<{ open: boolean; action: string; title: string; placeholder: string }>({
    open: false, action: '', title: '', placeholder: '',
  });
  const [dupWarning, setDupWarning] = useState<{
    open: boolean; withinJob: DuplicateMatch[]; crossJob: DuplicateMatch[]; pendingText?: string;
  }>({ open: false, withinJob: [], crossJob: [] });
  const queryClient = useQueryClient();

  const isStale =
    bullet.ai_analysis &&
    bullet.content_hash &&
    bullet.content_hash !== bullet.ai_analysis.content_hash_at_analysis;

  const checkDuplicates = async (text: string) => {
    try {
      const result = await api.post<DuplicateCheckResult>(
        `/bullets/${bullet.id}/check-duplicates`,
        {}
      );
      if (result.has_duplicates && (result.within_job?.length > 0 || result.cross_job?.length > 0)) {
        setDupWarning({
          open: true,
          withinJob: result.within_job || [],
          crossJob: result.cross_job || [],
          pendingText: text,
        });
        return;
      }
    } catch {
      // Duplicate check is optional
    }
    onRefresh();
  };

  const updateMutation = useMutation({
    mutationFn: (text: string) => api.patch(`/bullets/${bullet.id}`, { text }),
    onSuccess: async (_data, text) => {
      setEditing(false);
      await checkDuplicates(text);
    },
  });

  const cloneMutation = useMutation({
    mutationFn: () => api.post(`/bullets/${bullet.id}/clone`, {}),
    onSuccess: () => onRefresh(),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.del(`/bullets/${bullet.id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bullets'] });
      onRefresh();
    },
  });

  const wordsmithMutation = useMutation({
    mutationFn: (instruction: string) => api.post(`/bullets/${bullet.id}/wordsmith`, { instruction }),
    onSuccess: () => { setAiModal((s) => ({ ...s, open: false })); onRefresh(); },
  });

  const variantMutation = useMutation({
    mutationFn: (instruction: string) => api.post(`/bullets/${bullet.id}/variant`, { instruction }),
    onSuccess: () => { setAiModal((s) => ({ ...s, open: false })); onRefresh(); },
  });

  const strengthenMutation = useMutation({
    mutationFn: (instruction: string) => api.post(`/bullets/${bullet.id}/strengthen`, { instruction }),
    onSuccess: () => { setAiModal((s) => ({ ...s, open: false })); onRefresh(); },
  });

  const openAiModal = (action: string, title: string, placeholder: string) => {
    setAiModal({ open: true, action, title, placeholder });
  };

  const handleAiSubmit = (instruction: string) => {
    if (aiModal.action === 'wordsmith') wordsmithMutation.mutate(instruction);
    else if (aiModal.action === 'variant') variantMutation.mutate(instruction);
    else if (aiModal.action === 'strengthen') strengthenMutation.mutate(instruction);
  };

  const aiLoading = wordsmithMutation.isPending || variantMutation.isPending || strengthenMutation.isPending;

  const startEdit = () => {
    setEditText(bullet.text);
    setEditing(true);
  };

  const handleDelete = () => {
    if (window.confirm('Delete this bullet?')) {
      deleteMutation.mutate();
    }
  };

  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, bullet.id)}
      onDragOver={onDragOver}
      onDrop={(e) => onDrop(e, bullet.id)}
      className="bg-gray-800 border border-gray-700 rounded-lg p-3 hover:border-gray-600 transition-colors"
    >
      <div className="flex gap-2">
        {/* Drag handle */}
        <span className="text-gray-600 cursor-grab select-none mt-0.5" title="Drag to reorder">
          ⠿
        </span>

        <div className="flex-1 min-w-0">
          {editing ? (
            <div className="space-y-2">
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                rows={3}
                className="w-full bg-gray-900 border border-gray-600 rounded px-2 py-1 text-sm text-gray-100 focus:border-blue-400 focus:outline-none"
                autoFocus
              />
              <div className="flex gap-2">
                <button
                  onClick={() => updateMutation.mutate(editText)}
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
              </div>
            </div>
          ) : (
            <>
              {/* Bullet text */}
              <p className="text-sm text-gray-200 leading-relaxed">{bullet.text}</p>

              {/* Tags */}
              {bullet.tags && bullet.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {bullet.tags.map((tag) => (
                    <span
                      key={tag}
                      className="text-[10px] px-1.5 py-0.5 bg-blue-500/20 text-blue-300 rounded"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              {/* AI feedback for moderate/weak */}
              {bullet.ai_analysis?.feedback &&
                bullet.ai_analysis.strength !== 'strong' && (
                  <p className="text-xs text-yellow-400/80 italic mt-1.5">
                    {bullet.ai_analysis.feedback}
                  </p>
                )}
            </>
          )}
        </div>

        {/* Right side: badges + actions */}
        <div className="flex flex-col items-end gap-1 shrink-0">
          {/* Strength badge */}
          <div className="flex items-center gap-1">
            {isStale && (
              <span className="text-yellow-500 text-xs" title="Analysis is stale">
                ⟳
              </span>
            )}
            {bullet.ai_analysis?.strength && (
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded ${
                  strengthColors[bullet.ai_analysis.strength] || ''
                }`}
              >
                {bullet.ai_analysis.strength}
              </span>
            )}
          </div>

          {/* Action buttons */}
          {!editing && (
            <div className="flex flex-wrap gap-1 justify-end mt-1">
              <button
                onClick={startEdit}
                className="text-xs text-gray-400 hover:text-blue-300"
                title="Edit"
              >
                ✏️
              </button>
              <button
                onClick={() => cloneMutation.mutate()}
                disabled={cloneMutation.isPending}
                className="text-xs text-gray-400 hover:text-blue-300 disabled:opacity-50"
                title="Clone"
              >
                📋
              </button>
              <button
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
                className="text-xs text-gray-400 hover:text-red-400 disabled:opacity-50"
                title="Delete"
              >
                🗑
              </button>
              {aiEnabled && (
                <>
                  <button
                    onClick={() => openAiModal('wordsmith', 'Wordsmith', 'How should this bullet be reworded?')}
                    disabled={wordsmithMutation.isPending}
                    className="text-xs text-gray-400 hover:text-purple-300 disabled:opacity-50"
                    title="Wordsmith"
                  >
                    🤖
                  </button>
                  <button
                    onClick={() => openAiModal('variant', 'Create Variant', 'What angle should this variant take?')}
                    disabled={variantMutation.isPending}
                    className="text-xs text-gray-400 hover:text-purple-300 disabled:opacity-50"
                    title="Variant"
                  >
                    🔀
                  </button>
                  {bullet.ai_analysis?.strength === 'weak' && (
                    <button
                      onClick={() => openAiModal('strengthen', 'Strengthen Bullet', 'What metrics or context should be added?')}
                      disabled={strengthenMutation.isPending}
                      className="text-xs text-gray-400 hover:text-green-300 disabled:opacity-50"
                      title="Strengthen"
                    >
                      ✨
                    </button>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* AI Instruction Modal */}
      <AiInstructionModal
        isOpen={aiModal.open}
        onClose={() => setAiModal((s) => ({ ...s, open: false }))}
        onSubmit={handleAiSubmit}
        title={aiModal.title}
        placeholder={aiModal.placeholder}
        loading={aiLoading}
      />

      {/* Duplicate Warning Modal */}
      <DuplicateWarning
        isOpen={dupWarning.open}
        onClose={() => setDupWarning((s) => ({ ...s, open: false }))}
        onContinue={() => {
          setDupWarning((s) => ({ ...s, open: false }));
          onRefresh();
        }}
        withinJob={dupWarning.withinJob}
        crossJob={dupWarning.crossJob}
      />
    </div>
  );
}
