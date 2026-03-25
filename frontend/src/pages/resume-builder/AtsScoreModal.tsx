import { useState } from 'react';
import { recipeAtsScore, type AtsScoreResult } from '../../api/client';

interface Props {
  recipeId: number;
  applicationId?: number;
  onClose: () => void;
}

export default function AtsScoreModal({ recipeId, applicationId, onClose }: Props) {
  const [jdText, setJdText] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AtsScoreResult | null>(null);
  const [error, setError] = useState('');

  const runScore = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await recipeAtsScore(recipeId, jdText || undefined, applicationId);
      setResult(data);
    } catch (e: any) {
      setError(e.message || 'Failed to score');
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setResult(null);
    setError('');
  };

  const scoreColor = (score: number) => {
    if (score >= 80) return '#22c55e';
    if (score >= 60) return '#eab308';
    return '#ef4444';
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(0,0,0,0.6)',
    }} onClick={onClose}>
      <div style={{
        background: 'var(--bg-primary, #1e1e2e)',
        border: '1px solid var(--border-color, #333)',
        borderRadius: 12, padding: 24, width: 520, maxHeight: '80vh',
        overflow: 'hidden', display: 'flex', flexDirection: 'column',
        color: 'var(--text-secondary, #e0e0e0)',
      }} onClick={e => e.stopPropagation()}>
        <h2 style={{ margin: '0 0 16px', fontSize: 18, fontWeight: 600 }}>ATS Score</h2>

        {!result ? (
          <>
            <textarea
              value={jdText}
              onChange={e => setJdText(e.target.value)}
              placeholder="Paste job description here or leave blank to score against target roles"
              rows={8}
              style={{
                width: '100%', padding: 10, borderRadius: 6, resize: 'vertical',
                background: 'var(--bg-secondary, #2a2a3e)',
                border: '1px solid var(--border-color, #444)',
                color: 'var(--text-secondary, #e0e0e0)',
                fontFamily: 'inherit', fontSize: 13,
              }}
            />
            {error && <p style={{ color: '#ef4444', margin: '8px 0 0', fontSize: 13 }}>{error}</p>}
            <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
              <button onClick={onClose} style={{
                padding: '8px 16px', borderRadius: 6, border: '1px solid var(--border-color, #444)',
                background: 'transparent', color: 'var(--text-secondary, #ccc)', cursor: 'pointer',
              }}>Cancel</button>
              <button onClick={runScore} disabled={loading} style={{
                padding: '8px 20px', borderRadius: 6, border: 'none',
                background: '#3b82f6', color: '#fff', cursor: loading ? 'wait' : 'pointer',
                fontWeight: 600, opacity: loading ? 0.7 : 1,
              }}>{loading ? 'Scoring...' : 'Run ATS Score'}</button>
            </div>
          </>
        ) : (
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {/* Score display */}
            <div style={{ textAlign: 'center', marginBottom: 16 }}>
              <div style={{
                fontSize: 56, fontWeight: 700,
                color: scoreColor(result.ats_score),
                lineHeight: 1.1,
              }}>{result.ats_score}</div>
              <div style={{ fontSize: 14, color: 'var(--text-tertiary, #999)', marginTop: 4 }}>
                {result.keywords_found}/{result.keywords_checked} keywords matched ({result.match_percentage}%)
              </div>
              <span style={{
                display: 'inline-block', marginTop: 8, padding: '3px 10px',
                borderRadius: 12, fontSize: 11, fontWeight: 600,
                background: result.analysis_mode === 'ai-enhanced' ? '#7c3aed33' : '#3b82f633',
                color: result.analysis_mode === 'ai-enhanced' ? '#a78bfa' : '#60a5fa',
              }}>
                {result.analysis_mode === 'ai-enhanced' ? 'AI-enhanced' : 'Rule-based'}
              </span>
            </div>

            {/* Keyword checklist */}
            <div style={{
              maxHeight: 220, overflowY: 'auto', marginBottom: 16,
              background: 'var(--bg-secondary, #2a2a3e)',
              borderRadius: 8, padding: 12,
            }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: 'var(--text-tertiary, #999)' }}>
                Keywords
              </div>
              {Object.entries(result.keyword_matches).map(([kw, found]) => (
                <div key={kw} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '3px 0', fontSize: 13,
                }}>
                  <span style={{ color: found ? '#22c55e' : '#ef4444', fontWeight: 700, width: 16 }}>
                    {found ? '\u2713' : '\u2717'}
                  </span>
                  <span style={{ color: found ? 'var(--text-secondary, #e0e0e0)' : 'var(--text-tertiary, #999)' }}>
                    {kw}
                  </span>
                </div>
              ))}
            </div>

            {/* Formatting flags */}
            {result.formatting_flags.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: '#eab308' }}>Formatting Issues</div>
                {result.formatting_flags.map((flag, i) => (
                  <div key={i} style={{ fontSize: 13, color: 'var(--text-tertiary, #999)' }}>{flag}</div>
                ))}
              </div>
            )}

            {/* AI suggestions */}
            {result.suggestions && result.suggestions.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: '#a78bfa' }}>AI Suggestions</div>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {result.suggestions.map((s, i) => (
                    <li key={i} style={{ fontSize: 13, marginBottom: 4, color: 'var(--text-secondary, #e0e0e0)' }}>{s}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
              <button onClick={reset} style={{
                padding: '8px 16px', borderRadius: 6, border: '1px solid var(--border-color, #444)',
                background: 'transparent', color: 'var(--text-secondary, #ccc)', cursor: 'pointer',
              }}>Re-score</button>
              <button onClick={onClose} style={{
                padding: '8px 20px', borderRadius: 6, border: 'none',
                background: '#3b82f6', color: '#fff', cursor: 'pointer', fontWeight: 600,
              }}>Close</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
