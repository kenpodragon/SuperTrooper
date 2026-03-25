import { useState, useEffect } from 'react';

interface AiInstructionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (instruction: string) => void;
  title: string;
  placeholder?: string;
  loading?: boolean;
}

export default function AiInstructionModal({
  isOpen,
  onClose,
  onSubmit,
  title,
  placeholder = 'Enter instructions for the AI...',
  loading = false,
}: AiInstructionModalProps) {
  const [instruction, setInstruction] = useState('');

  useEffect(() => {
    if (isOpen) setInstruction('');
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-gray-800 rounded-xl max-w-lg w-full mx-4 shadow-xl border border-gray-700">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-700">
          <h3 className="text-sm font-semibold text-gray-100">{title}</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-200 text-lg leading-none"
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4">
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder={placeholder}
            rows={4}
            className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 focus:border-purple-400 focus:outline-none resize-none"
            autoFocus
          />
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-5 py-3 border-t border-gray-700">
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded"
          >
            Cancel
          </button>
          <button
            onClick={() => onSubmit(instruction)}
            disabled={!instruction.trim() || loading}
            className="px-4 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs rounded disabled:opacity-50 flex items-center gap-1.5"
          >
            {loading && (
              <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            Submit
          </button>
        </div>
      </div>
    </div>
  );
}
