import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../../api/client';
import BlockWrapper from './BlockWrapper';

interface HeaderData {
  full_name?: string;
  credentials?: string;
  location?: string;
  location_note?: string;
  email?: string;
  phone?: string;
  linkedin_url?: string;
  // v1 resolved format (from _v1_resolved_to_v2)
  name?: string;
  contact?: string;
}

interface Props {
  data: HeaderData;
  headerId: number;
  themeVars?: Record<string, string>;
}

export default function HeaderBlock({ data, headerId, themeVars }: Props) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const [values, setValues] = useState<HeaderData>(data);

  const saveMutation = useMutation({
    mutationFn: (updates: Partial<HeaderData>) =>
      api.put(`/resume/header/${headerId}`, updates),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['recipe-builder'] }),
  });

  const handleBlur = (field: keyof HeaderData) => {
    setEditing(null);
    if (values[field] !== data[field]) {
      saveMutation.mutate({ [field]: values[field] });
    }
  };

  const editableField = (field: keyof HeaderData, style: React.CSSProperties = {}) => (
    <span
      key={field}
      contentEditable={editing === field}
      suppressContentEditableWarning
      onClick={() => setEditing(field)}
      onBlur={() => handleBlur(field)}
      onInput={(e) => setValues(v => ({ ...v, [field]: (e.target as HTMLElement).textContent ?? '' }))}
      style={{
        outline: editing === field ? '1px solid rgba(59,130,246,0.5)' : 'none',
        borderRadius: 2,
        padding: '0 2px',
        cursor: 'pointer',
        ...style,
      }}
    >
      {values[field] || `[${field}]`}
    </span>
  );

  const alignment = themeVars?.['--header-alignment'] ?? 'center';

  // Detect v1 format (name + contact strings) vs v2 format (full_name, email, etc.)
  const isV1 = !!(data.name || data.contact) && !data.full_name;

  if (isV1) {
    return (
      <BlockWrapper label="Header" showHeader={false}>
        <div style={{ textAlign: alignment as any, marginBottom: 12 }}>
          <div style={{
            fontSize: 'var(--font-size-name, 22pt)',
            fontWeight: 700,
            color: '#111',
            lineHeight: 1.2,
            marginBottom: 4,
          }}>
            {data.name || '[Name]'}
          </div>
          {data.contact && (
            <div style={{ fontSize: '9pt', color: '#555' }}>
              {data.contact}
            </div>
          )}
        </div>
      </BlockWrapper>
    );
  }

  return (
    <BlockWrapper label="Header" showHeader={false}>
      <div style={{ textAlign: alignment as any, marginBottom: 12 }}>
        {/* Name line */}
        <div style={{
          fontSize: 'var(--font-size-name, 22pt)',
          fontWeight: 700,
          color: '#111',
          lineHeight: 1.2,
          marginBottom: 4,
        }}>
          {editableField('full_name')}
          {values.credentials && (
            <span style={{ fontWeight: 400, color: '#333' }}>
              , {editableField('credentials')}
            </span>
          )}
        </div>

        {/* Contact line */}
        <div style={{
          fontSize: '9pt',
          color: '#555',
          display: 'flex',
          justifyContent: alignment === 'center' ? 'center' : 'flex-start',
          flexWrap: 'wrap',
          gap: '4px 0',
        }}>
          {editableField('location', { color: '#555' })}
          {values.location_note && (
            <span style={{ color: '#777' }}> ({values.location_note})</span>
          )}
          <span style={{ margin: '0 6px', color: '#999' }}>&bull;</span>
          {editableField('email', { color: '#555' })}
          <span style={{ margin: '0 6px', color: '#999' }}>&bull;</span>
          {editableField('phone', { color: '#555' })}
          {values.linkedin_url && (
            <>
              <span style={{ margin: '0 6px', color: '#999' }}>&bull;</span>
              {editableField('linkedin_url', { color: '#2563eb' })}
            </>
          )}
        </div>
      </div>
    </BlockWrapper>
  );
}
