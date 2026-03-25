import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { recipeGenerateSlot, type GenerateSlotSuggestion } from '../../api/client';

interface Props {
  recipeId: number;
  slotType: string;
  jobId?: number;
  existingBullets?: string[];
  onSelect: (text: string) => void;
  onClose: () => void;
}

export default function AiGenerateModal({
  recipeId, slotType, jobId, existingBullets, onSelect, onClose,
}: Props) {
  const [instructions, setInstructions] = useState('');
  const [suggestions, setSuggestions] = useState<GenerateSlotSuggestion[]>([]);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [editText, setEditText] = useState('');
  const [analysisMode, setAnalysisMode] = useState('');

  const generateMut = useMutation({
    mutationFn: () => recipeGenerateSlot(recipeId, slotType, {
      job_id: jobId,
      existing_bullets: existingBullets,
      instructions: instructions || undefined,
    }),
    onSuccess: (data) => {
      setSuggestions(data.suggestions);
      setAnalysisMode(data.analysis_mode);
      setSelectedIdx(null);
      setEditText('');
    },
  });

  const handleSelect = (idx: number) => {
    setSelectedIdx(idx);
    setEditText(suggestions[idx].text);
  };

  const slotLabel = slotType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-gray-900 border border-gray-700 rounded-lg shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <h3 className="text-lg font-bold">Generate {slotLabel}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">&times;</button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {/* Instructions */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Instructions (optional)</label>
            <textarea
              value={instructions}
              onChange={e => setInstructions(e.target.value)}
              placeholder="e.g. emphasize cost savings, focus on team leadership..."
              className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm resize-none h-16"
            />
          </div>

          {/* Generate button */}
          <button
            onClick={() => generateMut.mutate()}
            disabled={generateMut.isPending}
            className="px-4 py-2 text-sm bg-purple-600 rounded hover:bg-purple-500 disabled:opacity-50"
          >
            {generateMut.isPending ? 'Generating...' : suggestions.length > 0 ? 'Regenerate' : 'Generate'}
          </button>

          {generateMut.isError && (
            <p className="text-red-400 text-sm">Error: {(generateMut.error as Error).message}</p>
          )}

          {/* Analysis mode badge */}
          {analysisMode && (
            <span className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-400">
              Mode: {analysisMode}
            </span>
          )}

          {/* Suggestions */}
          {suggestions.length > 0 ? (
            <div className="space-y-2">
              {suggestions.map((s, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSelect(idx)}
                  className={`w-full text-left p-3 rounded border transition-colors ${
                    selectedIdx === idx
                      ? 'border-purple-500 bg-purple-900/20'
                      : 'border-gray-700 bg-gray-800 hover:border-gray-500'
                  }`}
                >
                  <p className="text-sm">{s.text}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs text-gray-500">{s.source}</span>
                    <span className="text-xs text-gray-500">{Math.round(s.confidence * 100)}%</span>
                  </div>
                </button>
              ))}
            </div>
          ) : !generateMut.isPending && suggestions.length === 0 && generateMut.isSuccess ? (
            <p className="text-sm text-gray-500 italic">No suggestions found. Try different instructions or check your data.</p>
          ) : null}

          {/* Edit textarea */}
          {selectedIdx !== null && (
            <div>
              <label className="block text-sm text-gray-400 mb-1">Edit before inserting</label>
              <textarea
                value={editText}
                onChange={e => setEditText(e.target.value)}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm resize-none h-20"
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-700">
          <button onClick={onClose} className="px-4 py-2 text-sm bg-gray-800 rounded hover:bg-gray-700">
            Cancel
          </button>
          <button
            onClick={() => { onSelect(editText); onClose(); }}
            disabled={selectedIdx === null || !editText.trim()}
            className="px-4 py-2 text-sm bg-green-600 rounded hover:bg-green-500 disabled:opacity-50"
          >
            Insert
          </button>
        </div>
      </div>
    </div>
  );
}
