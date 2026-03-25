import { useState } from 'react';

export function parseFlexDate(input: string): { iso: string | null; display: string } {
  const s = input.trim();
  if (!s || /^present$/i.test(s)) return { iso: null, display: 'Present' };
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return { iso: s, display: s };
  if (/^\d{4}$/.test(s)) return { iso: `${s}-01-01`, display: s };
  const d = new Date(s);
  if (!isNaN(d.getTime())) return { iso: d.toISOString().split('T')[0], display: s };
  return { iso: null, display: s };
}

export function calcDuration(fromIso: string | null, toIso: string | null): string {
  if (!fromIso) return '';
  const start = new Date(fromIso);
  const end = toIso ? new Date(toIso) : new Date();
  let months = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
  if (months < 0) return '';
  const years = Math.floor(months / 12);
  months = months % 12;
  const parts: string[] = [];
  if (years > 0) parts.push(`${years} yr${years > 1 ? 's' : ''}`);
  if (months > 0) parts.push(`${months} mo${months > 1 ? 's' : ''}`);
  return parts.join(' ') || '< 1 mo';
}

interface SmartDateInputProps {
  value: string;
  onChange: (raw: string, iso: string | null) => void;
  label?: string;
}

export default function SmartDateInput({ value, onChange, label }: SmartDateInputProps) {
  const [showPicker, setShowPicker] = useState(false);
  const parsed = parseFlexDate(value);

  return (
    <div className="flex flex-col gap-1">
      {label && <label className="text-xs text-gray-400">{label}</label>}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => {
            const p = parseFlexDate(e.target.value);
            onChange(e.target.value, p.iso);
          }}
          onBlur={() => {
            const p = parseFlexDate(value);
            onChange(value, p.iso);
          }}
          placeholder="e.g. Mar 2022, 2022, Present"
          className="flex-1 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-gray-100 focus:border-blue-400 focus:outline-none"
        />
        <button
          type="button"
          onClick={() => setShowPicker(!showPicker)}
          className="text-gray-400 hover:text-gray-200 text-sm"
          title="Date picker"
        >
          📅
        </button>
        {parsed.iso && (
          <span className="text-xs text-green-400 whitespace-nowrap">{parsed.iso}</span>
        )}
      </div>
      {showPicker && (
        <input
          type="date"
          value={parsed.iso || ''}
          onChange={(e) => {
            onChange(e.target.value, e.target.value || null);
            setShowPicker(false);
          }}
          className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-gray-100"
        />
      )}
    </div>
  );
}
