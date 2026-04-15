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

  // Headline renders differently — no section header, styled as subtitle
  const isHeadline = slotKey === 'headline';

  return (
    <BlockWrapper label={label} showHeader={!isHeadline}>
      <div style={{ position: 'relative' }} className="group/text">
        {editing ? (
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onBlur={handleBlur}
            autoFocus
            style={{
              width: '100%',
              background: '#fefce8',
              border: '1px solid #d4a017',
              borderRadius: 4,
              padding: 8,
              fontSize: isHeadline ? '11pt' : 'var(--font-size-body, 10.5pt)',
              fontFamily: 'inherit',
              resize: 'vertical',
              minHeight: 60,
              outline: 'none',
              color: '#111',
            }}
          />
        ) : (
          <p
            onClick={() => setEditing(true)}
            style={{
              fontSize: isHeadline ? '11pt' : 'var(--font-size-body, 10.5pt)',
              color: isHeadline ? '#2563eb' : '#222',
              fontWeight: isHeadline ? 600 : 400,
              fontStyle: isHeadline ? 'italic' : 'normal',
              textAlign: isHeadline ? 'var(--header-alignment, center)' as any : 'left',
              lineHeight: 1.5,
              cursor: 'pointer',
              margin: 0,
              padding: 2,
              borderRadius: 2,
              whiteSpace: 'pre-wrap',
            }}
          >
            {value || <span style={{ color: '#aaa', fontStyle: 'italic' }}>[Click to add {label.toLowerCase()}]</span>}
          </p>
        )}
        {!editing && (
          <div style={{
            position: 'absolute', top: 2, right: 2,
            display: 'none', gap: 4,
          }} className="group-hover/text:!flex">
            {onPickFromDb && (
              <button
                onClick={onPickFromDb}
                style={{
                  fontSize: 11, padding: '2px 8px', background: '#e5e7eb',
                  border: 'none', borderRadius: 4, cursor: 'pointer', color: '#333',
                }}
              >
                Pick
              </button>
            )}
            {onAiGenerate && (
              <button
                onClick={onAiGenerate}
                style={{
                  fontSize: 11, padding: '2px 8px', background: '#dbeafe',
                  border: 'none', borderRadius: 4, cursor: 'pointer', color: '#1d4ed8',
                }}
              >
                AI
              </button>
            )}
          </div>
        )}
      </div>
    </BlockWrapper>
  );
}
