import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

export const HIGHLIGHTS_ID = -1;

interface CareerJob {
  id: number;
  employer: string;
  title: string;
}

interface Props {
  isOpen: boolean;
  bulletId: number;
  currentJobId: number | null; // null = highlights
  onClose: () => void;
  onComplete: () => void;
}

export default function MoveCloneModal({ isOpen, bulletId, currentJobId, onClose, onComplete }: Props) {
  const [mode, setMode] = useState<'move' | 'copy'>('copy');
  const [targetId, setTargetId] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const queryClient = useQueryClient();

  const { data: jobs = [] } = useQuery({
    queryKey: ['career-history'],
    queryFn: () => api.get<CareerJob[]>('/career-history?limit=200'),
    enabled: isOpen,
  });

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return jobs.filter(
      (j) =>
        j.id !== currentJobId &&
        (j.title.toLowerCase().includes(q) || j.employer.toLowerCase().includes(q)),
    );
  }, [jobs, search, currentJobId]);

  // Group by employer
  const groups = useMemo(() => {
    const map: Record<string, CareerJob[]> = {};
    for (const j of filtered) {
      const key = j.employer || 'Unknown';
      if (!map[key]) map[key] = [];
      map[key].push(j);
    }
    return Object.entries(map).sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  const mutation = useMutation({
    mutationFn: () => {
      const endpoint = mode === 'move' ? 'move-to' : 'copy-to';
      const payload = targetId === HIGHLIGHTS_ID
        ? { career_history_id: null }
        : { career_history_id: targetId };
      return api.post(`/bullets/${bulletId}/${endpoint}`, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bullets'] });
      queryClient.invalidateQueries({ queryKey: ['bullets-all'] });
      onComplete();
      onClose();
    },
  });

  if (!isOpen) return null;

  const targetLabel =
    targetId === HIGHLIGHTS_ID
      ? 'Top Resume Highlights'
      : targetId
        ? (() => { const j = jobs.find((x) => x.id === targetId); return j ? `${j.title} @ ${j.employer}` : ''; })()
        : '';

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.6)', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: '#1e293b', borderRadius: 12, width: '90%', maxWidth: 500,
        maxHeight: '80vh', overflow: 'hidden', display: 'flex', flexDirection: 'column',
        border: '1px solid #334155',
      }}>
        {/* Header */}
        <div style={{ padding: '16px 20px 12px', borderBottom: '1px solid #334155' }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#f1f5f9' }}>
            {mode === 'move' ? 'Move' : 'Copy'} Bullet To...
          </h3>
        </div>

        {/* Mode toggle */}
        <div style={{ padding: '12px 20px 8px', display: 'flex', gap: 8 }}>
          {(['copy', 'move'] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              style={{
                padding: '6px 16px', fontSize: 13, fontWeight: 500, borderRadius: 6,
                border: mode === m ? '1px solid #3b82f6' : '1px solid #475569',
                background: mode === m ? '#3b82f6' : 'transparent',
                color: mode === m ? '#fff' : '#94a3b8',
                cursor: 'pointer',
              }}
            >
              {m === 'copy' ? 'Copy (keep original)' : 'Move (remove from current)'}
            </button>
          ))}
        </div>

        {/* Search */}
        <div style={{ padding: '8px 20px' }}>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter jobs..."
            style={{
              width: '100%', padding: '6px 10px', fontSize: 13,
              background: '#0f172a', border: '1px solid #475569', borderRadius: 6,
              color: '#e2e8f0', outline: 'none',
            }}
          />
        </div>

        {/* Job list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '4px 20px 12px' }}>
          {/* Highlights option */}
          {currentJobId !== null && (
            <div
              onClick={() => setTargetId(HIGHLIGHTS_ID)}
              style={{
                padding: '8px 12px', marginBottom: 4, borderRadius: 6, cursor: 'pointer',
                background: targetId === HIGHLIGHTS_ID ? '#1e3a5f' : '#0f172a',
                border: targetId === HIGHLIGHTS_ID ? '1px solid #3b82f6' : '1px solid transparent',
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 600, color: '#facc15' }}>
                Top Resume Highlights
              </div>
              <div style={{ fontSize: 11, color: '#64748b' }}>Top-level bullets not tied to a specific job</div>
            </div>
          )}

          {groups.map(([employer, groupJobs]) => (
            <div key={employer} style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b', padding: '4px 0', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                {employer}
              </div>
              {groupJobs.map((j) => (
                <div
                  key={j.id}
                  onClick={() => setTargetId(j.id)}
                  style={{
                    padding: '6px 12px', marginBottom: 2, borderRadius: 6, cursor: 'pointer',
                    background: targetId === j.id ? '#1e3a5f' : 'transparent',
                    border: targetId === j.id ? '1px solid #3b82f6' : '1px solid transparent',
                  }}
                >
                  <div style={{ fontSize: 13, color: '#e2e8f0' }}>{j.title}</div>
                </div>
              ))}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={{ padding: '12px 20px', borderTop: '1px solid #334155', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: 12, color: '#64748b', maxWidth: '60%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {targetLabel ? `${mode === 'move' ? 'Moving' : 'Copying'} to: ${targetLabel}` : 'Select a destination'}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={onClose}
              style={{
                padding: '6px 16px', fontSize: 13, color: '#94a3b8',
                background: 'transparent', border: '1px solid #475569',
                borderRadius: 6, cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              onClick={() => mutation.mutate()}
              disabled={targetId === null || mutation.isPending}
              style={{
                padding: '6px 16px', fontSize: 13, fontWeight: 500,
                color: '#fff',
                background: targetId === null || mutation.isPending ? '#475569' : '#3b82f6',
                border: 'none', borderRadius: 6,
                cursor: targetId === null || mutation.isPending ? 'not-allowed' : 'pointer',
              }}
            >
              {mutation.isPending ? 'Working...' : mode === 'move' ? 'Move' : 'Copy'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
