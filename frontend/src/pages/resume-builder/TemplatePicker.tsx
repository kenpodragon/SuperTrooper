import { useState, useEffect } from 'react';
import { templateThumbnailUrl } from '../../api/client';

interface ResumeTemplate {
  id: number;
  name: string;
  description?: string;
  template_type?: string;
  has_thumbnail?: boolean;
}

interface ExistingRecipe {
  id: number;
  name: string;
  description?: string | null;
  headline?: string | null;
  template_id: number;
  updated_at?: string;
}

interface Props {
  templates: ResumeTemplate[];
  recipes?: ExistingRecipe[];
  onSelectTemplate: (templateId: number) => void;
  onSelectRecipe?: (recipeId: number) => void;
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

function fmtDate(iso?: string): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return '';
  }
}

export default function TemplatePicker({ templates, recipes = [], onSelectTemplate, onSelectRecipe }: Props) {
  return (
    <div className="p-8">
      {recipes.length > 0 && (
        <>
          <h1 className="text-2xl font-bold mb-2">Your Resumes</h1>
          <p className="text-gray-400 mb-6">Open an existing resume to keep editing.</p>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-10">
            {recipes.map((r) => (
              <button
                key={r.id}
                onClick={() => onSelectRecipe?.(r.id)}
                className="border border-gray-700 rounded-lg p-4 hover:border-emerald-500 hover:bg-gray-800/50 transition-colors text-left"
              >
                <div className="w-full h-40 bg-gray-800 rounded mb-3 flex items-center justify-center overflow-hidden">
                  <ThumbnailImg templateId={r.template_id} alt={r.name} />
                </div>
                <h3 className="font-medium truncate" title={r.name}>{r.name}</h3>
                {r.headline && (
                  <p className="text-sm text-gray-400 mt-1 line-clamp-2" title={r.headline}>
                    {r.headline}
                  </p>
                )}
                <span className="text-xs text-gray-500 mt-2 block">
                  Updated {fmtDate(r.updated_at)}
                </span>
              </button>
            ))}
          </div>
        </>
      )}

      <h1 className="text-2xl font-bold mb-2">
        {recipes.length > 0 ? 'Start a New Resume' : 'Choose a Template'}
      </h1>
      <p className="text-gray-400 mb-6">Pick a resume template to start building.</p>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {templates.map((t) => (
          <button
            key={t.id}
            onClick={() => onSelectTemplate(t.id)}
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
