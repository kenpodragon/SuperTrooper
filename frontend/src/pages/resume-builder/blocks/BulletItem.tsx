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
    <li ref={setNodeRef} style={style} className="flex items-start gap-2 group/bullet relative">
      <span {...attributes} {...listeners} className="cursor-grab text-gray-600 hover:text-gray-400 mt-1 select-none">&#x2807;</span>
      <span className="text-gray-500 mt-0.5">&bull;</span>
      {editing ? (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={handleBlur}
          autoFocus
          className="flex-1 bg-transparent border border-blue-500/30 rounded p-1 text-sm resize-y min-h-8 outline-none"
        />
      ) : (
        <span
          onClick={() => setEditing(true)}
          className="flex-1 text-sm cursor-pointer hover:bg-gray-800/50 rounded px-1 py-0.5"
        >
          {resolvedText || <span className="text-gray-500 italic">[empty bullet]</span>}
        </span>
      )}
      <div className="relative">
        <button
          onClick={() => setShowMenu(!showMenu)}
          className="text-gray-600 hover:text-gray-300 text-sm hidden group-hover/bullet:block"
        >
          &hellip;
        </button>
        {showMenu && (
          <div className="absolute right-0 top-6 z-10 bg-gray-800 border border-gray-700 rounded shadow-lg py-1 min-w-32">
            <button onClick={() => { setShowMenu(false); setEditing(true); }}
              className="block w-full text-left px-3 py-1.5 text-sm hover:bg-gray-700">Edit</button>
            <button onClick={() => { setShowMenu(false); onClone(); }}
              className="block w-full text-left px-3 py-1.5 text-sm hover:bg-gray-700">Clone &amp; Edit</button>
            {onAiRewrite && (
              <button onClick={() => { setShowMenu(false); onAiRewrite(); }}
                className="block w-full text-left px-3 py-1.5 text-sm text-blue-400 hover:bg-gray-700">AI Rewrite</button>
            )}
            <button onClick={() => { setShowMenu(false); onDelete(); }}
              className="block w-full text-left px-3 py-1.5 text-sm text-red-400 hover:bg-gray-700">Delete</button>
          </div>
        )}
      </div>
    </li>
  );
}
