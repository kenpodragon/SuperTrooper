import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
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

export default function ResumeBuilder() {
  const { id } = useParams<{ id: string }>();
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

  if (!recipeId && !selectedTemplateId) {
    return <TemplatePicker templates={templates} onSelect={(tid) => setSelectedTemplateId(tid)} />;
  }

  if (loadingRecipe) {
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
