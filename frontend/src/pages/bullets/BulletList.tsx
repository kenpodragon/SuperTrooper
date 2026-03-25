import { useState, useMemo, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import BulletCard, { type Bullet } from './BulletCard';
import AiInstructionModal from './AiInstructionModal';

interface BulletListProps {
  jobId: number;
  aiEnabled: boolean;
  onAiToggle: (enabled: boolean) => void;
}

type SortMode = 'order' | 'strength' | 'newest';
type TypeFilter = 'all' | 'achievement' | 'leadership' | 'technical';

const strengthOrder: Record<string, number> = { strong: 0, moderate: 1, weak: 2 };

export default function BulletList({ jobId, aiEnabled, onAiToggle }: BulletListProps) {
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all');
  const [sortMode, setSortMode] = useState<SortMode>('order');
  const [dragId, setDragId] = useState<number | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const queryClient = useQueryClient();

  const { data: bullets = [], isLoading } = useQuery<Bullet[]>({
    queryKey: ['bullets', jobId],
    queryFn: () => api.get(`/bullets?career_history_id=${jobId}&type=!synopsis`),
  });

  const { data: staleData } = useQuery<{ count: number }>({
    queryKey: ['stale-count', jobId],
    queryFn: () => api.get(`/bullets/stale-count?career_history_id=${jobId}`),
  });

  const staleCount = staleData?.count ?? 0;

  const analyzeMutation = useMutation({
    mutationFn: () => api.post('/bullets/analyze', { career_history_id: jobId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bullets', jobId] });
      queryClient.invalidateQueries({ queryKey: ['stale-count', jobId] });
    },
  });

  const addMutation = useMutation({
    mutationFn: () =>
      api.post('/bullets', {
        career_history_id: jobId,
        type: 'achievement',
        text: '',
        display_order: bullets.length,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['bullets', jobId] }),
  });

  const generateMutation = useMutation({
    mutationFn: (instruction: string) =>
      api.post('/bullets/generate', {
        career_history_id: jobId,
        type: 'achievement',
        instruction,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bullets', jobId] });
      setShowGenerateModal(false);
    },
  });

  const reorderMutation = useMutation({
    mutationFn: (items: Array<{ id: number; order: number }>) =>
      api.post('/bullets/reorder', { career_history_id: jobId, items }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['bullets', jobId] }),
  });

  const refetch = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['bullets', jobId] });
    queryClient.invalidateQueries({ queryKey: ['stale-count', jobId] });
  }, [queryClient, jobId]);

  // Strength counts
  const counts = useMemo(() => {
    const c = { strong: 0, moderate: 0, weak: 0 };
    for (const b of bullets) {
      const s = b.ai_analysis?.strength;
      if (s && s in c) c[s as keyof typeof c]++;
    }
    return c;
  }, [bullets]);

  // Filtered + sorted
  const filtered = useMemo(() => {
    let list = [...bullets];

    if (search) {
      const q = search.toLowerCase();
      list = list.filter((b) => b.text.toLowerCase().includes(q));
    }

    if (typeFilter !== 'all') {
      list = list.filter((b) => b.type === typeFilter);
    }

    switch (sortMode) {
      case 'strength':
        list.sort(
          (a, b) =>
            (strengthOrder[a.ai_analysis?.strength || 'weak'] ?? 3) -
            (strengthOrder[b.ai_analysis?.strength || 'weak'] ?? 3)
        );
        break;
      case 'newest':
        list.sort(
          (a, b) =>
            new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime()
        );
        break;
      default:
        list.sort((a, b) => a.display_order - b.display_order);
    }

    return list;
  }, [bullets, search, typeFilter, sortMode]);

  // Drag handlers
  const handleDragStart = (e: React.DragEvent, id: number) => {
    setDragId(id);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e: React.DragEvent, targetId: number) => {
    e.preventDefault();
    if (dragId === null || dragId === targetId) return;

    const ordered = [...bullets].sort((a, b) => a.display_order - b.display_order);
    const fromIdx = ordered.findIndex((b) => b.id === dragId);
    const toIdx = ordered.findIndex((b) => b.id === targetId);
    if (fromIdx === -1 || toIdx === -1) return;

    const [moved] = ordered.splice(fromIdx, 1);
    ordered.splice(toIdx, 0, moved);

    const items = ordered.map((b, i) => ({ id: b.id, order: i }));
    reorderMutation.mutate(items);
    setDragId(null);
  };

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-700">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Bullets
        </span>
        {counts.strong > 0 && (
          <span className="text-[10px] px-1.5 py-0.5 bg-green-500/20 text-green-300 rounded-full">
            {counts.strong}
          </span>
        )}
        {counts.moderate > 0 && (
          <span className="text-[10px] px-1.5 py-0.5 bg-yellow-500/20 text-yellow-300 rounded-full">
            {counts.moderate}
          </span>
        )}
        {counts.weak > 0 && (
          <span className="text-[10px] px-1.5 py-0.5 bg-red-500/20 text-red-300 rounded-full">
            {counts.weak}
          </span>
        )}

        <div className="flex-1" />

        {/* AI toggle */}
        <label className="flex items-center gap-1.5 cursor-pointer" title="Toggle AI features">
          <span className="text-[10px] text-gray-500">AI</span>
          <div
            onClick={() => onAiToggle(!aiEnabled)}
            className={`w-7 h-4 rounded-full relative transition-colors cursor-pointer ${
              aiEnabled ? 'bg-purple-600' : 'bg-gray-600'
            }`}
          >
            <div
              className={`w-3 h-3 rounded-full bg-white absolute top-0.5 transition-transform ${
                aiEnabled ? 'translate-x-3.5' : 'translate-x-0.5'
              }`}
            />
          </div>
        </label>

        <button
          onClick={() => analyzeMutation.mutate()}
          disabled={analyzeMutation.isPending || staleCount === 0}
          className="text-xs px-2 py-1 bg-purple-600/30 text-purple-300 hover:bg-purple-600/50 rounded disabled:opacity-30"
          title={staleCount > 0 ? `${staleCount} stale bullets` : 'All bullets analyzed'}
        >
          {analyzeMutation.isPending ? 'Analyzing...' : `Analyze All${staleCount > 0 ? ` (${staleCount})` : ''}`}
        </button>

        <button
          onClick={() => {
            if (aiEnabled) setShowGenerateModal(true);
            else addMutation.mutate();
          }}
          disabled={addMutation.isPending}
          className="text-xs px-2 py-1 bg-blue-600/30 text-blue-300 hover:bg-blue-600/50 rounded"
        >
          + Add Bullet
        </button>
      </div>

      {/* Filter toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-700/50">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search bullets..."
          className="flex-1 max-w-[240px] bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-100 focus:border-blue-400 focus:outline-none"
        />
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as TypeFilter)}
          className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-300"
        >
          <option value="all">All Types</option>
          <option value="achievement">Achievement</option>
          <option value="leadership">Leadership</option>
          <option value="technical">Technical</option>
        </select>
        <select
          value={sortMode}
          onChange={(e) => setSortMode(e.target.value as SortMode)}
          className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-300"
        >
          <option value="order">Sort: Order</option>
          <option value="strength">Sort: Strength</option>
          <option value="newest">Sort: Newest</option>
        </select>
      </div>

      {/* Bullet cards */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {isLoading ? (
          <div className="text-gray-500 text-sm text-center py-8">Loading bullets...</div>
        ) : filtered.length === 0 ? (
          <div className="text-gray-500 text-sm text-center py-8">
            {bullets.length === 0
              ? 'No bullets yet. Click + Add Bullet to get started.'
              : 'No bullets match the current filter.'}
          </div>
        ) : (
          filtered.map((bullet) => (
            <BulletCard
              key={bullet.id}
              bullet={bullet}
              aiEnabled={aiEnabled}
              onRefresh={refetch}
              onDragStart={handleDragStart}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
            />
          ))
        )}
      </div>

      {/* AI Generate Modal */}
      <AiInstructionModal
        isOpen={showGenerateModal}
        onClose={() => setShowGenerateModal(false)}
        onSubmit={(instruction) => generateMutation.mutate(instruction)}
        title="Generate New Bullet"
        placeholder="Create a bullet about cloud migration savings..."
        loading={generateMutation.isPending}
      />
    </div>
  );
}
