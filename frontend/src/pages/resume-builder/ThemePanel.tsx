import type { ThemeSettings } from './types';

interface Props {
  theme: ThemeSettings;
  onChange: (theme: ThemeSettings) => void;
  onClose: () => void;
}

const FONT_OPTIONS = [
  'Georgia, serif',
  'Times New Roman, serif',
  'Calibri, sans-serif',
  'Arial, sans-serif',
  'Garamond, serif',
  'Cambria, serif',
  'Helvetica, sans-serif',
];

const BULLET_STYLES = ['disc', 'circle', 'square', 'dash', 'arrow'];
const DIVIDER_STYLES = ['line', 'double', 'dotted', 'none'];
const ALIGNMENTS = ['left', 'center'];

export default function ThemePanel({ theme, onChange, onClose }: Props) {
  const update = (key: keyof ThemeSettings, value: unknown) => {
    onChange({ ...theme, [key]: value });
  };

  return (
    <div className="w-72 border-l border-gray-700 bg-gray-900 p-4 overflow-y-auto">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-bold">Theme Settings</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-white">&times;</button>
      </div>

      <label className="block text-xs text-gray-400 mb-1 mt-3">Font Family</label>
      <select value={theme.font_family ?? 'Georgia, serif'} onChange={(e) => update('font_family', e.target.value)}
        className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm">
        {FONT_OPTIONS.map(f => <option key={f} value={f}>{f.split(',')[0]}</option>)}
      </select>

      <label className="block text-xs text-gray-400 mb-1 mt-3">Name Size ({theme.font_size_name ?? 20}pt)</label>
      <input type="range" min={14} max={28} value={theme.font_size_name ?? 20}
        onChange={(e) => update('font_size_name', parseInt(e.target.value))} className="w-full" />

      <label className="block text-xs text-gray-400 mb-1 mt-3">Heading Size ({theme.font_size_heading ?? 14}pt)</label>
      <input type="range" min={10} max={20} value={theme.font_size_heading ?? 14}
        onChange={(e) => update('font_size_heading', parseInt(e.target.value))} className="w-full" />

      <label className="block text-xs text-gray-400 mb-1 mt-3">Body Size ({theme.font_size_body ?? 11}pt)</label>
      <input type="range" min={8} max={14} value={theme.font_size_body ?? 11}
        onChange={(e) => update('font_size_body', parseInt(e.target.value))} className="w-full" />

      <label className="block text-xs text-gray-400 mb-1 mt-3">Accent Color</label>
      <div className="flex items-center gap-2">
        <input type="color" value={theme.accent_color ?? '#2563eb'}
          onChange={(e) => update('accent_color', e.target.value)} className="w-8 h-8 rounded cursor-pointer" />
        <span className="text-xs text-gray-400">{theme.accent_color ?? '#2563eb'}</span>
      </div>

      <label className="block text-xs text-gray-400 mb-1 mt-3">Margins (inches)</label>
      <div className="grid grid-cols-2 gap-2">
        {(['margin_top', 'margin_bottom', 'margin_left', 'margin_right'] as const).map(key => (
          <div key={key}>
            <span className="text-xs text-gray-500">{key.replace('margin_', '')}</span>
            <input type="number" step={0.125} min={0.25} max={1.5}
              value={theme[key] as number ?? (key.includes('left') || key.includes('right') ? 0.75 : 0.5)}
              onChange={(e) => update(key, parseFloat(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm" />
          </div>
        ))}
      </div>

      <label className="block text-xs text-gray-400 mb-1 mt-3">Bullet Style</label>
      <select value={theme.bullet_style as string ?? 'disc'} onChange={(e) => update('bullet_style', e.target.value)}
        className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm">
        {BULLET_STYLES.map(s => <option key={s} value={s}>{s}</option>)}
      </select>

      <label className="block text-xs text-gray-400 mb-1 mt-3">Header Alignment</label>
      <div className="flex gap-2">
        {ALIGNMENTS.map(a => (
          <button key={a} onClick={() => update('header_alignment', a)}
            className={`px-3 py-1 text-sm rounded ${(theme.header_alignment ?? 'left') === a ? 'bg-blue-600' : 'bg-gray-800 hover:bg-gray-700'}`}>
            {a}
          </button>
        ))}
      </div>

      <label className="block text-xs text-gray-400 mb-1 mt-3">Section Divider</label>
      <select value={theme.section_divider as string ?? 'line'} onChange={(e) => update('section_divider', e.target.value)}
        className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm">
        {DIVIDER_STYLES.map(s => <option key={s} value={s}>{s}</option>)}
      </select>
    </div>
  );
}
