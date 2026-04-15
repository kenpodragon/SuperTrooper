import { useState } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

interface BulletRef {
  ref?: string;
  id?: number;
  literal?: string;
}

interface Props {
  bullet: BulletRef;
  resolvedText: string;
  index: number;
  sortableId: string;
  onEdit: (text: string) => void;
  onClone: () => void;
  onDelete: () => void;
  onAiRewrite?: () => void;
}

export default function BulletItem({
  bullet, resolvedText, sortableId,
  onEdit, onClone, onDelete, onAiRewrite,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(resolvedText);
  const [showMenu, setShowMenu] = useState(false);

  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: sortableId });
  const style = { transform: CSS.Transform.toString(transform), transition };

  const handleBlur = () => {
    setEditing(false);
    if (text !== resolvedText) {
      onEdit(text);
    }
  };

  return (
    <li
      ref={setNodeRef}
      style={{ ...style, display: 'flex', alignItems: 'flex-start', gap: 4, position: 'relative', marginBottom: 2 }}
      className="group/bullet"
    >
      {/* Drag handle */}
      <span
        {...attributes} {...listeners}
        style={{ cursor: 'grab', color: '#d1d5db', marginTop: 2, userSelect: 'none', fontSize: 12, flexShrink: 0 }}
      >
        &#x2807;
      </span>

      {editing ? (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={handleBlur}
          autoFocus
          style={{
            flex: 1, background: '#fefce8', border: '1px solid #d4a017',
            borderRadius: 3, padding: 4, fontSize: 'var(--font-size-body, 10.5pt)',
            fontFamily: 'inherit', resize: 'vertical', minHeight: 32, outline: 'none',
            color: '#111', lineHeight: 1.4,
          }}
        />
      ) : (
        <span
          onClick={() => setEditing(true)}
          style={{
            flex: 1, fontSize: 'var(--font-size-body, 10.5pt)', color: '#222',
            cursor: 'pointer', padding: '0 2px', borderRadius: 2, lineHeight: 1.5,
          }}
        >
          {resolvedText || <span style={{ color: '#aaa', fontStyle: 'italic' }}>[empty bullet]</span>}
        </span>
      )}

      {/* Context menu */}
      <div style={{ position: 'relative', flexShrink: 0 }}>
        <button
          onClick={() => setShowMenu(!showMenu)}
          style={{
            background: 'none', border: 'none', color: '#bbb', fontSize: 14,
            cursor: 'pointer', display: 'none', padding: 0,
          }}
          className="group-hover/bullet:!inline-block"
        >
          &hellip;
        </button>
        {showMenu && (
          <div style={{
            position: 'absolute', right: 0, top: 20, zIndex: 10,
            background: '#fff', border: '1px solid #e2e8f0', borderRadius: 6,
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)', padding: '4px 0', minWidth: 120,
          }}>
            <MenuBtn label="Edit" onClick={() => { setShowMenu(false); setEditing(true); }} />
            <MenuBtn label="Clone & Edit" onClick={() => { setShowMenu(false); onClone(); }} />
            {onAiRewrite && (
              <MenuBtn label="AI Rewrite" onClick={() => { setShowMenu(false); onAiRewrite(); }} color="#2563eb" />
            )}
            <MenuBtn label="Delete" onClick={() => { setShowMenu(false); onDelete(); }} color="#ef4444" />
          </div>
        )}
      </div>
    </li>
  );
}

function MenuBtn({ label, onClick, color }: { label: string; onClick: () => void; color?: string }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'block', width: '100%', textAlign: 'left', padding: '6px 12px',
        fontSize: 12, background: 'none', border: 'none', cursor: 'pointer',
        color: color ?? '#333',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = '#f5f5f5')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
    >
      {label}
    </button>
  );
}
