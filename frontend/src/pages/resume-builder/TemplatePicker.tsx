import { useState, useEffect } from 'react';
import { templateThumbnailUrl } from '../../api/client';

interface ResumeTemplate {
  id: number;
  name: string;
  description?: string;
  template_type?: string;
  has_thumbnail?: boolean;
}

interface Props {
  templates: ResumeTemplate[];
  onSelect: (templateId: number) => void;
}

function ThumbnailImg({ templateId, alt }: { templateId: number; alt: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(templateThumbnailUrl(templateId))
      .then((r) => (r.ok ? r.blob() : Promise.reject()))
      .then((blob) => {
        if (!cancelled) setSrc(URL.createObjectURL(blob));
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => { cancelled = true; };
  }, [templateId]);

  if (failed || !src) {
    return <span className="text-gray-500 text-sm">{failed ? 'Preview' : 'Loading...'}</span>;
  }
  return <img src={src} alt={alt} className="max-w-full max-h-full object-contain" />;
}

export default function TemplatePicker({ templates, onSelect }: Props) {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-2">Choose a Template</h1>
      <p className="text-gray-400 mb-6">Pick a resume template to start building.</p>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {templates.map((t) => (
          <button
            key={t.id}
            onClick={() => onSelect(t.id)}
            className="border border-gray-700 rounded-lg p-4 hover:border-blue-500 hover:bg-gray-800/50 transition-colors text-left"
          >
            <div className="w-full h-40 bg-gray-800 rounded mb-3 flex items-center justify-center overflow-hidden">
              <ThumbnailImg templateId={t.id} alt={t.name} />
            </div>
            <h3 className="font-medium">{t.name}</h3>
            {t.description && <p className="text-sm text-gray-400 mt-1">{t.description}</p>}
            <span className="text-xs text-gray-500 mt-2 block">{t.template_type ?? 'placeholder'}</span>
          </button>
        ))}
      </div>
      {templates.length === 0 && <p className="text-gray-500">No templates available.</p>}
    </div>
  );
}
