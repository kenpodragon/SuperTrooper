import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { recipeAiReview } from '../../api/client';
import type { AiReviewResult, AiReviewFeedbackItem, AiReviewTargetRole } from '../../api/client';

interface Props {
  recipeId: number;
  onClose: () => void;
}

const severityColor: Record<string, { bg: string; text: string; label: string }> = {
  high: { bg: 'rgba(239,68,68,0.15)', text: '#f87171', label: 'HIGH' },
  medium: { bg: 'rgba(234,179,8,0.15)', text: '#facc15', label: 'MED' },
  low: { bg: 'rgba(59,130,246,0.15)', text: '#60a5fa', label: 'LOW' },
};

function scoreColor(score: number): string {
  if (score >= 80) return '#4ade80';
  if (score >= 60) return '#facc15';
  return '#f87171';
}

export default function AiReviewPanel({ recipeId, onClose }: Props) {
  const [result, setResult] = useState<AiReviewResult | null>(null);

  const mutation = useMutation({
    mutationFn: () => recipeAiReview(recipeId),
    onSuccess: (data) => setResult(data),
  });

  // Auto-trigger on first render
  useState(() => { mutation.mutate(); });

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, bottom: 0, width: 380,
      backgroundColor: '#111827', borderLeft: '1px solid #374151',
      display: 'flex', flexDirection: 'column', zIndex: 50,
      color: '#e5e7eb', fontFamily: 'system-ui, sans-serif',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '16px 20px', borderBottom: '1px solid #374151',
      }}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>AI Review</span>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer',
          fontSize: 20, lineHeight: 1,
        }}>&times;</button>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
        {mutation.isPending && (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#9ca3af' }}>
            Analyzing resume...
          </div>
        )}

        {mutation.isError && (
          <div style={{ color: '#f87171', padding: '20px 0' }}>
            Error: {(mutation.error as Error).message}
          </div>
        )}

        {result && (
          <>
            {/* Score gauge */}
            <div style={{ textAlign: 'center', marginBottom: 24 }}>
              <div style={{
                fontSize: 56, fontWeight: 800, lineHeight: 1,
                color: scoreColor(result.generic.score),
              }}>
                {result.generic.score}
              </div>
              <div style={{ color: '#9ca3af', fontSize: 13, marginTop: 4 }}>Quality Score</div>
              <span style={{
                display: 'inline-block', marginTop: 8,
                padding: '2px 10px', borderRadius: 9999, fontSize: 11, fontWeight: 600,
                backgroundColor: result.analysis_mode === 'ai' ? 'rgba(139,92,246,0.2)' : 'rgba(59,130,246,0.2)',
                color: result.analysis_mode === 'ai' ? '#a78bfa' : '#60a5fa',
              }}>
                {result.analysis_mode === 'ai' ? 'AI Analysis' : 'Rule-Based'}
              </span>
            </div>

            {/* Strengths */}
            {result.generic.strengths.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontWeight: 600, fontSize: 13, color: '#4ade80', marginBottom: 8 }}>
                  Strengths
                </div>
                {result.generic.strengths.map((s, i) => (
                  <div key={i} style={{
                    padding: '6px 10px', marginBottom: 4, borderRadius: 6,
                    backgroundColor: 'rgba(74,222,128,0.08)', fontSize: 13,
                  }}>
                    + {s}
                  </div>
                ))}
              </div>
            )}

            {/* Feedback */}
            {result.generic.feedback.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontWeight: 600, fontSize: 13, color: '#e5e7eb', marginBottom: 8 }}>
                  Feedback
                </div>
                {result.generic.feedback.map((f: AiReviewFeedbackItem, i: number) => {
                  const sev = severityColor[f.severity] || severityColor.low;
                  return (
                    <div key={i} style={{
                      padding: '8px 10px', marginBottom: 6, borderRadius: 6,
                      backgroundColor: 'rgba(255,255,255,0.04)', fontSize: 13,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                        <span style={{
                          padding: '1px 6px', borderRadius: 4, fontSize: 10, fontWeight: 700,
                          backgroundColor: sev.bg, color: sev.text,
                        }}>
                          {sev.label}
                        </span>
                        <span style={{ color: '#9ca3af', fontSize: 12 }}>{f.section}</span>
                      </div>
                      <div>{f.issue}</div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Target Roles */}
            {result.target_roles.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontWeight: 600, fontSize: 13, color: '#e5e7eb', marginBottom: 8 }}>
                  Target Role Fit
                </div>
                {result.target_roles.map((tr: AiReviewTargetRole, i: number) => (
                  <div key={i} style={{
                    padding: '10px 12px', marginBottom: 8, borderRadius: 8,
                    backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid #1f2937',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <span style={{ fontWeight: 600, fontSize: 14 }}>{tr.role}</span>
                      <span style={{ fontWeight: 700, fontSize: 18, color: scoreColor(tr.score) }}>
                        {tr.score}
                      </span>
                    </div>
                    {tr.gaps.length > 0 && (
                      <div style={{ marginBottom: 4 }}>
                        {tr.gaps.map((g, j) => (
                          <div key={j} style={{ fontSize: 12, color: '#f87171', paddingLeft: 8 }}>
                            - {g}
                          </div>
                        ))}
                      </div>
                    )}
                    {tr.suggestions.length > 0 && (
                      <div>
                        {tr.suggestions.map((s, j) => (
                          <div key={j} style={{ fontSize: 12, color: '#c084fc', paddingLeft: 8 }}>
                            + {s}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Re-analyze button */}
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              style={{
                width: '100%', padding: '10px', borderRadius: 8,
                backgroundColor: '#1f2937', border: '1px solid #374151',
                color: '#e5e7eb', cursor: 'pointer', fontWeight: 600, fontSize: 13,
                opacity: mutation.isPending ? 0.5 : 1,
              }}
            >
              {mutation.isPending ? 'Analyzing...' : 'Re-analyze'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
