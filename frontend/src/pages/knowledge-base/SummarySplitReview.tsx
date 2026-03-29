import { useState, useEffect } from 'react';
import { api } from '../../api/client';

interface MixedContent {
  id: number;
  original_text: string;
  summary_portion: string;
  bullet_portions: string[];
  reason: string;
  career_history_id?: number;
}

interface Props {
  mixedContent: MixedContent[];
  onComplete: () => void;
}

export function SummarySplitReview({ mixedContent, onComplete }: Props) {
  const [skipped, setSkipped] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (mixedContent.length === 0) {
      onComplete();
    }
  }, [mixedContent, onComplete]);

  const toggleSkip = (id: number) => {
    setSkipped((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleConfirm = async () => {
    setSaving(true);
    setError(null);
    try {
      const splits = mixedContent
        .filter((item) => !skipped.has(item.id))
        .map((item) => ({
          id: item.id,
          keep_summary_text: item.summary_portion,
          extract_bullets: item.bullet_portions,
          career_history_id: item.career_history_id ?? null,
        }));
      await api.post('/api/kb/dedup/summaries/split', { splits });
      onComplete();
    } catch (err: any) {
      setError(err?.message ?? 'Failed to confirm splits');
    } finally {
      setSaving(false);
    }
  };

  if (mixedContent.length === 0) return null;

  const activeCount = mixedContent.length - skipped.size;

  return (
    <div className="bg-gray-800 rounded-lg border border-orange-700/30 p-4 space-y-4">
      <div>
        <h3 className="text-orange-400 font-semibold text-sm uppercase tracking-wide mb-1">
          Mixed Content — Split Review
        </h3>
        <p className="text-gray-400 text-sm">
          These summaries contain both summary text and bullet points. Review the proposed split and skip any you'd like to leave unchanged.
        </p>
      </div>

      <div className="space-y-4">
        {mixedContent.map((item) => {
          const isSkipped = skipped.has(item.id);
          return (
            <div
              key={item.id}
              className={`rounded-lg border p-3 space-y-2 transition-opacity ${
                isSkipped
                  ? 'opacity-40 border-gray-700'
                  : 'border-orange-700/20'
              }`}
            >
              {item.reason && (
                <p className="text-gray-500 text-xs">{item.reason}</p>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-green-900/20 border border-green-800/30 rounded p-3 space-y-1">
                  <p className="text-green-400 text-xs font-semibold uppercase tracking-wide mb-2">
                    Keep as Summary
                  </p>
                  <p className="text-gray-200 text-sm leading-relaxed">
                    {item.summary_portion}
                  </p>
                </div>

                <div className="bg-blue-900/20 border border-blue-800/30 rounded p-3 space-y-1">
                  <p className="text-blue-400 text-xs font-semibold uppercase tracking-wide mb-2">
                    Extract as Bullets
                  </p>
                  <ul className="space-y-1">
                    {item.bullet_portions.map((bullet, i) => (
                      <li key={i} className="text-gray-200 text-sm flex gap-2">
                        <span className="text-blue-400 mt-0.5 shrink-0">•</span>
                        <span>{bullet}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  onClick={() => toggleSkip(item.id)}
                  className="text-sm text-gray-400 hover:text-white transition-colors"
                >
                  {isSkipped ? 'Undo Skip' : 'Skip'}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <div className="flex items-center justify-between">
        <p className="text-gray-500 text-xs">
          {activeCount} of {mixedContent.length} will be split
        </p>
        <button
          onClick={handleConfirm}
          disabled={saving}
          className="bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded transition-colors"
        >
          {saving ? 'Confirming...' : 'Confirm Splits'}
        </button>
      </div>
    </div>
  );
}
