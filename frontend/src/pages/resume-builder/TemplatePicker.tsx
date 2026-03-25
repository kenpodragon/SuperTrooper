interface ResumeTemplate {
  id: number;
  name: string;
  description?: string;
  template_type?: string;
}

interface Props {
  templates: ResumeTemplate[];
  onSelect: (templateId: number) => void;
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
            <div className="w-full h-40 bg-gray-800 rounded mb-3 flex items-center justify-center text-gray-500 text-sm">
              Preview
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
