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

  // Highlights use bullet points, education/certs use pipe-separated format
  const isHighlights = slotKey === 'highlights';

  return (
    <BlockWrapper label={label}>
      <ul style={{
        margin: 0,
        paddingLeft: isHighlights ? 18 : 0,
        listStyleType: isHighlights ? 'disc' : 'none',
      }}>
        {localItems.map((item, idx) => (
          <li
            key={idx}
            className="group/item"
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 6,
              marginBottom: 3,
              fontSize: 'var(--font-size-body, 10.5pt)',
              lineHeight: 1.5,
            }}
          >
            {!isHighlights && (
              <span style={{ color: '#999', flexShrink: 0 }}>&bull;</span>
            )}
            {editingIdx === idx ? (
              <input
                value={item}
                onChange={(e) => handleItemChange(idx, e.target.value)}
                onBlur={() => handleItemBlur(idx)}
                autoFocus
                style={{
                  flex: 1, background: '#fefce8', border: '1px solid #d4a017',
                  borderRadius: 3, fontSize: 'inherit', fontFamily: 'inherit',
                  outline: 'none', padding: '2px 4px', color: '#111',
                }}
              />
            ) : (
              <span
                onClick={() => setEditingIdx(idx)}
                style={{
                  flex: 1, cursor: 'pointer', color: '#222',
                  padding: '0 2px', borderRadius: 2,
                }}
              >
                {item || <span style={{ color: '#aaa', fontStyle: 'italic' }}>[empty]</span>}
              </span>
            )}
            <button
              onClick={() => removeItem(idx)}
              style={{
                background: 'none', border: 'none', color: '#ccc',
                cursor: 'pointer', fontSize: 14, flexShrink: 0,
                display: 'none', padding: 0,
              }}
              className="group-hover/item:!inline"
            >
              &times;
            </button>
          </li>
        ))}
      </ul>
      <button
        onClick={addItem}
        style={{ fontSize: 11, color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer', marginTop: 4 }}
      >
        + Add {label.toLowerCase().replace(/s$/, '')}
      </button>
    </BlockWrapper>
  );
}
