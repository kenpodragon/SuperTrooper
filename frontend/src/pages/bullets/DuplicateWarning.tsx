interface DuplicateMatch {
  id: number;
  text: string;
  similarity: number;
  employer?: string;
  title?: string;
}

interface DuplicateWarningProps {
  isOpen: boolean;
  onClose: () => void;
  onContinue: () => void;
  withinJob: DuplicateMatch[];
  crossJob: DuplicateMatch[];
}

function MatchList({ matches, showContext }: { matches: DuplicateMatch[]; showContext?: boolean }) {
  return (
    <ul className="space-y-2">
      {matches.map((m) => (
        <li key={m.id} className="flex items-start gap-2">
          <span className="shrink-0 text-[10px] px-1.5 py-0.5 bg-yellow-600/30 text-yellow-300 rounded mt-0.5">
            {Math.round(m.similarity * 100)}%
          </span>
          <div className="min-w-0">
            <p className="text-xs text-gray-300 line-clamp-2">{m.text}</p>
            {showContext && (m.employer || m.title) && (
              <p className="text-[10px] text-gray-500 mt-0.5">
                {[m.employer, m.title].filter(Boolean).join(' - ')}
              </p>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function DuplicateWarning({
  isOpen,
  onClose,
  onContinue,
  withinJob,
  crossJob,
}: DuplicateWarningProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-gray-800 rounded-xl max-w-lg w-full mx-4 shadow-xl border border-yellow-600">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-yellow-600/50 bg-yellow-900/20 rounded-t-xl">
          <h3 className="text-sm font-semibold text-yellow-300">Similar Bullets Found</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-200 text-lg leading-none"
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4 max-h-80 overflow-y-auto space-y-4">
          {withinJob.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-yellow-400 mb-2">In this job:</h4>
              <MatchList matches={withinJob} />
            </div>
          )}
          {crossJob.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-yellow-400 mb-2">In other jobs:</h4>
              <MatchList matches={crossJob} showContext />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-5 py-3 border-t border-gray-700">
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded"
          >
            Go Back
          </button>
          <button
            onClick={onContinue}
            className="px-4 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-white text-xs rounded"
          >
            Save Anyway
          </button>
        </div>
      </div>
    </div>
  );
}
