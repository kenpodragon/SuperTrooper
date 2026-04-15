import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api/client';
import BlockWrapper from './BlockWrapper';

interface SkillRef {
  ref?: string;
  ids?: number[];
  literal?: string;
}

interface SkillRow {
  id: number;
  name: string;
}

interface Props {
  skillRefs: SkillRef[];
  resolvedSkills: string[];
  onUpdate: (updatedRefs: SkillRef[]) => void;
}

export default function SkillTagsBlock({ skillRefs, resolvedSkills, onUpdate }: Props) {
  const [showPicker, setShowPicker] = useState(false);
  const [search, setSearch] = useState('');

  const { data: allSkillsData } = useQuery({
    queryKey: ['all-skills'],
    queryFn: () => api.get<{ skills: SkillRow[] }>('/skills?limit=500'),
    enabled: showPicker,
  });
  const allSkills = allSkillsData?.skills ?? [];

  const currentIds = new Set(skillRefs.flatMap(r => r.ids ?? []));

  const filtered = allSkills.filter(
    s => !currentIds.has(s.id) && s.name.toLowerCase().includes(search.toLowerCase())
  );

  const addSkill = (skillId: number) => {
    if (skillRefs.length > 0 && skillRefs[0].ids) {
      const updated = [...skillRefs];
      updated[0] = { ...updated[0], ids: [...(updated[0].ids ?? []), skillId] };
      onUpdate(updated);
    } else {
      onUpdate([{ ref: 'skills', ids: [...Array.from(currentIds), skillId] }]);
    }
    setSearch('');
  };

  const removeSkill = (skillId: number) => {
    const updated = skillRefs.map(r => {
      if (r.ids) {
        return { ...r, ids: r.ids.filter(id => id !== skillId) };
      }
      return r;
    }).filter(r => (r.ids?.length ?? 0) > 0 || r.literal);
    onUpdate(updated);
  };

  return (
    <BlockWrapper label="Skills">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, fontSize: 'var(--font-size-body, 10.5pt)' }}>
        {resolvedSkills.map((skill, idx) => {
          const skillId = skillRefs.flatMap(r => r.ids ?? [])[idx];
          return (
            <span
              key={idx}
              className="group/tag"
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                padding: '2px 10px', background: '#f1f5f9', borderRadius: 12,
                fontSize: '9.5pt', color: '#334155', border: '1px solid #e2e8f0',
              }}
            >
              {skill}
              {skillId && (
                <button
                  onClick={() => removeSkill(skillId)}
                  style={{
                    background: 'none', border: 'none', color: '#94a3b8',
                    cursor: 'pointer', fontSize: 12, padding: 0, display: 'none',
                  }}
                  className="group-hover/tag:!inline"
                >
                  &times;
                </button>
              )}
            </span>
          );
        })}
        <button
          onClick={() => setShowPicker(!showPicker)}
          style={{
            padding: '2px 10px', border: '1px dashed #cbd5e1', borderRadius: 12,
            fontSize: '9.5pt', color: '#64748b', background: 'none', cursor: 'pointer',
          }}
        >
          + Add
        </button>
      </div>
      {showPicker && (
        <div style={{
          marginTop: 10, border: '1px solid #e2e8f0', borderRadius: 6,
          padding: 10, maxHeight: 180, overflowY: 'auto', background: '#fafafa',
        }}>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search skills..."
            autoFocus
            style={{
              width: '100%', background: '#fff', border: '1px solid #e2e8f0',
              borderRadius: 4, fontSize: 12, outline: 'none', padding: '4px 8px',
              marginBottom: 8,
            }}
          />
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {filtered.slice(0, 30).map(s => (
              <button
                key={s.id}
                onClick={() => addSkill(s.id)}
                style={{
                  padding: '2px 8px', fontSize: 11, background: '#e2e8f0',
                  border: 'none', borderRadius: 4, cursor: 'pointer', color: '#334155',
                }}
              >
                {s.name}
              </button>
            ))}
            {filtered.length === 0 && <p style={{ fontSize: 11, color: '#999' }}>No matching skills</p>}
          </div>
        </div>
      )}
    </BlockWrapper>
  );
}
