import React, { useState, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';

interface JunkItem {
  id: number;
  content_preview: string;
  reason: string;
  suggested_reclassify?: { target_table: string; career_history_id?: number };
}

interface Props {
  entityType: string;
  items: JunkItem[];
  onComplete: () => void;
}

type ItemDecision = 'delete' | 'reclassify' | 'keep';

export default function DedupStepJunk({ entityType, items, onComplete }: Props) {
  const [decisions, setDecisions] = useState<Record<number, ItemDecision>>(() => {
    const initial: Record<number, ItemDecision> = {};
    items.forEach((item) => {
      initial[item.id] = 'delete';
    });
    return initial;
  });

  useEffect(() => {
    if (items.length === 0) {
      onComplete();
    }
  }, [items, onComplete]);

  const applyMutation = useMutation({
    mutationFn: async () => {
      const deletes: number[] = [];
      const reclassify: any[] = [];

      for (const item of items) {
        const decision = decisions[item.id] ?? 'delete';
        if (decision === 'delete') {
          deletes.push(item.id);
        } else if (decision === 'reclassify' && item.suggested_reclassify) {
          reclassify.push({ id: item.id, ...item.suggested_reclassify });
        }
        // keep = no action
      }

      await api.post('/kb/dedup/apply', { entity_type: entityType, merges: [], deletes, reclassify });
    },
    onSuccess: onComplete,
  });

  const setDecision = (id: number, decision: ItemDecision) => {
    setDecisions((prev) => ({ ...prev, [id]: decision }));
  };

  if (items.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        No junk items found.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-red-400 font-semibold text-lg">
          Junk Items ({items.length})
        </h3>
        <button
          onClick={() => applyMutation.mutate()}
          disabled={applyMutation.isPending}
          className="px-6 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-lg text-white font-medium transition-colors"
        >
          {applyMutation.isPending ? 'Applying...' : 'Confirm'}
        </button>
      </div>

      {applyMutation.isError && (
        <div className="p-3 bg-red-900/40 border border-red-700 rounded text-red-300 text-sm">
          Error applying changes. Please try again.
        </div>
      )}

      {items.map((item) => {
        const decision = decisions[item.id] ?? 'delete';

        return (
          <div
            key={item.id}
            className="bg-gray-800 rounded-lg border border-gray-700 p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-gray-200 text-sm truncate">
                  {item.content_preview}
                </p>
                <p className="text-gray-400 text-xs mt-1">{item.reason}</p>
                {item.suggested_reclassify && (
                  <p className="text-blue-400 text-xs mt-1">
                    Suggested: move to{' '}
                    <span className="font-medium">{item.suggested_reclassify.target_table}</span>
                  </p>
                )}
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => setDecision(item.id, 'delete')}
                  className={`px-3 py-1 rounded text-sm transition-colors ${
                    decision === 'delete'
                      ? 'bg-red-700 border border-red-500 text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  Delete
                </button>
                {item.suggested_reclassify && (
                  <button
                    onClick={() => setDecision(item.id, 'reclassify')}
                    className={`px-3 py-1 rounded text-sm transition-colors ${
                      decision === 'reclassify'
                        ? 'bg-blue-700 border border-blue-500 text-white'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    Reclassify
                  </button>
                )}
                <button
                  onClick={() => setDecision(item.id, 'keep')}
                  className={`px-3 py-1 rounded text-sm transition-colors ${
                    decision === 'keep'
                      ? 'bg-gray-500 border border-gray-400 text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  Keep
                </button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
