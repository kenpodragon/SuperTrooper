import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';

interface ReviewGroup {
  group_id: string;
  winner_id: number;
  members: any[];
  similarity_score: number;
  reason: string;
}

interface Props {
  entityType: string;
  groups: ReviewGroup[];
  onComplete: () => void;
}

type GroupDecision =
  | { type: 'merge'; winner_id: number }
  | { type: 'not_duplicates' }
  | { type: 'delete_both' };

export default function DedupStepReview({ entityType, groups, onComplete }: Props) {
  const [decisions, setDecisions] = useState<Record<string, GroupDecision>>({});

  const allDecided = groups.length > 0 && groups.every((g) => decisions[g.group_id] !== undefined);

  const applyMutation = useMutation({
    mutationFn: async () => {
      const merges: any[] = [];
      const deletes: number[] = [];

      for (const group of groups) {
        const decision = decisions[group.group_id];
        if (!decision) continue;
        if (decision.type === 'merge') {
          const winnerId = decision.winner_id;
          merges.push({
            winner_id: winnerId,
            loser_ids: group.members.filter((m: any) => m.id !== winnerId).map((m: any) => m.id),
          });
        } else if (decision.type === 'delete_both') {
          group.members.forEach((m: any) => deletes.push(m.id));
        }
        // not_duplicates = no action
      }

      await api.post('/kb/dedup/apply', { entity_type: entityType, merges, deletes, reclassifications: [] });
    },
    onSuccess: onComplete,
  });

  const setWinner = (groupId: string, winnerId: number) => {
    setDecisions((prev) => ({ ...prev, [groupId]: { type: 'merge', winner_id: winnerId } }));
  };

  const setNotDuplicates = (groupId: string) => {
    setDecisions((prev) => ({ ...prev, [groupId]: { type: 'not_duplicates' } }));
  };

  const setDeleteBoth = (groupId: string) => {
    setDecisions((prev) => ({ ...prev, [groupId]: { type: 'delete_both' } }));
  };

  if (groups.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        No review groups.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-yellow-400 font-semibold text-lg">
          Review Groups ({groups.length})
        </h3>
        <button
          onClick={() => applyMutation.mutate()}
          disabled={!allDecided || applyMutation.isPending}
          className="px-6 py-2 bg-yellow-600 hover:bg-yellow-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-white font-medium transition-colors"
        >
          {applyMutation.isPending ? 'Applying...' : 'Apply Decisions'}
        </button>
      </div>

      {!allDecided && (
        <p className="text-yellow-400/70 text-sm">
          All groups need a decision before applying.
        </p>
      )}

      {applyMutation.isError && (
        <div className="p-3 bg-red-900/40 border border-red-700 rounded text-red-300 text-sm">
          Error applying decisions. Please try again.
        </div>
      )}

      {groups.map((group) => {
        const decision = decisions[group.group_id];
        const mergeWinnerId = decision?.type === 'merge' ? decision.winner_id : null;

        return (
          <div
            key={group.group_id}
            className="bg-gray-800 rounded-lg border border-gray-700 p-4"
          >
            <div className="flex items-center justify-between mb-3">
              <div>
                <span className="text-yellow-400 text-sm font-medium">
                  Similarity: {(group.similarity_score * 100).toFixed(0)}%
                </span>
                <span className="text-gray-400 text-xs ml-3">{group.reason}</span>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setNotDuplicates(group.group_id)}
                  className={`px-3 py-1 rounded text-sm transition-colors ${
                    decision?.type === 'not_duplicates'
                      ? 'bg-blue-700 border border-blue-500 text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  Not Duplicates
                </button>
                <button
                  onClick={() => setDeleteBoth(group.group_id)}
                  className={`px-3 py-1 rounded text-sm transition-colors ${
                    decision?.type === 'delete_both'
                      ? 'bg-red-700 border border-red-500 text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  Delete Both
                </button>
              </div>
            </div>

            <p className="text-gray-400 text-xs mb-3">
              Click a card to select it as the winner (merge into this one):
            </p>

            <div className="grid grid-cols-2 gap-3">
              {group.members.map((member: any) => {
                const isSelected = mergeWinnerId === member.id;
                return (
                  <button
                    key={member.id}
                    onClick={() => setWinner(group.group_id, member.id)}
                    className={`p-3 rounded-lg text-left transition-colors border ${
                      isSelected
                        ? 'bg-gray-700 border-green-500 text-white'
                        : 'bg-gray-750 border-gray-600 text-gray-300 hover:bg-gray-700 hover:border-gray-500'
                    }`}
                  >
                    <div className="font-medium text-sm truncate">
                      {member.name || member.content_preview || `#${member.id}`}
                    </div>
                    {member.content_preview && member.name && (
                      <div className="text-gray-400 text-xs mt-1 truncate">
                        {member.content_preview}
                      </div>
                    )}
                    {isSelected && (
                      <div className="text-green-400 text-xs mt-1 font-medium">Winner</div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
