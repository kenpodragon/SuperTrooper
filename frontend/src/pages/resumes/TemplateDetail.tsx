import { useQuery } from '@tanstack/react-query';
import { templates, templateThumbnailUrl } from '../../api/client';
import type { TemplateSlot } from '../../api/client';

interface Props {
  templateId: number;
  onBack: () => void;
}

export default function TemplateDetail({ templateId, onBack }: Props) {
  const { data: detail, isLoading } = useQuery({
    queryKey: ['template-detail', templateId],
    queryFn: () => templates.get(templateId),
  });

  if (isLoading) {
    return (
      <div>
        <button onClick={onBack} style={backBtnStyle}>&larr; Back to Templates</button>
        <p style={{ fontSize: 14, color: '#999' }}>Loading template...</p>
      </div>
    );
  }

  if (!detail) {
    return (
      <div>
        <button onClick={onBack} style={backBtnStyle}>&larr; Back to Templates</button>
        <p style={{ fontSize: 14, color: '#ef4444' }}>Template not found.</p>
      </div>
    );
  }

  // Parse template_map into slot entries
  const slots = parseSlots(detail.template_map);
  const grouped = groupBySection(slots);

  return (
    <div>
      <button onClick={onBack} style={backBtnStyle}>&larr; Back to Templates</button>

      {/* Header */}
      <div style={{
        display: 'flex',
        gap: 24,
        marginTop: 16,
        background: 'var(--card-bg, #fff)',
        border: '1px solid var(--border, #e5e7eb)',
        borderRadius: 8,
        padding: 16,
      }}>
        {/* Thumbnail */}
        <div style={{
          width: 140,
          minHeight: 180,
          background: 'var(--bg-muted, #f9fafb)',
          borderRadius: 6,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
          flexShrink: 0,
        }}>
          {detail.has_thumbnail ? (
            <img
              src={templateThumbnailUrl(detail.id)}
              alt={`${detail.name} preview`}
              style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
            />
          ) : (
            <span style={{ fontSize: 48, color: '#d1d5db' }}>&#128196;</span>
          )}
        </div>

        {/* Info */}
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary, #111)', margin: '0 0 8px' }}>
            {detail.name}
          </h2>
          {detail.description && (
            <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 12 }}>{detail.description}</p>
          )}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            {detail.template_type && (
              <Badge bg="#dbeafe" color="#1d4ed8">{detail.template_type}</Badge>
            )}
            {detail.parser_version && (
              <Badge bg="#f0fdf4" color="#15803d">v{detail.parser_version}</Badge>
            )}
            {detail.is_active && (
              <Badge bg="#dcfce7" color="#166534">Active</Badge>
            )}
          </div>
          <div style={{ fontSize: 12, color: '#9ca3af' }}>
            {detail.filename && <span>File: {detail.filename} &middot; </span>}
            {detail.size_bytes && <span>{(detail.size_bytes / 1024).toFixed(1)} KB &middot; </span>}
            {detail.created_at && <span>Created {new Date(detail.created_at).toLocaleDateString()}</span>}
          </div>
        </div>
      </div>

      {/* Slot Map */}
      <div style={{
        marginTop: 16,
        background: 'var(--card-bg, #fff)',
        border: '1px solid var(--border, #e5e7eb)',
        borderRadius: 8,
        padding: 16,
      }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary, #111)', margin: '0 0 12px' }}>
          Slot Map ({slots.length} slots)
        </h3>
        {slots.length === 0 && (
          <p style={{ fontSize: 13, color: '#9ca3af' }}>No template_map data available for this template.</p>
        )}
        {Object.entries(grouped).map(([section, sectionSlots]) => (
          <div key={section} style={{ marginBottom: 12 }}>
            <p style={{
              fontSize: 12,
              fontWeight: 600,
              color: '#6b7280',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: 6,
            }}>
              {section}
            </p>
            {sectionSlots.map((s, i) => (
              <div key={i} style={{
                padding: '6px 0',
                borderBottom: '1px solid var(--border-light, #f3f4f6)',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}>
                <code style={{
                  fontSize: 12,
                  background: 'var(--bg-muted, #f9fafb)',
                  padding: '2px 6px',
                  borderRadius: 4,
                  color: '#4b5563',
                  flexShrink: 0,
                }}>
                  {s.placeholder}
                </code>
                {s.slot_type && (
                  <Badge bg="#fef3c7" color="#92400e">{s.slot_type}</Badge>
                )}
                {s.original_text && (
                  <span style={{ fontSize: 12, color: '#9ca3af', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {s.original_text.length > 80 ? s.original_text.slice(0, 80) + '...' : s.original_text}
                  </span>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Recipes referencing this template */}
      <div style={{
        marginTop: 16,
        background: 'var(--card-bg, #fff)',
        border: '1px solid var(--border, #e5e7eb)',
        borderRadius: 8,
        padding: 16,
      }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary, #111)', margin: '0 0 12px' }}>
          Recipes ({detail.recipes?.length || 0})
        </h3>
        {(!detail.recipes || detail.recipes.length === 0) && (
          <p style={{ fontSize: 13, color: '#9ca3af' }}>No recipes reference this template.</p>
        )}
        {detail.recipes?.map((r) => (
          <div key={r.id} style={{
            padding: '8px 0',
            borderBottom: '1px solid var(--border-light, #f3f4f6)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <div>
              <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary, #111)' }}>{r.name}</p>
              {r.description && <p style={{ fontSize: 12, color: '#9ca3af' }}>{r.description}</p>}
            </div>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              {r.is_active && <Badge bg="#dcfce7" color="#166534">Active</Badge>}
              <span style={{ fontSize: 11, color: '#9ca3af' }}>
                {r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Helpers ---

interface SlotEntry {
  placeholder: string;
  slot_type?: string;
  original_text?: string;
  parent_section?: string;
}

function parseSlots(templateMap: unknown): SlotEntry[] {
  if (!templateMap) return [];
  if (Array.isArray(templateMap)) {
    return templateMap.map((s: any) => ({
      placeholder: s.placeholder || s.name || '(unnamed)',
      slot_type: s.slot_type || s.type,
      original_text: s.original_text || s.original,
      parent_section: s.parent_section || s.section || 'General',
    }));
  }
  if (typeof templateMap === 'object') {
    return Object.entries(templateMap as Record<string, any>).map(([key, val]) => ({
      placeholder: key,
      slot_type: val?.slot_type || val?.type,
      original_text: val?.original_text || val?.original || (typeof val === 'string' ? val : undefined),
      parent_section: val?.parent_section || val?.section || 'General',
    }));
  }
  return [];
}

function groupBySection(slots: SlotEntry[]): Record<string, SlotEntry[]> {
  const groups: Record<string, SlotEntry[]> = {};
  for (const s of slots) {
    const section = s.parent_section || 'General';
    if (!groups[section]) groups[section] = [];
    groups[section].push(s);
  }
  return groups;
}

function Badge({ bg, color, children }: { bg: string; color: string; children: React.ReactNode }) {
  return (
    <span style={{
      fontSize: 11,
      padding: '2px 8px',
      borderRadius: 12,
      background: bg,
      color,
      fontWeight: 500,
      whiteSpace: 'nowrap',
    }}>
      {children}
    </span>
  );
}

const backBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: '#3b82f6',
  cursor: 'pointer',
  fontSize: 13,
  padding: 0,
};
