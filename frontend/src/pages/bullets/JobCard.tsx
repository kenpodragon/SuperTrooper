import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import SmartDateInput, { calcDuration } from './SmartDateInput';

export interface CareerJob {
  id: number;
  employer: string;
  title: string;
  start_date?: string | null;
  end_date?: string | null;
  location?: string | null;
  industry?: string | null;
  team_size?: number | null;
  budget_usd?: number | null;
  revenue_impact?: string | null;
  is_current?: boolean;
  linkedin_dates?: string | null;
  notes?: string | null;
  metadata?: Record<string, string> | null;
  bullet_count?: number;
}

interface JobCardProps {
  job: CareerJob;
  isSelected: boolean;
  onSelect: () => void;
  onUpdate: () => void;
  onDeleted?: () => void;
}

type EditMode = 'collapsed' | 'view' | 'edit';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

export default function JobCard({ job, isSelected, onSelect, onUpdate, onDeleted }: JobCardProps) {
  const [mode, setMode] = useState<EditMode>('collapsed');
  const [form, setForm] = useState<Record<string, string>>({});
  const [metaRows, setMetaRows] = useState<Array<{ key: string; value: string }>>([]);
  const queryClient = useQueryClient();

  const expanded = isSelected && mode !== 'collapsed';

  const handleSelect = () => {
    if (!isSelected) {
      onSelect();
      setMode('view');
    } else if (mode === 'collapsed') {
      setMode('view');
    } else {
      setMode('collapsed');
    }
  };

  const startEdit = () => {
    setForm({
      title: job.title || '',
      employer: job.employer || '',
      location: job.location || '',
      industry: job.industry || '',
      start_date: job.start_date || '',
      end_date: job.end_date || '',
      team_size: job.team_size?.toString() || '',
      budget_usd: job.budget_usd?.toString() || '',
      revenue_impact: job.revenue_impact || '',
      linkedin_dates: job.linkedin_dates || '',
      notes: job.notes || '',
    });
    const meta = job.metadata || {};
    setMetaRows(Object.entries(meta).map(([key, value]) => ({ key, value: String(value) })));
    setMode('edit');
  };

  const cancelEdit = () => setMode('view');

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.patch(`/career-history/${job.id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['career-history'] });
      setMode('view');
      onUpdate();
    },
  });

  const saveEdit = () => {
    const payload: Record<string, unknown> = {};
    const stringFields = ['title', 'employer', 'location', 'industry', 'revenue_impact', 'linkedin_dates', 'notes'];
    for (const f of stringFields) {
      if (form[f] !== undefined) payload[f] = form[f] || null;
    }
    if (form.start_date !== undefined) payload.start_date = form.start_date || null;
    if (form.end_date !== undefined) payload.end_date = form.end_date || null;
    if (form.team_size !== undefined) payload.team_size = form.team_size ? parseInt(form.team_size) : null;
    if (form.budget_usd !== undefined) payload.budget_usd = form.budget_usd ? parseFloat(form.budget_usd) : null;

    const metaObj: Record<string, string> = {};
    for (const row of metaRows) {
      if (row.key.trim()) metaObj[row.key.trim()] = row.value;
    }
    if (metaRows.length > 0) payload.metadata = metaObj;

    mutation.mutate(payload);
  };

  const duration = calcDuration(job.start_date || null, job.end_date || null);

  return (
    <div
      className={`border-b border-gray-700 transition-colors ${
        isSelected ? 'bg-gray-800' : 'hover:bg-gray-800/50'
      }`}
    >
      {/* Collapsed header - always visible */}
      <button
        onClick={handleSelect}
        className="w-full flex items-center gap-3 px-4 py-3 text-left"
      >
        <span className="text-gray-500 text-xs">{expanded ? '\u25BE' : '\u25B8'}</span>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm text-gray-100 truncate">{job.title}</div>
        </div>
        <span className="shrink-0 text-xs text-gray-500">
          {(() => {
            const s = job.start_date?.match(/(\d{4})/)?.[1];
            if (!s) return '';
            if (!job.end_date) return `${s}–now`;
            const e = job.end_date.match(/(\d{4})/)?.[1];
            return e && s !== e ? `${s}–${e}` : s;
          })()}
        </span>
        {job.bullet_count !== undefined && (
          <span className="shrink-0 bg-blue-500/20 text-blue-300 text-xs px-2 py-0.5 rounded-full">
            {job.bullet_count}
          </span>
        )}
      </button>

      {/* Expanded view */}
      {isSelected && mode === 'view' && (
        <div className="px-4 pb-3 space-y-2">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <Detail label="Title" value={job.title} />
            <Detail label="Company" value={job.employer} />
            <Detail label="Location" value={job.location} />
            <Detail label="Industry" value={job.industry} />
            <Detail label="From" value={job.start_date} />
            <Detail label="To" value={job.end_date || (job.is_current ? 'Present' : undefined)} />
            {duration && <Detail label="Duration" value={duration} />}
            {job.team_size && <Detail label="Team Size" value={String(job.team_size)} />}
            {job.budget_usd && <Detail label="Budget" value={`$${job.budget_usd.toLocaleString()}`} />}
            {job.revenue_impact && <Detail label="Revenue Impact" value={job.revenue_impact} />}
            {job.linkedin_dates && <Detail label="LinkedIn Dates" value={job.linkedin_dates} />}
          </div>
          {job.metadata && Object.keys(job.metadata).length > 0 && (
            <div className="text-xs space-y-0.5">
              <span className="text-gray-500">Metadata:</span>
              {Object.entries(job.metadata).map(([k, v]) => (
                <div key={k} className="pl-2 text-gray-400">
                  <span className="text-gray-500">{k}:</span> {String(v)}
                </div>
              ))}
            </div>
          )}
          {job.notes && (
            <div className="text-xs text-gray-400">
              <span className="text-gray-500">Notes:</span> {job.notes}
            </div>
          )}
          <div className="flex gap-2 pt-1">
            <button
              onClick={startEdit}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              ✏️ Edit
            </button>
            <button
              onClick={async () => {
                const msg = `Delete "${job.title}" at "${job.employer}"? This job has ${job.bullet_count || 0} bullets.`;
                if (!window.confirm(msg)) return;
                const keepBullets = window.confirm(
                  'Keep the bullets? They will be moved to UNASSIGNED.\n\nOK = Keep bullets\nCancel = Delete everything'
                );
                try {
                  await fetch(`${API_BASE}/career-history/${job.id}/with-options`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ keep_bullets: keepBullets }),
                  });
                  onDeleted?.();
                } catch (e) {
                  alert(`Delete failed: ${(e as Error).message}`);
                }
              }}
              className="text-xs text-gray-500 hover:text-red-400"
            >
              🗑 Delete
            </button>
          </div>
        </div>
      )}

      {/* Edit mode */}
      {isSelected && mode === 'edit' && (
        <div className="px-4 pb-3 space-y-2">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-yellow-400 font-medium">Editing</span>
          </div>
          <div className="space-y-2">
            <Field label="Title" value={form.title || ''} onChange={(v) => setForm({ ...form, title: v })} />
            <Field label="Company" value={form.employer || ''} onChange={(v) => setForm({ ...form, employer: v })} />
            <Field label="Location" value={form.location || ''} onChange={(v) => setForm({ ...form, location: v })} />
            <Field label="Industry" value={form.industry || ''} onChange={(v) => setForm({ ...form, industry: v })} />
            <SmartDateInput
              label="From"
              value={form.start_date || ''}
              onChange={(raw) => setForm({ ...form, start_date: raw })}
            />
            <SmartDateInput
              label="To"
              value={form.end_date || ''}
              onChange={(raw) => setForm({ ...form, end_date: raw })}
            />
            {form.start_date && (
              <div className="text-xs text-gray-500">
                Duration: {calcDuration(form.start_date, form.end_date || null)}
              </div>
            )}
            <Field label="Team Size" value={form.team_size || ''} onChange={(v) => setForm({ ...form, team_size: v })} />
            <Field label="Budget (USD)" value={form.budget_usd || ''} onChange={(v) => setForm({ ...form, budget_usd: v })} />
            <Field label="Revenue Impact" value={form.revenue_impact || ''} onChange={(v) => setForm({ ...form, revenue_impact: v })} />
            <Field label="LinkedIn Dates" value={form.linkedin_dates || ''} onChange={(v) => setForm({ ...form, linkedin_dates: v })} />
            <div>
              <label className="text-xs text-gray-400">Notes</label>
              <textarea
                value={form.notes || ''}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                rows={2}
                className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-gray-100 focus:border-blue-400 focus:outline-none"
              />
            </div>

            {/* Metadata key-value rows */}
            <div className="space-y-1">
              <label className="text-xs text-gray-400">Metadata</label>
              {metaRows.map((row, i) => (
                <div key={i} className="flex gap-1 items-center">
                  <input
                    value={row.key}
                    onChange={(e) => {
                      const updated = [...metaRows];
                      updated[i] = { ...updated[i], key: e.target.value };
                      setMetaRows(updated);
                    }}
                    placeholder="key"
                    className="w-1/3 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-100"
                  />
                  <input
                    value={row.value}
                    onChange={(e) => {
                      const updated = [...metaRows];
                      updated[i] = { ...updated[i], value: e.target.value };
                      setMetaRows(updated);
                    }}
                    placeholder="value"
                    className="flex-1 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-100"
                  />
                  <button
                    onClick={() => setMetaRows(metaRows.filter((_, j) => j !== i))}
                    className="text-red-400 hover:text-red-300 text-xs px-1"
                  >
                    x
                  </button>
                </div>
              ))}
              <button
                onClick={() => setMetaRows([...metaRows, { key: '', value: '' }])}
                className="text-xs text-blue-400 hover:text-blue-300"
              >
                + Add field
              </button>
            </div>
          </div>

          <div className="flex gap-2 pt-2">
            <button
              onClick={saveEdit}
              disabled={mutation.isPending}
              className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded disabled:opacity-50"
            >
              {mutation.isPending ? 'Saving...' : 'Save'}
            </button>
            <button
              onClick={cancelEdit}
              className="px-3 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded"
            >
              Cancel
            </button>
            {mutation.isError && (
              <span className="text-xs text-red-400">{(mutation.error as Error).message}</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Detail({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div>
      <span className="text-gray-500">{label}: </span>
      <span className="text-gray-300">{value}</span>
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="text-xs text-gray-400">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-gray-100 focus:border-blue-400 focus:outline-none"
      />
    </div>
  );
}
