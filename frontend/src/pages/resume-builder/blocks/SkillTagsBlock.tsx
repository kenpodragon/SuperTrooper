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
      <div className="flex flex-wrap gap-2">
        {resolvedSkills.map((skill, idx) => {
          const skillId = skillRefs.flatMap(r => r.ids ?? [])[idx];
          return (
            <span key={idx} className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-800 rounded-full text-sm group/tag">
              {skill}
              {skillId && (
                <button onClick={() => removeSkill(skillId)} className="text-gray-600 hover:text-red-400 hidden group-hover/tag:inline">
                  &times;
                </button>
              )}
            </span>
          );
        })}
        <button
          onClick={() => setShowPicker(!showPicker)}
          className="px-2 py-0.5 border border-dashed border-gray-600 rounded-full text-sm text-gray-400 hover:border-blue-500 hover:text-blue-400"
        >
          + Add
        </button>
      </div>
      {showPicker && (
        <div className="mt-3 border border-gray-700 rounded p-3 max-h-48 overflow-y-auto">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search skills..."
            autoFocus
            className="w-full bg-transparent border-b border-gray-700 text-sm outline-none pb-2 mb-2"
          />
          <div className="flex flex-wrap gap-1">
            {filtered.slice(0, 30).map(s => (
              <button key={s.id} onClick={() => addSkill(s.id)} className="px-2 py-0.5 text-xs bg-gray-700 rounded hover:bg-blue-700">
                {s.name}
              </button>
            ))}
            {filtered.length === 0 && <p className="text-xs text-gray-500">No matching skills</p>}
          </div>
        </div>
      )}
    </BlockWrapper>
  );
}
