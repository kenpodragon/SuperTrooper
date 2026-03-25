interface Props {
  recipeName: string;
  saveState: 'saved' | 'saving' | 'unsaved';
  onGenerate: () => void;
  onAiReview: () => void;
  onAtsScore: () => void;
  onBestPicks: () => void;
  onToggleTheme: () => void;
  onAiGenerate: () => void;
  generating?: boolean;
}

export default function EditorToolbar({
  recipeName, saveState, onGenerate, onAiReview, onAtsScore, onBestPicks, onToggleTheme, onAiGenerate, generating,
}: Props) {
  return (
    <div className="sticky top-0 z-20 bg-gray-900 border-b border-gray-700 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <h2 className="font-bold text-lg">{recipeName}</h2>
        <span className={`text-xs px-2 py-0.5 rounded ${
          saveState === 'saved' ? 'bg-green-900/30 text-green-400' :
          saveState === 'saving' ? 'bg-yellow-900/30 text-yellow-400' :
          'bg-red-900/30 text-red-400'
        }`}>
          {saveState === 'saved' ? 'Saved' : saveState === 'saving' ? 'Saving...' : 'Unsaved'}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <button onClick={onToggleTheme} className="px-3 py-1.5 text-sm bg-gray-800 rounded hover:bg-gray-700">Theme</button>
        <button onClick={onAiGenerate} className="px-3 py-1.5 text-sm bg-purple-700 rounded hover:bg-purple-600">AI Generate</button>
        <button onClick={onBestPicks} className="px-3 py-1.5 text-sm bg-violet-700 rounded hover:bg-violet-600">Best Picks</button>
        <button onClick={onAiReview} className="px-3 py-1.5 text-sm bg-gray-800 rounded hover:bg-gray-700">AI Review</button>
        <button onClick={onAtsScore} className="px-3 py-1.5 text-sm bg-gray-800 rounded hover:bg-gray-700">ATS Score</button>
        <button onClick={onGenerate} disabled={generating} className="px-3 py-1.5 text-sm bg-blue-600 rounded hover:bg-blue-500 disabled:opacity-50">
          {generating ? 'Generating...' : 'Generate .docx'}
        </button>
      </div>
    </div>
  );
}
