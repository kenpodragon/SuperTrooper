import { useState } from 'react';
import BlockWrapper from './BlockWrapper';

interface Props {
  label: string;
  slotKey: string;
  items: string[];
  onUpdate: (slotKey: string, items: string[]) => void;
}

export default function LiteralListBlock({ label, slotKey, items, onUpdate }: Props) {
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [localItems, setLocalItems] = useState(items);

  const handleItemBlur = (idx: number) => {
    setEditingIdx(null);
    if (JSON.stringify(localItems) !== JSON.stringify(items)) {
      onUpdate(slotKey, localItems);
    }
  };

  const handleItemChange = (idx: number, text: string) => {
    const updated = [...localItems];
    updated[idx] = text;
    setLocalItems(updated);
  };

  const addItem = () => {
    const updated = [...localItems, ''];
    setLocalItems(updated);
    setEditingIdx(updated.length - 1);
  };

  const removeItem = (idx: number) => {
    const updated = localItems.filter((_, i) => i !== idx);
    setLocalItems(updated);
    onUpdate(slotKey, updated);
  };

  return (
    <BlockWrapper label={label}>
      <ul className="space-y-1">
        {localItems.map((item, idx) => (
          <li key={idx} className="flex items-start gap-2 group/item">
            <span className="text-gray-500 mt-0.5">&bull;</span>
            {editingIdx === idx ? (
              <input
                value={item}
                onChange={(e) => handleItemChange(idx, e.target.value)}
                onBlur={() => handleItemBlur(idx)}
                autoFocus
                className="flex-1 bg-transparent border-b border-blue-500/30 text-sm outline-none py-0.5"
              />
            ) : (
              <span
                onClick={() => setEditingIdx(idx)}
                className="flex-1 text-sm cursor-pointer hover:bg-gray-800/50 rounded px-1 py-0.5"
              >
                {item || <span className="text-gray-500 italic">[empty]</span>}
              </span>
            )}
            <button
              onClick={() => removeItem(idx)}
              className="text-gray-600 hover:text-red-400 text-xs hidden group-hover/item:block"
            >
              &times;
            </button>
          </li>
        ))}
      </ul>
      <button onClick={addItem} className="text-xs text-blue-400 hover:text-blue-300 mt-2">
        + Add {label.toLowerCase().replace(/s$/, '')}
      </button>
    </BlockWrapper>
  );
}
