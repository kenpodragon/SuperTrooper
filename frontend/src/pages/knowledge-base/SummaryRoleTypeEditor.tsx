import { useState, useEffect } from 'react';
import { api } from '../../api/client';

interface RoleTypeSuggestion {
  current: string;
  suggested: string | null;
  reason: string;
}

interface Props {
  suggestions: RoleTypeSuggestion[];
  onComplete: () => void;
}

export function SummaryRoleTypeEditor({ suggestions, onComplete }: Props) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (suggestions.length === 0) {
      onComplete();
      return;
    }
    const initial: Record<string, string> = {};
    for (const s of suggestions) {
      initial[s.current] = s.suggested ?? s.current;
    }
    setValues(initial);
  }, [suggestions, onComplete]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const reassignments: Record<string, string> = {};
      for (const [oldLabel, newLabel] of Object.entries(values)) {
        if (newLabel.trim() && newLabel.trim() !== oldLabel) {
          reassignments[oldLabel] = newLabel.trim();
        }
      }
      await api.post('/kb/dedup/summaries/role-types', { reassignments });
      onComplete();
    } catch (err: any) {
      setError(err?.message ?? 'Failed to save role types');
    } finally {
      setSaving(false);
    }
  };

  if (suggestions.length === 0) return null;

  return (
    <div className="bg-gray-800 rounded-lg border border-purple-700/30 p-4 space-y-4">
      <div>
        <h3 className="text-purple-400 font-semibold text-sm uppercase tracking-wide mb-1">
          Role Type Labels
        </h3>
        <p className="text-gray-400 text-sm">
          AI has suggested clearer labels for auto-generated role types. Edit as needed.
        </p>
      </div>

      <div className="space-y-3">
        {suggestions.map((s) => (
          <div key={s.current} className="space-y-1">
            <div className="flex items-center gap-3">
              <span className="bg-gray-700 text-gray-300 text-xs px-2 py-1 rounded font-mono whitespace-nowrap">
                {s.current}
              </span>
              <span className="text-gray-500 text-sm">→</span>
              <input
                type="text"
                value={values[s.current] ?? ''}
                onChange={(e) =>
                  setValues((prev) => ({ ...prev, [s.current]: e.target.value }))
                }
                className="flex-1 bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-white focus:border-purple-500 focus:outline-none"
                placeholder="New label..."
              />
            </div>
            {s.reason && (
              <p className="text-gray-500 text-xs pl-1">{s.reason}</p>
            )}
          </div>
        ))}
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={saving}
          className="bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded transition-colors"
        >
          {saving ? 'Saving...' : 'Save & Continue'}
        </button>
      </div>
    </div>
  );
}
