import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';

interface BulletRow { id: number; text: string; type?: string; career_history_id?: number; employer?: string; }
interface CareerRow { id: number; employer: string; title: string; start_date?: string; end_date?: string; }
interface SummaryRow { id: number; text: string; role_type?: string; }

type PickerMode = 'bullets' | 'jobs' | 'summaries';

interface Props {
  mode: PickerMode;
  filterEmployer?: string;
  onSelect: (item: { ref: string; id: number; text: string }) => void;
  onClose: () => void;
}

export default function ContentPickerModal({ mode, filterEmployer, onSelect, onClose }: Props) {
  const [search, setSearch] = useState('');

  const { data: bullets } = useQuery({
    queryKey: ['picker-bullets', filterEmployer],
    queryFn: () => api.get<BulletRow[]>(`/bullets?limit=500${filterEmployer ? `&employer=${encodeURIComponent(filterEmployer)}` : ''}`),
    enabled: mode === 'bullets',
  });

  const { data: jobs } = useQuery({
    queryKey: ['picker-jobs'],
    queryFn: () => api.get<CareerRow[]>('/career-history?limit=200'),
    enabled: mode === 'jobs',
  });

  const { data: summariesData } = useQuery({
    queryKey: ['picker-summaries'],
    queryFn: () => api.get<{ variants: SummaryRow[] }>('/resume/summary-variants'),
    enabled: mode === 'summaries',
  });

  const items = mode === 'bullets'
    ? (bullets ?? []).filter(b => b.text?.toLowerCase().includes(search.toLowerCase())).map(b => ({
        id: b.id, text: b.text, subtitle: b.employer ?? '', ref: 'bullets',
      }))
    : mode === 'jobs'
    ? (jobs ?? []).filter(j => j.employer?.toLowerCase().includes(search.toLowerCase())).map(j => ({
        id: j.id, text: `${j.employer} — ${j.title}`, subtitle: `${j.start_date ?? ''} - ${j.end_date ?? 'Present'}`, ref: 'career_history',
      }))
    : (summariesData?.variants ?? []).filter(s => s.text?.toLowerCase().includes(search.toLowerCase())).map(s => ({
        id: s.id, text: s.text, subtitle: s.role_type ?? '', ref: 'summary_variants',
      }));

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-lg w-[600px] max-h-[70vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="p-4 border-b border-gray-700">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-bold">Pick {mode === 'bullets' ? 'a Bullet' : mode === 'jobs' ? 'a Job' : 'a Summary'}</h3>
            <button onClick={onClose} className="text-gray-400 hover:text-white">&times;</button>
          </div>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={`Search ${mode}...`}
            autoFocus className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm outline-none" />
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {items.map(item => (
            <button key={item.id} onClick={() => onSelect({ ref: item.ref, id: item.id, text: item.text })}
              className="w-full text-left p-3 rounded hover:bg-gray-800 transition-colors">
              <p className="text-sm">{item.text}</p>
              {item.subtitle && <p className="text-xs text-gray-500 mt-0.5">{item.subtitle}</p>}
            </button>
          ))}
          {items.length === 0 && <p className="text-sm text-gray-500 p-4 text-center">No results</p>}
        </div>
      </div>
    </div>
  );
}
