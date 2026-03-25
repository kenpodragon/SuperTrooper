import { useState, type ReactNode } from 'react';

interface Props {
  label: string;
  children: ReactNode;
  className?: string;
}

export default function BlockWrapper({ label, children, className = '' }: Props) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      className={`relative group ${className}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {hovered && (
        <div className="absolute -top-6 left-0 text-xs text-blue-400 bg-gray-900 px-2 py-0.5 rounded z-10">
          {label}
        </div>
      )}
      <div className={`border transition-colors rounded px-4 py-3 ${
        hovered ? 'border-blue-500/50' : 'border-transparent'
      }`}>
        {children}
      </div>
    </div>
  );
}
