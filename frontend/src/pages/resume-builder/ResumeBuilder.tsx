import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';
import TemplatePicker from './TemplatePicker';
import ResumeEditor from './ResumeEditor';

interface ResumeTemplate {
  id: number;
  name: string;
  description?: string;
  template_type?: string;
  is_active?: boolean;
}

interface RecipeRow {
  id: number;
  name: string;
  recipe: Record<string, unknown>;
  recipe_version?: number;
  template_id: number;
  theme?: Record<string, unknown>;
  resolved_preview?: Record<string, unknown>;
}

const SCAFFOLD_RECIPE = {
  header: { ref: 'candidate_header', id: 1 },
  headline: { literal: '' },
  summary: { literal: '' },
  experience: [],
  skills: [],
  education: [],
  certifications: [],
  highlights: [],
};

export default function ResumeBuilder() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const recipeId = id ? parseInt(id, 10) : null;
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);

  const { data: recipe, isLoading: loadingRecipe } = useQuery({
    queryKey: ['recipe-builder', recipeId],
    queryFn: () => api.get<RecipeRow>(`/resume/recipes/${recipeId}?resolve=true`),
    enabled: recipeId != null,
  });

  const { data: templatesData } = useQuery({
    queryKey: ['templates'],
    queryFn: () => api.get<{ templates: ResumeTemplate[] }>('/resume/templates'),
  });
  const templates = templatesData?.templates ?? [];

  const createRecipeMut = useMutation({
    mutationFn: (templateId: number) => {
      const tpl = templates.find((t) => t.id === templateId);
      return api.post<RecipeRow>('/resume/recipes', {
        name: `New Resume`,
        template_id: templateId,
        description: tpl ? `From template: ${tpl.name}` : '',
        recipe: SCAFFOLD_RECIPE,
      });
    },
    onSuccess: (data) => {
      navigate(`/resume-builder/${data.id}`, { replace: true });
    },
  });

  // When a template is selected, create a recipe from it
  useEffect(() => {
    if (selectedTemplateId && !recipeId && !createRecipeMut.isPending) {
      createRecipeMut.mutate(selectedTemplateId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTemplateId]);

  if (!recipeId && !selectedTemplateId) {
    return <TemplatePicker templates={templates} onSelect={(tid) => setSelectedTemplateId(tid)} />;
  }

  if (loadingRecipe || createRecipeMut.isPending) {
    return <div className="p-8 text-gray-400">Loading recipe...</div>;
  }

  return (
    <ResumeEditor
      recipeId={recipeId ?? 0}
      recipeName={recipe?.name ?? 'New Resume'}
      recipe={recipe?.recipe as any ?? {}}
      resolved={recipe?.resolved_preview as any ?? {}}
      theme={recipe?.theme as any ?? {}}
    />
  );
}
