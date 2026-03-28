import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

// ---- Types ----

interface Skill {
  id: number;
  name: string;
  category?: string;
  proficiency?: string;
  last_used_year?: number;
}

interface Education {
  id: number;
  degree: string;
  field?: string;
  institution?: string;
  location?: string;
  type?: string;
  sort_order?: number;
}

interface Certification {
  id: number;
  name: string;
  issuer?: string;
  is_active?: boolean;
  sort_order?: number;
}

interface Language {
  id: number;
  name: string;
  proficiency?: string;
}

interface SummaryVariant {
  id: number;
  role_type: string;
  text?: string;
}

interface Reference {
  id: number;
  name: string;
  title?: string;
  company?: string;
  relationship?: string;
  email?: string;
  phone?: string;
  linkedin_url?: string;
  notes?: string;
  ok_to_contact?: boolean;
  career_history_id?: number;
}

type TabKey = 'skills' | 'education' | 'certifications' | 'languages' | 'references' | 'summaries';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'skills', label: 'Skills' },
  { key: 'education', label: 'Education' },
  { key: 'certifications', label: 'Certifications' },
  { key: 'languages', label: 'Languages' },
  { key: 'references', label: 'References' },
  { key: 'summaries', label: 'Summaries' },
];

const PROFICIENCY_LEVELS = ['beginner', 'intermediate', 'advanced', 'expert'];
const EDUCATION_TYPES = ['degree', 'certificate', 'diploma'];
const LANGUAGE_LEVELS = ['native', 'fluent', 'professional', 'conversational', 'basic'];

// ---- Shared styles ----

const styles = {
  table: { width: '100%', borderCollapse: 'collapse' as const },
  th: {
    textAlign: 'left' as const, padding: '8px 12px', fontSize: '12px',
    fontWeight: 600, color: '#94a3b8', borderBottom: '1px solid #334155',
    textTransform: 'uppercase' as const, letterSpacing: '0.05em',
  },
  td: { padding: '8px 12px', fontSize: '14px', borderBottom: '1px solid #1e293b' },
  input: {
    background: '#1e293b', border: '1px solid #334155', borderRadius: '4px',
    padding: '6px 10px', color: '#e2e8f0', fontSize: '14px', width: '100%',
    outline: 'none',
  },
  select: {
    background: '#1e293b', border: '1px solid #334155', borderRadius: '4px',
    padding: '6px 10px', color: '#e2e8f0', fontSize: '14px', width: '100%',
    outline: 'none',
  },
  textarea: {
    background: '#1e293b', border: '1px solid #334155', borderRadius: '4px',
    padding: '6px 10px', color: '#e2e8f0', fontSize: '14px', width: '100%',
    minHeight: '80px', outline: 'none', resize: 'vertical' as const,
  },
  btnPrimary: {
    background: '#3b82f6', color: '#fff', border: 'none', borderRadius: '4px',
    padding: '6px 16px', fontSize: '13px', cursor: 'pointer', fontWeight: 500,
  },
  btnDanger: {
    background: 'transparent', color: '#ef4444', border: '1px solid #ef4444',
    borderRadius: '4px', padding: '4px 10px', fontSize: '12px', cursor: 'pointer',
  },
  btnGhost: {
    background: 'transparent', color: '#94a3b8', border: '1px solid #475569',
    borderRadius: '4px', padding: '4px 10px', fontSize: '12px', cursor: 'pointer',
  },
  row: { transition: 'background 0.15s' },
};

// ---- Generic inline-edit row helpers ----

function useTabCrud<T extends { id: number }>(endpoint: string, queryKey: string, dataKey?: string) {
  const qc = useQueryClient();
  const { data = [], isLoading } = useQuery<T[]>({
    queryKey: [queryKey],
    queryFn: async () => {
      const res = await api.get<any>(endpoint);
      if (dataKey && res?.[dataKey]) return res[dataKey];
      return Array.isArray(res) ? res : [];
    },
  });
  const createMut = useMutation({
    mutationFn: (item: Partial<T>) => api.post<T>(endpoint, item),
    onSuccess: () => qc.invalidateQueries({ queryKey: [queryKey] }),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, ...rest }: Partial<T> & { id: number }) =>
      api.patch<T>(`${endpoint}/${id}`, rest),
    onSuccess: () => qc.invalidateQueries({ queryKey: [queryKey] }),
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => api.del(`${endpoint}/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: [queryKey] }),
  });
  return { data, isLoading, createMut, updateMut, deleteMut };
}

// ---- Skills Tab ----

function SkillsTab() {
  const { data, isLoading, createMut, updateMut, deleteMut } = useTabCrud<Skill>('/skills', 'kb-skills', 'skills');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Partial<Skill>>({});
  const [adding, setAdding] = useState(false);
  const [filterCat, setFilterCat] = useState('');

  const categories = useMemo(() => {
    const cats = new Set(data.map((s) => s.category).filter(Boolean));
    return Array.from(cats).sort() as string[];
  }, [data]);

  const filtered = filterCat ? data.filter((s) => s.category === filterCat) : data;

  const startEdit = (item: Skill) => { setEditingId(item.id); setDraft({ ...item }); setAdding(false); };
  const cancelEdit = () => { setEditingId(null); setDraft({}); setAdding(false); };
  const saveEdit = () => {
    if (adding) {
      createMut.mutate(draft as Partial<Skill>, { onSuccess: cancelEdit });
    } else if (editingId) {
      updateMut.mutate({ id: editingId, ...draft } as Partial<Skill> & { id: number }, { onSuccess: cancelEdit });
    }
  };
  const startAdd = () => { setAdding(true); setEditingId(null); setDraft({ proficiency: 'intermediate' }); };

  if (isLoading) return <p style={{ color: '#94a3b8', padding: 16 }}>Loading skills...</p>;

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16 }}>
        <button style={styles.btnPrimary} onClick={startAdd}>+ Add Skill</button>
        <select style={{ ...styles.select, width: 200 }} value={filterCat} onChange={(e) => setFilterCat(e.target.value)}>
          <option value="">All Categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <span style={{ color: '#64748b', fontSize: 13 }}>{filtered.length} skill{filtered.length !== 1 ? 's' : ''}</span>
      </div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>Name</th>
            <th style={styles.th}>Category</th>
            <th style={styles.th}>Proficiency</th>
            <th style={styles.th}>Last Used</th>
            <th style={{ ...styles.th, width: 120 }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {adding && (
            <tr style={{ background: '#1e293b' }}>
              <td style={styles.td}><input style={styles.input} placeholder="Skill name" value={draft.name || ''} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></td>
              <td style={styles.td}><input style={styles.input} placeholder="Category" value={draft.category || ''} onChange={(e) => setDraft({ ...draft, category: e.target.value })} /></td>
              <td style={styles.td}>
                <select style={styles.select} value={draft.proficiency || ''} onChange={(e) => setDraft({ ...draft, proficiency: e.target.value })}>
                  {PROFICIENCY_LEVELS.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </td>
              <td style={styles.td}><input style={{ ...styles.input, width: 80 }} type="number" placeholder="Year" value={draft.last_used_year || ''} onChange={(e) => setDraft({ ...draft, last_used_year: Number(e.target.value) || undefined })} /></td>
              <td style={styles.td}>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button style={styles.btnPrimary} onClick={saveEdit}>Save</button>
                  <button style={styles.btnGhost} onClick={cancelEdit}>Cancel</button>
                </div>
              </td>
            </tr>
          )}
          {filtered.map((item) => (
            <tr key={item.id} style={styles.row} onMouseEnter={(e) => (e.currentTarget.style.background = '#1e293b')} onMouseLeave={(e) => (e.currentTarget.style.background = '')}>
              {editingId === item.id ? (
                <>
                  <td style={styles.td}><input style={styles.input} value={draft.name || ''} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></td>
                  <td style={styles.td}><input style={styles.input} value={draft.category || ''} onChange={(e) => setDraft({ ...draft, category: e.target.value })} /></td>
                  <td style={styles.td}>
                    <select style={styles.select} value={draft.proficiency || ''} onChange={(e) => setDraft({ ...draft, proficiency: e.target.value })}>
                      {PROFICIENCY_LEVELS.map((p) => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </td>
                  <td style={styles.td}><input style={{ ...styles.input, width: 80 }} type="number" value={draft.last_used_year || ''} onChange={(e) => setDraft({ ...draft, last_used_year: Number(e.target.value) || undefined })} /></td>
                  <td style={styles.td}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button style={styles.btnPrimary} onClick={saveEdit}>Save</button>
                      <button style={styles.btnGhost} onClick={cancelEdit}>Cancel</button>
                    </div>
                  </td>
                </>
              ) : (
                <>
                  <td style={{ ...styles.td, color: '#e2e8f0' }}>{item.name}</td>
                  <td style={{ ...styles.td, color: '#94a3b8' }}>{item.category || '-'}</td>
                  <td style={{ ...styles.td, color: '#94a3b8' }}>{item.proficiency || '-'}</td>
                  <td style={{ ...styles.td, color: '#94a3b8' }}>{item.last_used_year || '-'}</td>
                  <td style={styles.td}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button style={styles.btnGhost} onClick={() => startEdit(item)}>Edit</button>
                      <button style={styles.btnDanger} onClick={() => { if (confirm(`Delete "${item.name}"?`)) deleteMut.mutate(item.id); }}>Del</button>
                    </div>
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {filtered.length === 0 && !adding && <p style={{ color: '#64748b', padding: 16, textAlign: 'center' }}>No skills found.</p>}
    </div>
  );
}

// ---- Education Tab ----

function EducationTab() {
  const { data, isLoading, createMut, updateMut, deleteMut } = useTabCrud<Education>('/education', 'kb-education', 'education');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Partial<Education>>({});
  const [adding, setAdding] = useState(false);

  const startEdit = (item: Education) => { setEditingId(item.id); setDraft({ ...item }); setAdding(false); };
  const cancelEdit = () => { setEditingId(null); setDraft({}); setAdding(false); };
  const saveEdit = () => {
    if (adding) {
      createMut.mutate(draft as Partial<Education>, { onSuccess: cancelEdit });
    } else if (editingId) {
      updateMut.mutate({ id: editingId, ...draft } as Partial<Education> & { id: number }, { onSuccess: cancelEdit });
    }
  };
  const startAdd = () => { setAdding(true); setEditingId(null); setDraft({ type: 'degree' }); };

  if (isLoading) return <p style={{ color: '#94a3b8', padding: 16 }}>Loading education...</p>;

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16 }}>
        <button style={styles.btnPrimary} onClick={startAdd}>+ Add Education</button>
        <span style={{ color: '#64748b', fontSize: 13 }}>{data.length} record{data.length !== 1 ? 's' : ''}</span>
      </div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>Degree</th>
            <th style={styles.th}>Field</th>
            <th style={styles.th}>Institution</th>
            <th style={styles.th}>Location</th>
            <th style={styles.th}>Type</th>
            <th style={styles.th}>Order</th>
            <th style={{ ...styles.th, width: 120 }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {adding && (
            <tr style={{ background: '#1e293b' }}>
              <td style={styles.td}><input style={styles.input} placeholder="Degree" value={draft.degree || ''} onChange={(e) => setDraft({ ...draft, degree: e.target.value })} /></td>
              <td style={styles.td}><input style={styles.input} placeholder="Field" value={draft.field || ''} onChange={(e) => setDraft({ ...draft, field: e.target.value })} /></td>
              <td style={styles.td}><input style={styles.input} placeholder="Institution" value={draft.institution || ''} onChange={(e) => setDraft({ ...draft, institution: e.target.value })} /></td>
              <td style={styles.td}><input style={styles.input} placeholder="Location" value={draft.location || ''} onChange={(e) => setDraft({ ...draft, location: e.target.value })} /></td>
              <td style={styles.td}>
                <select style={styles.select} value={draft.type || ''} onChange={(e) => setDraft({ ...draft, type: e.target.value })}>
                  {EDUCATION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </td>
              <td style={styles.td}><input style={{ ...styles.input, width: 60 }} type="number" value={draft.sort_order || ''} onChange={(e) => setDraft({ ...draft, sort_order: Number(e.target.value) || undefined })} /></td>
              <td style={styles.td}>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button style={styles.btnPrimary} onClick={saveEdit}>Save</button>
                  <button style={styles.btnGhost} onClick={cancelEdit}>Cancel</button>
                </div>
              </td>
            </tr>
          )}
          {data.map((item) => (
            <tr key={item.id} style={styles.row} onMouseEnter={(e) => (e.currentTarget.style.background = '#1e293b')} onMouseLeave={(e) => (e.currentTarget.style.background = '')}>
              {editingId === item.id ? (
                <>
                  <td style={styles.td}><input style={styles.input} value={draft.degree || ''} onChange={(e) => setDraft({ ...draft, degree: e.target.value })} /></td>
                  <td style={styles.td}><input style={styles.input} value={draft.field || ''} onChange={(e) => setDraft({ ...draft, field: e.target.value })} /></td>
                  <td style={styles.td}><input style={styles.input} value={draft.institution || ''} onChange={(e) => setDraft({ ...draft, institution: e.target.value })} /></td>
                  <td style={styles.td}><input style={styles.input} value={draft.location || ''} onChange={(e) => setDraft({ ...draft, location: e.target.value })} /></td>
                  <td style={styles.td}>
                    <select style={styles.select} value={draft.type || ''} onChange={(e) => setDraft({ ...draft, type: e.target.value })}>
                      {EDUCATION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </td>
                  <td style={styles.td}><input style={{ ...styles.input, width: 60 }} type="number" value={draft.sort_order || ''} onChange={(e) => setDraft({ ...draft, sort_order: Number(e.target.value) || undefined })} /></td>
                  <td style={styles.td}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button style={styles.btnPrimary} onClick={saveEdit}>Save</button>
                      <button style={styles.btnGhost} onClick={cancelEdit}>Cancel</button>
                    </div>
                  </td>
                </>
              ) : (
                <>
                  <td style={{ ...styles.td, color: '#e2e8f0' }}>{item.degree}</td>
                  <td style={{ ...styles.td, color: '#94a3b8' }}>{item.field || '-'}</td>
                  <td style={{ ...styles.td, color: '#94a3b8' }}>{item.institution || '-'}</td>
                  <td style={{ ...styles.td, color: '#94a3b8' }}>{item.location || '-'}</td>
                  <td style={{ ...styles.td, color: '#94a3b8' }}>{item.type || '-'}</td>
                  <td style={{ ...styles.td, color: '#94a3b8' }}>{item.sort_order ?? '-'}</td>
                  <td style={styles.td}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button style={styles.btnGhost} onClick={() => startEdit(item)}>Edit</button>
                      <button style={styles.btnDanger} onClick={() => { if (confirm(`Delete "${item.degree}"?`)) deleteMut.mutate(item.id); }}>Del</button>
                    </div>
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length === 0 && !adding && <p style={{ color: '#64748b', padding: 16, textAlign: 'center' }}>No education records.</p>}
    </div>
  );
}

// ---- Certifications Tab ----

function CertificationsTab() {
  const { data, isLoading, createMut, updateMut, deleteMut } = useTabCrud<Certification>('/certifications', 'kb-certifications', 'certifications');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Partial<Certification>>({});
  const [adding, setAdding] = useState(false);

  const startEdit = (item: Certification) => { setEditingId(item.id); setDraft({ ...item }); setAdding(false); };
  const cancelEdit = () => { setEditingId(null); setDraft({}); setAdding(false); };
  const saveEdit = () => {
    if (adding) {
      createMut.mutate(draft as Partial<Certification>, { onSuccess: cancelEdit });
    } else if (editingId) {
      updateMut.mutate({ id: editingId, ...draft } as Partial<Certification> & { id: number }, { onSuccess: cancelEdit });
    }
  };
  const startAdd = () => { setAdding(true); setEditingId(null); setDraft({ is_active: true }); };

  if (isLoading) return <p style={{ color: '#94a3b8', padding: 16 }}>Loading certifications...</p>;

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16 }}>
        <button style={styles.btnPrimary} onClick={startAdd}>+ Add Certification</button>
        <span style={{ color: '#64748b', fontSize: 13 }}>{data.length} certification{data.length !== 1 ? 's' : ''}</span>
      </div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>Name</th>
            <th style={styles.th}>Issuer</th>
            <th style={styles.th}>Active</th>
            <th style={styles.th}>Order</th>
            <th style={{ ...styles.th, width: 120 }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {adding && (
            <tr style={{ background: '#1e293b' }}>
              <td style={styles.td}><input style={styles.input} placeholder="Certification name" value={draft.name || ''} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></td>
              <td style={styles.td}><input style={styles.input} placeholder="Issuer" value={draft.issuer || ''} onChange={(e) => setDraft({ ...draft, issuer: e.target.value })} /></td>
              <td style={styles.td}>
                <input type="checkbox" checked={draft.is_active ?? true} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} />
              </td>
              <td style={styles.td}><input style={{ ...styles.input, width: 60 }} type="number" value={draft.sort_order || ''} onChange={(e) => setDraft({ ...draft, sort_order: Number(e.target.value) || undefined })} /></td>
              <td style={styles.td}>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button style={styles.btnPrimary} onClick={saveEdit}>Save</button>
                  <button style={styles.btnGhost} onClick={cancelEdit}>Cancel</button>
                </div>
              </td>
            </tr>
          )}
          {data.map((item) => (
            <tr key={item.id} style={styles.row} onMouseEnter={(e) => (e.currentTarget.style.background = '#1e293b')} onMouseLeave={(e) => (e.currentTarget.style.background = '')}>
              {editingId === item.id ? (
                <>
                  <td style={styles.td}><input style={styles.input} value={draft.name || ''} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></td>
                  <td style={styles.td}><input style={styles.input} value={draft.issuer || ''} onChange={(e) => setDraft({ ...draft, issuer: e.target.value })} /></td>
                  <td style={styles.td}>
                    <input type="checkbox" checked={draft.is_active ?? false} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} />
                  </td>
                  <td style={styles.td}><input style={{ ...styles.input, width: 60 }} type="number" value={draft.sort_order || ''} onChange={(e) => setDraft({ ...draft, sort_order: Number(e.target.value) || undefined })} /></td>
                  <td style={styles.td}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button style={styles.btnPrimary} onClick={saveEdit}>Save</button>
                      <button style={styles.btnGhost} onClick={cancelEdit}>Cancel</button>
                    </div>
                  </td>
                </>
              ) : (
                <>
                  <td style={{ ...styles.td, color: '#e2e8f0' }}>{item.name}</td>
                  <td style={{ ...styles.td, color: '#94a3b8' }}>{item.issuer || '-'}</td>
                  <td style={{ ...styles.td, color: item.is_active ? '#22c55e' : '#ef4444' }}>{item.is_active ? 'Yes' : 'No'}</td>
                  <td style={{ ...styles.td, color: '#94a3b8' }}>{item.sort_order ?? '-'}</td>
                  <td style={styles.td}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button style={styles.btnGhost} onClick={() => startEdit(item)}>Edit</button>
                      <button style={styles.btnDanger} onClick={() => { if (confirm(`Delete "${item.name}"?`)) deleteMut.mutate(item.id); }}>Del</button>
                    </div>
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length === 0 && !adding && <p style={{ color: '#64748b', padding: 16, textAlign: 'center' }}>No certifications.</p>}
    </div>
  );
}

// ---- Languages Tab ----

function LanguagesTab() {
  const { data, isLoading, createMut, updateMut, deleteMut } = useTabCrud<Language>('/languages', 'kb-languages', 'languages');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Partial<Language>>({});
  const [adding, setAdding] = useState(false);

  const startEdit = (item: Language) => { setEditingId(item.id); setDraft({ ...item }); setAdding(false); };
  const cancelEdit = () => { setEditingId(null); setDraft({}); setAdding(false); };
  const saveEdit = () => {
    if (adding) {
      createMut.mutate(draft as Partial<Language>, { onSuccess: cancelEdit });
    } else if (editingId) {
      updateMut.mutate({ id: editingId, ...draft } as Partial<Language> & { id: number }, { onSuccess: cancelEdit });
    }
  };
  const startAdd = () => { setAdding(true); setEditingId(null); setDraft({ proficiency: 'professional' }); };

  if (isLoading) return <p style={{ color: '#94a3b8', padding: 16 }}>Loading languages...</p>;

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16 }}>
        <button style={styles.btnPrimary} onClick={startAdd}>+ Add Language</button>
        <span style={{ color: '#64748b', fontSize: 13 }}>{data.length} language{data.length !== 1 ? 's' : ''}</span>
      </div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>Name</th>
            <th style={styles.th}>Proficiency</th>
            <th style={{ ...styles.th, width: 120 }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {adding && (
            <tr style={{ background: '#1e293b' }}>
              <td style={styles.td}><input style={styles.input} placeholder="Language" value={draft.name || ''} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></td>
              <td style={styles.td}>
                <select style={styles.select} value={draft.proficiency || ''} onChange={(e) => setDraft({ ...draft, proficiency: e.target.value })}>
                  {LANGUAGE_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
                </select>
              </td>
              <td style={styles.td}>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button style={styles.btnPrimary} onClick={saveEdit}>Save</button>
                  <button style={styles.btnGhost} onClick={cancelEdit}>Cancel</button>
                </div>
              </td>
            </tr>
          )}
          {data.map((item) => (
            <tr key={item.id} style={styles.row} onMouseEnter={(e) => (e.currentTarget.style.background = '#1e293b')} onMouseLeave={(e) => (e.currentTarget.style.background = '')}>
              {editingId === item.id ? (
                <>
                  <td style={styles.td}><input style={styles.input} value={draft.name || ''} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></td>
                  <td style={styles.td}>
                    <select style={styles.select} value={draft.proficiency || ''} onChange={(e) => setDraft({ ...draft, proficiency: e.target.value })}>
                      {LANGUAGE_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
                    </select>
                  </td>
                  <td style={styles.td}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button style={styles.btnPrimary} onClick={saveEdit}>Save</button>
                      <button style={styles.btnGhost} onClick={cancelEdit}>Cancel</button>
                    </div>
                  </td>
                </>
              ) : (
                <>
                  <td style={{ ...styles.td, color: '#e2e8f0' }}>{item.name}</td>
                  <td style={{ ...styles.td, color: '#94a3b8' }}>{item.proficiency || '-'}</td>
                  <td style={styles.td}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button style={styles.btnGhost} onClick={() => startEdit(item)}>Edit</button>
                      <button style={styles.btnDanger} onClick={() => { if (confirm(`Delete "${item.name}"?`)) deleteMut.mutate(item.id); }}>Del</button>
                    </div>
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length === 0 && !adding && <p style={{ color: '#64748b', padding: 16, textAlign: 'center' }}>No languages.</p>}
    </div>
  );
}

// ---- References Tab ----

const RELATIONSHIP_TYPES = ['former manager', 'peer', 'direct report', 'client', 'mentor', 'vendor', 'other'];

function ReferencesTab() {
  const { data, isLoading, createMut, updateMut, deleteMut } = useTabCrud<Reference>('/references', 'kb-references');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Partial<Reference>>({});
  const [adding, setAdding] = useState(false);

  const startEdit = (item: Reference) => { setEditingId(item.id); setDraft({ ...item }); setAdding(false); };
  const cancelEdit = () => { setEditingId(null); setDraft({}); setAdding(false); };
  const saveEdit = () => {
    if (adding) {
      createMut.mutate(draft as Partial<Reference>, { onSuccess: cancelEdit });
    } else if (editingId) {
      updateMut.mutate({ id: editingId, ...draft } as Partial<Reference> & { id: number }, { onSuccess: cancelEdit });
    }
  };
  const startAdd = () => { setAdding(true); setEditingId(null); setDraft({ ok_to_contact: true }); };

  if (isLoading) return <p style={{ color: '#94a3b8', padding: 16 }}>Loading references...</p>;

  if (isLoading) return <p style={{ color: '#94a3b8', padding: 16 }}>Loading references...</p>;

  const formCells = () => (
    <>
      <td style={styles.td}><input style={styles.input} placeholder="Name" value={draft.name || ''} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></td>
      <td style={styles.td}><input style={styles.input} placeholder="Title" value={draft.title || ''} onChange={(e) => setDraft({ ...draft, title: e.target.value })} /></td>
      <td style={styles.td}><input style={styles.input} placeholder="Company" value={draft.company || ''} onChange={(e) => setDraft({ ...draft, company: e.target.value })} /></td>
      <td style={styles.td}>
        <select style={styles.select} value={draft.relationship || ''} onChange={(e) => setDraft({ ...draft, relationship: e.target.value })}>
          <option value="">-</option>
          {RELATIONSHIP_TYPES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </td>
      <td style={styles.td}><input style={styles.input} placeholder="Email" value={draft.email || ''} onChange={(e) => setDraft({ ...draft, email: e.target.value })} /></td>
      <td style={styles.td}>
        <input type="checkbox" checked={draft.ok_to_contact ?? true} onChange={(e) => setDraft({ ...draft, ok_to_contact: e.target.checked })} />
      </td>
      <td style={styles.td}>
        <div style={{ display: 'flex', gap: 6 }}>
          <button style={styles.btnPrimary} onClick={saveEdit}>Save</button>
          <button style={styles.btnGhost} onClick={cancelEdit}>Cancel</button>
        </div>
      </td>
    </>
  );

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16 }}>
        <button style={styles.btnPrimary} onClick={startAdd}>+ Add Reference</button>
        <span style={{ color: '#64748b', fontSize: 13 }}>{data.length} reference{data.length !== 1 ? 's' : ''}</span>
      </div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>Name</th>
            <th style={styles.th}>Title</th>
            <th style={styles.th}>Company</th>
            <th style={styles.th}>Relationship</th>
            <th style={styles.th}>Email</th>
            <th style={{ ...styles.th, width: 50 }}>OK?</th>
            <th style={{ ...styles.th, width: 120 }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {adding && <tr style={{ background: '#1e293b' }}>{formCells()}</tr>}
          {data.map((item) => (
            <tr key={item.id} style={styles.row} onMouseEnter={(e) => (e.currentTarget.style.background = '#1e293b')} onMouseLeave={(e) => (e.currentTarget.style.background = '')}>
              {editingId === item.id ? formCells() : (
                <>
                  <td style={{ ...styles.td, color: '#e2e8f0' }}>{item.name}</td>
                  <td style={{ ...styles.td, color: '#94a3b8' }}>{item.title || '-'}</td>
                  <td style={{ ...styles.td, color: '#94a3b8' }}>{item.company || '-'}</td>
                  <td style={{ ...styles.td, color: '#94a3b8' }}>{item.relationship || '-'}</td>
                  <td style={{ ...styles.td, color: '#94a3b8' }}>{item.email || '-'}</td>
                  <td style={{ ...styles.td, textAlign: 'center' }}>{item.ok_to_contact !== false ? 'Y' : 'N'}</td>
                  <td style={styles.td}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button style={styles.btnGhost} onClick={() => startEdit(item)}>Edit</button>
                      <button style={styles.btnDanger} onClick={() => { if (confirm(`Delete "${item.name}"?`)) deleteMut.mutate(item.id); }}>Del</button>
                    </div>
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length === 0 && !adding && <p style={{ color: '#64748b', padding: 16, textAlign: 'center' }}>No references.</p>}
    </div>
  );
}

// ---- Summaries Tab ----

function SummariesTab() {
  const { data, isLoading, createMut, updateMut, deleteMut } = useTabCrud<SummaryVariant>('/summary-variants', 'kb-summaries');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Partial<SummaryVariant>>({});
  const [adding, setAdding] = useState(false);

  const startEdit = (item: SummaryVariant) => { setEditingId(item.id); setDraft({ ...item }); setAdding(false); };
  const cancelEdit = () => { setEditingId(null); setDraft({}); setAdding(false); };
  const saveEdit = () => {
    if (adding) {
      createMut.mutate(draft as Partial<SummaryVariant>, { onSuccess: cancelEdit });
    } else if (editingId) {
      updateMut.mutate({ id: editingId, ...draft } as Partial<SummaryVariant> & { id: number }, { onSuccess: cancelEdit });
    }
  };
  const startAdd = () => { setAdding(true); setEditingId(null); setDraft({}); };

  if (isLoading) return <p style={{ color: '#94a3b8', padding: 16 }}>Loading summaries...</p>;

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16 }}>
        <button style={styles.btnPrimary} onClick={startAdd}>+ Add Summary</button>
        <span style={{ color: '#64748b', fontSize: 13 }}>{data.length} variant{data.length !== 1 ? 's' : ''}</span>
      </div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={{ ...styles.th, width: 180 }}>Role Type</th>
            <th style={styles.th}>Text</th>
            <th style={{ ...styles.th, width: 120 }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {adding && (
            <tr style={{ background: '#1e293b' }}>
              <td style={styles.td}><input style={styles.input} placeholder="e.g. CTO, VP Engineering" value={draft.role_type || ''} onChange={(e) => setDraft({ ...draft, role_type: e.target.value })} /></td>
              <td style={styles.td}><textarea style={styles.textarea} placeholder="Summary text..." value={draft.text || ''} onChange={(e) => setDraft({ ...draft, text: e.target.value })} /></td>
              <td style={styles.td}>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button style={styles.btnPrimary} onClick={saveEdit}>Save</button>
                  <button style={styles.btnGhost} onClick={cancelEdit}>Cancel</button>
                </div>
              </td>
            </tr>
          )}
          {data.map((item) => (
            <tr key={item.id} style={styles.row} onMouseEnter={(e) => (e.currentTarget.style.background = '#1e293b')} onMouseLeave={(e) => (e.currentTarget.style.background = '')}>
              {editingId === item.id ? (
                <>
                  <td style={styles.td}><input style={styles.input} value={draft.role_type || ''} onChange={(e) => setDraft({ ...draft, role_type: e.target.value })} /></td>
                  <td style={styles.td}><textarea style={styles.textarea} value={draft.text || ''} onChange={(e) => setDraft({ ...draft, text: e.target.value })} /></td>
                  <td style={styles.td}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button style={styles.btnPrimary} onClick={saveEdit}>Save</button>
                      <button style={styles.btnGhost} onClick={cancelEdit}>Cancel</button>
                    </div>
                  </td>
                </>
              ) : (
                <>
                  <td style={{ ...styles.td, color: '#e2e8f0', fontWeight: 500 }}>{item.role_type}</td>
                  <td style={{ ...styles.td, color: '#94a3b8', maxWidth: 600, whiteSpace: 'pre-wrap' }}>{item.text || '-'}</td>
                  <td style={styles.td}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button style={styles.btnGhost} onClick={() => startEdit(item)}>Edit</button>
                      <button style={styles.btnDanger} onClick={() => { if (confirm(`Delete "${item.role_type}" summary?`)) deleteMut.mutate(item.id); }}>Del</button>
                    </div>
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length === 0 && !adding && <p style={{ color: '#64748b', padding: 16, textAlign: 'center' }}>No summary variants.</p>}
    </div>
  );
}

// ---- Main Page ----

export default function KnowledgeBase() {
  const [activeTab, setActiveTab] = useState<TabKey>('skills');

  return (
    <div>
      <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#f1f5f9', marginBottom: 24 }}>Knowledge Base</h1>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid #334155', marginBottom: 24 }}>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: '10px 20px',
              fontSize: '14px',
              fontWeight: activeTab === tab.key ? 600 : 400,
              color: activeTab === tab.key ? '#3b82f6' : '#94a3b8',
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === tab.key ? '2px solid #3b82f6' : '2px solid transparent',
              cursor: 'pointer',
              transition: 'color 0.15s, border-color 0.15s',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'skills' && <SkillsTab />}
      {activeTab === 'education' && <EducationTab />}
      {activeTab === 'certifications' && <CertificationsTab />}
      {activeTab === 'languages' && <LanguagesTab />}
      {activeTab === 'references' && <ReferencesTab />}
      {activeTab === 'summaries' && <SummariesTab />}
    </div>
  );
}
