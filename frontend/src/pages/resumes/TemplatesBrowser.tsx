import { useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { templates, templateThumbnailUrl } from '../../api/client';
import type { TemplateListItem } from '../../api/client';
import TemplateDetail from './TemplateDetail';

export default function TemplatesBrowser() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);

  const { data: templateList, isLoading } = useQuery({
    queryKey: ['templates'],
    queryFn: () => templates.list(),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => templates.del(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['templates'] });
      if (selectedId === deleteMut.variables) setSelectedId(null);
    },
    onError: (err: any) => alert(err?.message || 'Failed to delete template'),
  });

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await templates.upload(file);
      qc.invalidateQueries({ queryKey: ['templates'] });
    } catch (err: any) {
      alert(err?.message || 'Upload failed');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const confirmDelete = (t: TemplateListItem) => {
    const msg = t.recipe_count > 0
      ? `Delete template "${t.name}"? ${t.recipe_count} recipe(s) reference it.`
      : `Delete template "${t.name}"?`;
    if (confirm(msg)) deleteMut.mutate(t.id);
  };

  // Detail view
  if (selectedId != null) {
    return <TemplateDetail templateId={selectedId} onBack={() => setSelectedId(null)} />;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary, #111)' }}>Templates</h2>
        <div>
          <input
            ref={fileRef}
            type="file"
            accept=".docx"
            onChange={handleUpload}
            style={{ display: 'none' }}
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            style={{
              padding: '8px 16px',
              background: 'var(--btn-primary-bg, #111)',
              color: 'var(--btn-primary-text, #fff)',
              border: 'none',
              borderRadius: 6,
              fontSize: 14,
              cursor: uploading ? 'wait' : 'pointer',
              opacity: uploading ? 0.6 : 1,
            }}
          >
            {uploading ? 'Uploading...' : 'Upload Template'}
          </button>
        </div>
      </div>

      {isLoading && <p style={{ fontSize: 14, color: '#999' }}>Loading templates...</p>}

      {!isLoading && (!templateList || templateList.length === 0) && (
        <div style={{
          padding: 40,
          textAlign: 'center',
          background: 'var(--card-bg, #fff)',
          border: '1px solid var(--border, #e5e7eb)',
          borderRadius: 8,
        }}>
          <p style={{ fontSize: 14, color: '#999' }}>No templates yet. Upload a .docx resume to create one.</p>
        </div>
      )}

      {templateList && templateList.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: 16,
        }}>
          {templateList.map((t) => (
            <TemplateCard
              key={t.id}
              template={t}
              onClick={() => setSelectedId(t.id)}
              onDelete={() => confirmDelete(t)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function TemplateCard({
  template: t,
  onClick,
  onDelete,
}: {
  template: TemplateListItem;
  onClick: () => void;
  onDelete: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const [imgError, setImgError] = useState(false);

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: 'var(--card-bg, #fff)',
        border: `1px solid ${hovered ? 'var(--accent, #3b82f6)' : 'var(--border, #e5e7eb)'}`,
        borderRadius: 8,
        overflow: 'hidden',
        cursor: 'pointer',
        transition: 'border-color 0.15s, box-shadow 0.15s',
        boxShadow: hovered ? '0 4px 12px rgba(0,0,0,0.08)' : 'none',
      }}
    >
      {/* Thumbnail */}
      <div style={{
        height: 160,
        background: 'var(--bg-muted, #f9fafb)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
      }}>
        {t.has_thumbnail && !imgError ? (
          <img
            src={templateThumbnailUrl(t.id)}
            alt={`${t.name} preview`}
            onError={() => setImgError(true)}
            style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }}
          />
        ) : (
          <div style={{ fontSize: 36, color: '#d1d5db' }}>&#128196;</div>
        )}
      </div>

      {/* Info */}
      <div style={{ padding: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary, #111)', margin: 0 }}>
            {t.name}
          </h3>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            style={{
              background: 'none',
              border: 'none',
              color: '#ef4444',
              cursor: 'pointer',
              fontSize: 12,
              padding: '2px 6px',
              borderRadius: 4,
            }}
            title="Delete template"
          >
            Del
          </button>
        </div>

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
          {t.template_type && (
            <span style={{
              fontSize: 11,
              padding: '2px 8px',
              borderRadius: 12,
              background: t.template_type === 'full' ? '#dbeafe' : '#f3e8ff',
              color: t.template_type === 'full' ? '#1d4ed8' : '#7c3aed',
            }}>
              {t.template_type}
            </span>
          )}
          {t.parser_version && (
            <span style={{
              fontSize: 11,
              padding: '2px 8px',
              borderRadius: 12,
              background: '#f0fdf4',
              color: '#15803d',
            }}>
              v{t.parser_version}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: '#6b7280' }}>
            {t.recipe_count} recipe{t.recipe_count !== 1 ? 's' : ''}
          </span>
          <span style={{ fontSize: 11, color: '#9ca3af' }}>
            {t.created_at ? new Date(t.created_at).toLocaleDateString() : ''}
          </span>
        </div>
      </div>
    </div>
  );
}
