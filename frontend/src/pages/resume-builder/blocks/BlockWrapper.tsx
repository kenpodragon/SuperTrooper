import { useState, type ReactNode } from 'react';

interface Props {
  label: string;
  children: ReactNode;
  className?: string;
  /** If true, show a resume-style section header (uppercase, underlined) */
  showHeader?: boolean;
}

export default function BlockWrapper({ label, children, className = '', showHeader = true }: Props) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      className={`relative group ${className}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ marginBottom: 4 }}
    >
      {/* Editor label tooltip — only shows on hover */}
      {hovered && (
        <div style={{
          position: 'absolute', top: -20, right: 0, fontSize: 10,
          color: '#3b82f6', background: '#f0f7ff', padding: '2px 8px',
          borderRadius: 4, zIndex: 10, border: '1px solid #bfdbfe',
        }}>
          Click to edit
        </div>
      )}

      {/* Resume-style section header */}
      {showHeader && label !== 'Header' && (
        <div style={{
          fontSize: 'var(--font-size-heading, 13pt)',
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: 'var(--accent-color, #1e3a5f)',
          borderBottom: '2px solid var(--accent-color, #1e3a5f)',
          paddingBottom: 3,
          marginBottom: 8,
          marginTop: 12,
        }}>
          {label}
        </div>
      )}

      <div style={{
        borderRadius: 4,
        padding: '2px 4px',
        border: hovered ? '1px solid rgba(59, 130, 246, 0.3)' : '1px solid transparent',
        transition: 'border-color 0.15s',
      }}>
        {children}
      </div>
    </div>
  );
}
