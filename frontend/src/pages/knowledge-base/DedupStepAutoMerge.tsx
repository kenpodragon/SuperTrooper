import React, { useState, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';

interface MergeGroup {
  group_id: string;
  winner_id?: number;
  canonical_name?: string;
  members: any[];
  reason: string;
}

interface Props {
  entityType: string;
  groups: MergeGroup[];
  onComplete: () => void;
}

export default function DedupStepAutoMerge({ entityType, groups, onComplete }: Props) {
  const [activeGroups, setActiveGroups] = useState<MergeGroup[]>(groups);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [winnerOverrides, setWinnerOverrides] = useState<Record<string, number>>({});

  useEffect(() => {
    if (activeGroups.length === 0) {
      onComplete();
    }
  }, [activeGroups, onComplete]);

  const applyMutation = useMutation({
    mutationFn: async () => {
      // Employer renames first (before merging/deleting records)
      const employerGroups = activeGroups.filter((g) => g.canonical_name);
      for (const g of employerGroups) {
        await api.post('/kb/dedup/employer-rename', {
          career_history_ids: g.members.map((m: any) => m.id),
          canonical_name: g.canonical_name,
        });
      }

      // Then role merges (groups with winner_id, not employer renames)
      const roleGroups = activeGroups.filter((g) => g.winner_id && !g.canonical_name);
      const merges = roleGroups.map((g) => {
        const winnerId = winnerOverrides[g.group_id] ?? g.winner_id;
        return {
          winner_id: winnerId,
          loser_ids: g.members.filter((m: any) => m.id !== winnerId).map((m: any) => m.id),
        };
      });
      if (merges.length > 0) {
        await api.post('/kb/dedup/apply', { entity_type: entityType, merges, deletes: [], reclassifications: [] });
      }
    },
    onSuccess: onComplete,
  });

  const demoteGroup = (groupId: string) => {
    setActiveGroups((prev) => prev.filter((g) => g.group_id !== groupId));
  };

  const toggleExpand = (groupId: string) => {
    setExpanded((prev) => ({ ...prev, [groupId]: !prev[groupId] }));
  };

  if (activeGroups.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        No auto-merge groups. Proceeding...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-green-400 font-semibold text-lg">
          Auto-Merge Groups ({activeGroups.length})
        </h3>
        <button
          onClick={() => applyMutation.mutate()}
          disabled={applyMutation.isPending}
          className="px-6 py-2 bg-green-600 hover:bg-green-500 disabled:opacity-50 rounded-lg text-white font-medium transition-colors"
        >
          {applyMutation.isPending ? 'Applying...' : 'Confirm All'}
        </button>
      </div>

      {applyMutation.isError && (
        <div className="p-3 bg-red-900/40 border border-red-700 rounded text-red-300 text-sm">
          Error applying merges. Please try again.
        </div>
      )}

      {activeGroups.map((group) => {
        const isEmployerRename = !!group.canonical_name;
        const effectiveWinner = winnerOverrides[group.group_id] ?? group.winner_id;
        const isExpanded = expanded[group.group_id];

        return (
          <div
            key={group.group_id}
            className="bg-gray-800 rounded-lg border border-gray-700 p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap gap-2 mb-2">
                  {group.members.map((member: any) => {
                    const isWinner = !isEmployerRename && member.id === effectiveWinner;
                    const label = member.employer || member.title || member.name || member.text?.slice(0, 60) || member.content_preview || `#${member.id}`;
                    return (
                      <span
                        key={member.id}
                        className={`px-3 py-1 rounded text-sm font-medium ${
                          isWinner
                            ? 'bg-green-700 text-white font-bold'
                            : 'bg-gray-700 text-gray-300'
                        }`}
                      >
                        {label}
                      </span>
                    );
                  })}
                </div>
                <p className="text-gray-400 text-xs">{group.reason}</p>
                {isEmployerRename && (
                  <p className="text-green-400 text-xs mt-1">
                    Rename to: <span className="font-medium">{group.canonical_name}</span>
                  </p>
                )}
              </div>
              <div className="flex gap-2 shrink-0">
                {!isEmployerRename && (
                  <button
                    onClick={() => toggleExpand(group.group_id)}
                    className="px-3 py-1 rounded text-sm bg-gray-700 text-gray-300 hover:bg-gray-600 transition-colors"
                  >
                    {isExpanded ? 'Collapse' : 'Override'}
                  </button>
                )}
                <button
                  onClick={() => demoteGroup(group.group_id)}
                  className="px-3 py-1 rounded text-sm bg-yellow-700 text-yellow-200 hover:bg-yellow-600 transition-colors"
                >
                  Move to Review
                </button>
              </div>
            </div>

            {isExpanded && !isEmployerRename && (
              <div className="mt-3 pt-3 border-t border-gray-700">
                <p className="text-gray-400 text-xs mb-2">Select winner:</p>
                <div className="flex flex-wrap gap-2">
                  {group.members.map((member: any) => {
                    const isSelected = member.id === effectiveWinner;
                    return (
                      <button
                        key={member.id}
                        onClick={() =>
                          setWinnerOverrides((prev) => ({
                            ...prev,
                            [group.group_id]: member.id,
                          }))
                        }
                        className={`px-3 py-1 rounded text-sm transition-colors ${
                          isSelected
                            ? 'bg-green-700 border border-green-500 text-white font-bold'
                            : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                        }`}
                      >
                        {member.name || member.content_preview || `#${member.id}`}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
