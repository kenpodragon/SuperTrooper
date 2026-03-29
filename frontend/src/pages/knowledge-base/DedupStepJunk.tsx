import React, { useState, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';

interface JunkItem {
  id: number;
  content_preview: string;
  reason: string;
  action?: 'delete' | 'split' | 'reclassify';
  extracted_skills?: string[];
  extracted_certs?: string[];
  suggested_reclassify?: { target_table: string; career_history_id?: number };
}

interface Props {
  entityType: string;
  items: JunkItem[];
  onComplete: () => void;
}

type ItemDecision = 'delete' | 'split' | 'reclassify' | 'keep';

export default function DedupStepJunk({ entityType, items, onComplete }: Props) {
  const [decisions, setDecisions] = useState<Record<number, ItemDecision>>(() => {
    const initial: Record<number, ItemDecision> = {};
    items.forEach((item) => {
      // Default to the suggested action, or delete
      initial[item.id] = item.action || 'delete';
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
      const reclassifications: any[] = [];
      const splits: any[] = [];

      for (const item of items) {
        const decision = decisions[item.id] ?? 'delete';
        if (decision === 'delete') {
          deletes.push(item.id);
        } else if (decision === 'split') {
          splits.push({
            id: item.id,
            extracted_skills: item.extracted_skills,
            extracted_certs: item.extracted_certs,
          });
        } else if (decision === 'reclassify' && item.suggested_reclassify) {
          reclassifications.push({ id: item.id, ...item.suggested_reclassify });
        }
        // keep = no action
      }

      await api.post('/kb/dedup/apply', {
        entity_type: entityType, merges: [], deletes, reclassifications, splits,
      });
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
          Cleanup Items ({items.length})
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
        const hasSplit = !!(item.extracted_skills?.length || item.extracted_certs?.length);
        const hasReclassify = !!item.suggested_reclassify;
        const extractedItems = item.extracted_skills || item.extracted_certs || [];

        return (
          <div
            key={item.id}
            className="bg-gray-800 rounded-lg border border-gray-700 p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-gray-200 text-sm">{item.content_preview}</p>
                <p className="text-gray-400 text-xs mt-1">{item.reason}</p>

                {/* Show extracted items for split actions */}
                {hasSplit && decision === 'split' && (
                  <div className="mt-2 p-2 bg-green-900/20 border border-green-800/30 rounded">
                    <p className="text-green-400 text-xs font-semibold mb-1">
                      Will split into {extractedItems.length} individual entries:
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {extractedItems.map((name, i) => (
                        <span key={i} className="px-2 py-0.5 bg-green-800/40 text-green-300 text-xs rounded">
                          {name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Show reclassify target */}
                {hasReclassify && decision === 'reclassify' && (
                  <p className="text-blue-400 text-xs mt-2">
                    Will move to <span className="font-medium">{item.suggested_reclassify!.target_table}</span>
                  </p>
                )}
              </div>

              <div className="flex gap-2 shrink-0">
                {hasSplit && (
                  <button
                    onClick={() => setDecision(item.id, 'split')}
                    className={`px-3 py-1 rounded text-sm transition-colors ${
                      decision === 'split'
                        ? 'bg-green-700 border border-green-500 text-white'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    Split ({extractedItems.length})
                  </button>
                )}
                {hasReclassify && (
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
                  onClick={() => setDecision(item.id, 'delete')}
                  className={`px-3 py-1 rounded text-sm transition-colors ${
                    decision === 'delete'
                      ? 'bg-red-700 border border-red-500 text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  Delete
                </button>
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
