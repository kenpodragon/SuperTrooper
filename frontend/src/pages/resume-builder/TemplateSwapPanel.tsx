import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { templates as templatesApi, templateThumbnailUrl } from '../../api/client';

interface Props {
  currentTemplateId: number;
  onSelect: (templateId: number) => void;
  onClose: () => void;
}

export default function TemplateSwapPanel({ currentTemplateId, onSelect, onClose }: Props) {
  const [selected, setSelected] = useState<number>(currentTemplateId);

  const { data: rawData } = useQuery({
    queryKey: ['templates'],
    queryFn: () => templatesApi.list(),
  });

  // Normalize: ResumeBuilder caches {templates: [...]} for same key, we need the array
  const templateList = Array.isArray(rawData) ? rawData : (rawData as any)?.templates ?? [];
  const activeTemplates = templateList.filter((t: any) => t.is_active !== false);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.2)', zIndex: 40 }}
      />
      {/* Panel */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: 280,
        background: 'white', borderLeft: '2px solid #3b82f6',
        boxShadow: '-4px 0 12px rgba(0,0,0,0.08)', zIndex: 50,
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid #e5e7eb' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Change Template</h3>
            <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, cursor: 'pointer', color: '#9ca3af' }}>&times;</button>
          </div>
          <p style={{ fontSize: 12, color: '#6b7280', marginTop: 4, marginBottom: 0 }}>Select a new layout design</p>
        </div>

        {/* Template list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {activeTemplates.map((t) => {
            const isCurrent = t.id === currentTemplateId;
            const isSelected = t.id === selected;
            return (
              <div
                key={t.id}
                onClick={() => setSelected(t.id)}
                style={{
                  border: `2px solid ${isSelected ? '#3b82f6' : '#e5e7eb'}`,
                  borderRadius: 8, padding: 8, cursor: 'pointer',
                  background: isSelected ? '#f0f7ff' : 'white',
                  transition: 'border-color 0.15s',
                }}
              >
                <div style={{
                  height: 60, background: '#f9fafb', borderRadius: 4,
                  marginBottom: 6, display: 'flex', alignItems: 'center',
                  justifyContent: 'center', overflow: 'hidden',
                }}>
                  {t.has_thumbnail ? (
                    <img
                      src={templateThumbnailUrl(t.id)}
                      alt={t.name}
                      style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }}
                    />
                  ) : (
                    <span style={{ fontSize: 24, color: '#d1d5db' }}>&#128196;</span>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 500, color: '#111' }}>{t.name}</span>
                  {isCurrent && (
                    <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 8, background: '#dbeafe', color: '#1d4ed8' }}>Current</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div style={{ padding: 12, borderTop: '1px solid #e5e7eb', display: 'flex', gap: 8 }}>
          <button
            onClick={onClose}
            style={{ flex: 1, padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, cursor: 'pointer', background: 'white' }}
          >
            Cancel
          </button>
          <button
            onClick={() => { if (selected !== currentTemplateId) onSelect(selected); }}
            disabled={selected === currentTemplateId}
            style={{
              flex: 1, padding: '8px 12px', borderRadius: 6, fontSize: 13,
              cursor: selected === currentTemplateId ? 'not-allowed' : 'pointer',
              border: 'none', background: '#1e293b', color: 'white',
              opacity: selected === currentTemplateId ? 0.5 : 1,
            }}
          >
            Apply Template
          </button>
        </div>
      </div>
    </>
  );
}
