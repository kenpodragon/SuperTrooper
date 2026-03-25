import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { recipeBestPicks } from '../../api/client';
import type { BestPicksResult, BestPicksBullet, BestPicksJob } from '../../api/client';

interface Props {
  recipeId: number;
  applicationId?: number;
  onClose: () => void;
}

function pctBar(value: number) {
  const pct = Math.round(value * 100);
  const color = pct >= 60 ? '#4ade80' : pct >= 30 ? '#facc15' : '#f87171';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 80 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.1)' }}>
        <div style={{ width: `${pct}%`, height: '100%', borderRadius: 3, backgroundColor: color }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 700, color, minWidth: 32, textAlign: 'right' }}>{pct}%</span>
    </div>
  );
}

export default function BestPicksPanel({ recipeId, applicationId, onClose }: Props) {
  const [jdText, setJdText] = useState('');
  const [result, setResult] = useState<BestPicksResult | null>(null);
  const [tab, setTab] = useState<'bullets' | 'jobs' | 'skills'>('bullets');
  const [copied, setCopied] = useState<number | null>(null);

  const mutation = useMutation({
    mutationFn: () => recipeBestPicks(recipeId, jdText || undefined, applicationId),
    onSuccess: (data) => setResult(data),
  });

  const handleCopy = (bullet: BestPicksBullet) => {
    navigator.clipboard.writeText(bullet.text);
    setCopied(bullet.bullet_id);
    setTimeout(() => setCopied(null), 1500);
  };

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, bottom: 0, width: 400,
      backgroundColor: '#111827', borderLeft: '1px solid #374151',
      display: 'flex', flexDirection: 'column', zIndex: 50,
      color: '#e5e7eb', fontFamily: 'system-ui, sans-serif',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '16px 20px', borderBottom: '1px solid #374151',
      }}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>Best Picks</span>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer',
          fontSize: 20, lineHeight: 1,
        }}>&times;</button>
      </div>

      {/* JD Input */}
      {!result && (
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #374151' }}>
          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste job description here..."
            style={{
              width: '100%', height: 120, resize: 'vertical',
              backgroundColor: '#1f2937', border: '1px solid #374151',
              borderRadius: 8, padding: 12, color: '#e5e7eb', fontSize: 13,
              fontFamily: 'system-ui, sans-serif',
            }}
          />
          {applicationId && (
            <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 6 }}>
              Or leave empty to use JD from linked application #{applicationId}
            </div>
          )}
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || (!jdText.trim() && !applicationId)}
            style={{
              width: '100%', marginTop: 12, padding: '10px',
              borderRadius: 8, border: 'none', fontWeight: 600, fontSize: 14,
              backgroundColor: '#7c3aed', color: '#fff', cursor: 'pointer',
              opacity: mutation.isPending || (!jdText.trim() && !applicationId) ? 0.5 : 1,
            }}
          >
            {mutation.isPending ? 'Analyzing...' : 'Find Best Picks'}
          </button>
          {mutation.isError && (
            <div style={{ color: '#f87171', fontSize: 13, marginTop: 8 }}>
              Error: {(mutation.error as Error).message}
            </div>
          )}
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Tabs */}
          <div style={{
            display: 'flex', borderBottom: '1px solid #374151',
          }}>
            {(['bullets', 'jobs', 'skills'] as const).map((t) => (
              <button key={t} onClick={() => setTab(t)} style={{
                flex: 1, padding: '10px', border: 'none', cursor: 'pointer',
                backgroundColor: tab === t ? '#1f2937' : 'transparent',
                color: tab === t ? '#e5e7eb' : '#6b7280',
                fontWeight: tab === t ? 700 : 400, fontSize: 13,
                borderBottom: tab === t ? '2px solid #7c3aed' : '2px solid transparent',
              }}>
                {t === 'bullets' ? `Bullets (${result.ranked_bullets.length})` :
                 t === 'jobs' ? `Jobs (${result.ranked_jobs.length})` :
                 `Skills (${result.suggested_skills.length})`}
              </button>
            ))}
          </div>

          {/* Mode badge */}
          <div style={{ padding: '8px 20px', textAlign: 'right' }}>
            <span style={{
              padding: '2px 10px', borderRadius: 9999, fontSize: 11, fontWeight: 600,
              backgroundColor: result.analysis_mode === 'ai' ? 'rgba(139,92,246,0.2)' : 'rgba(59,130,246,0.2)',
              color: result.analysis_mode === 'ai' ? '#a78bfa' : '#60a5fa',
            }}>
              {result.analysis_mode === 'ai' ? 'AI Analysis' : 'Rule-Based'}
            </span>
          </div>

          {/* Tab content */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '0 20px 20px' }}>
            {tab === 'bullets' && result.ranked_bullets.map((b: BestPicksBullet) => (
              <div
                key={b.bullet_id}
                onClick={() => handleCopy(b)}
                style={{
                  padding: '10px 12px', marginBottom: 8, borderRadius: 8, cursor: 'pointer',
                  backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid #1f2937',
                  transition: 'border-color 0.15s',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#7c3aed')}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#1f2937')}
              >
                {pctBar(b.relevance)}
                <div style={{ fontSize: 13, margin: '6px 0', lineHeight: 1.4 }}>{b.text}</div>
                <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4 }}>{b.job}</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {b.matched_keywords.slice(0, 8).map((kw) => (
                    <span key={kw} style={{
                      padding: '1px 6px', borderRadius: 4, fontSize: 10,
                      backgroundColor: 'rgba(124,58,237,0.2)', color: '#c4b5fd',
                    }}>
                      {kw}
                    </span>
                  ))}
                </div>
                {copied === b.bullet_id && (
                  <div style={{ fontSize: 11, color: '#4ade80', marginTop: 4 }}>Copied!</div>
                )}
              </div>
            ))}

            {tab === 'jobs' && result.ranked_jobs.map((j: BestPicksJob) => (
              <div key={j.career_history_id} style={{
                padding: '10px 12px', marginBottom: 8, borderRadius: 8,
                backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid #1f2937',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{j.company}</div>
                    <div style={{ fontSize: 12, color: '#9ca3af' }}>{j.title}</div>
                  </div>
                </div>
                <div style={{ marginTop: 6 }}>{pctBar(j.relevance)}</div>
                <div style={{ fontSize: 12, color: '#c4b5fd', marginTop: 4 }}>{j.reason}</div>
              </div>
            ))}

            {tab === 'skills' && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, paddingTop: 8 }}>
                {result.suggested_skills.length === 0 && (
                  <div style={{ color: '#9ca3af', fontSize: 13 }}>No missing skills detected.</div>
                )}
                {result.suggested_skills.map((s) => (
                  <span key={s} style={{
                    padding: '4px 12px', borderRadius: 9999, fontSize: 13,
                    backgroundColor: 'rgba(234,179,8,0.15)', color: '#facc15',
                    fontWeight: 500,
                  }}>
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Re-analyze / back */}
          <div style={{ padding: '12px 20px', borderTop: '1px solid #374151', display: 'flex', gap: 8 }}>
            <button
              onClick={() => { setResult(null); setCopied(null); }}
              style={{
                flex: 1, padding: '10px', borderRadius: 8,
                backgroundColor: '#1f2937', border: '1px solid #374151',
                color: '#e5e7eb', cursor: 'pointer', fontWeight: 600, fontSize: 13,
              }}
            >
              New Search
            </button>
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              style={{
                flex: 1, padding: '10px', borderRadius: 8,
                backgroundColor: '#7c3aed', border: 'none',
                color: '#fff', cursor: 'pointer', fontWeight: 600, fontSize: 13,
                opacity: mutation.isPending ? 0.5 : 1,
              }}
            >
              {mutation.isPending ? 'Analyzing...' : 'Re-analyze'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
