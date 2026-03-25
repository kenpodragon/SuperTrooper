import { useState } from 'react';
import BlockWrapper from './BlockWrapper';

interface Props {
  label: string;
  slotKey: string;
  value: string;
  onSave: (slotKey: string, text: string) => void;
  onPickFromDb?: () => void;
  onAiGenerate?: () => void;
}

export default function TextBlock({ label, slotKey, value, onSave, onPickFromDb, onAiGenerate }: Props) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value);

  const handleBlur = () => {
    setEditing(false);
    if (text !== value) {
      onSave(slotKey, text);
    }
  };

  return (
    <BlockWrapper label={label}>
      <div className="relative group/text">
        {editing ? (
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onBlur={handleBlur}
            autoFocus
            className="w-full bg-transparent border border-blue-500/30 rounded p-2 text-sm resize-y min-h-16 outline-none"
          />
        ) : (
          <p
            onClick={() => setEditing(true)}
            className="text-sm cursor-pointer hover:bg-gray-800/50 rounded p-2 whitespace-pre-wrap"
          >
            {value || <span className="text-gray-500 italic">[Click to edit {label.toLowerCase()}]</span>}
          </p>
        )}
        {!editing && (
          <div className="absolute top-1 right-1 hidden group-hover/text:flex gap-1">
            {onPickFromDb && (
              <button onClick={onPickFromDb} className="text-xs px-2 py-0.5 bg-gray-700 rounded hover:bg-gray-600">Pick</button>
            )}
            {onAiGenerate && (
              <button onClick={onAiGenerate} className="text-xs px-2 py-0.5 bg-blue-700 rounded hover:bg-blue-600">AI</button>
            )}
          </div>
        )}
      </div>
    </BlockWrapper>
  );
}
