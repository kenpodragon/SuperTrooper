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

  const editableField = (field: keyof HeaderData, className: string) => (
    <span
      key={field}
      contentEditable={editing === field}
      suppressContentEditableWarning
      onClick={() => setEditing(field)}
      onBlur={() => handleBlur(field)}
      onInput={(e) => setValues(v => ({ ...v, [field]: (e.target as HTMLElement).textContent ?? '' }))}
      className={`${className} ${editing === field ? 'outline-none ring-1 ring-blue-500 rounded px-1' : 'cursor-pointer hover:bg-gray-800/50 rounded px-1'}`}
    >
      {values[field] || `[${field}]`}
    </span>
  );

  const nameStyle = themeVars?.['--font-size-name'] ? { fontSize: themeVars['--font-size-name'] } : {};
  const alignClass = themeVars?.['--header-alignment'] === 'center' ? 'text-center' : 'text-left';

  return (
    <BlockWrapper label="Header">
      <div className={alignClass}>
        <div style={nameStyle} className="font-bold text-xl">
          {editableField('full_name', 'text-xl font-bold')}
          {values.credentials && <>, {editableField('credentials', 'text-lg')}</>}
        </div>
        <div className="text-sm text-gray-400 mt-1 space-x-2">
          {editableField('location', 'text-sm')}
          <span className="text-gray-600">&bull;</span>
          {editableField('email', 'text-sm')}
          <span className="text-gray-600">&bull;</span>
          {editableField('phone', 'text-sm')}
          {values.linkedin_url && (
            <>
              <span className="text-gray-600">&bull;</span>
              {editableField('linkedin_url', 'text-sm')}
            </>
          )}
        </div>
      </div>
    </BlockWrapper>
  );
}
