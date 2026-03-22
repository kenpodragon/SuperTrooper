/**
 * ResumeSelector.tsx — Dropdown to select which resume recipe to use for a job application.
 * Fetches available recipes from the backend and shows name + target role.
 */

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@shared/api";

interface Recipe {
  id: number;
  name: string;
  target_role: string;
  description?: string;
  created_at?: string;
}

interface RecipesResponse {
  recipes: Recipe[];
}

export default function ResumeSelector() {
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genResult, setGenResult] = useState<string | null>(null);

  const loadRecipes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<RecipesResponse>("/api/resume/recipes");
      const list = data.recipes || [];
      setRecipes(list);
      if (list.length > 0 && !selected) {
        setSelected(list[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load recipes");
    } finally {
      setLoading(false);
    }
  }, [selected]);

  useEffect(() => {
    loadRecipes();
  }, [loadRecipes]);

  const handleGenerate = async () => {
    if (!selected) return;
    setGenerating(true);
    setGenResult(null);
    try {
      const result = await apiFetch<{ file_path?: string; message?: string }>(
        "/api/resume/generate",
        {
          method: "POST",
          body: JSON.stringify({ recipe_id: selected }),
        }
      );
      setGenResult(result.file_path || result.message || "Resume generated");
    } catch (err) {
      setGenResult(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="p-4 text-center text-st-muted text-sm animate-pulse">
        Loading recipes...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-center">
        <p className="text-st-red text-sm mb-2">{error}</p>
        <button
          onClick={loadRecipes}
          className="text-xs text-st-green hover:underline"
        >
          Retry
        </button>
      </div>
    );
  }

  if (recipes.length === 0) {
    return (
      <div className="p-4 text-center text-st-muted text-sm">
        <p className="text-lg mb-1">No recipes found</p>
        <p className="text-xs">Upload a resume to create your first recipe.</p>
      </div>
    );
  }

  const selectedRecipe = recipes.find((r) => r.id === selected);

  return (
    <div className="p-3 space-y-3">
      <h2 className="text-xs font-bold text-st-green tracking-wider uppercase">
        &gt; Resume Recipe
      </h2>

      {/* Recipe Dropdown */}
      <div>
        <label className="block text-xs text-st-muted mb-1">Select Recipe</label>
        <select
          value={selected || ""}
          onChange={(e) => setSelected(Number(e.target.value))}
          className="w-full bg-st-surface border border-st-border rounded px-3 py-2 text-sm text-st-text font-mono focus:border-st-green focus:outline-none appearance-none"
        >
          {recipes.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
      </div>

      {/* Selected Recipe Details */}
      {selectedRecipe && (
        <div className="bg-st-surface rounded p-3 border border-st-border">
          <div className="text-st-text text-sm font-semibold">
            {selectedRecipe.name}
          </div>
          <div className="text-st-green text-xs font-mono mt-0.5">
            {selectedRecipe.target_role}
          </div>
          {selectedRecipe.description && (
            <div className="text-st-muted text-xs mt-1">
              {selectedRecipe.description}
            </div>
          )}
        </div>
      )}

      {/* Generate Button */}
      <button
        onClick={handleGenerate}
        disabled={generating || !selected}
        className="w-full bg-st-green text-st-bg font-bold py-2 rounded text-sm hover:bg-st-green-dim transition-colors disabled:opacity-40"
      >
        {generating ? "Generating..." : "Generate Resume"}
      </button>

      {genResult && (
        <div className="bg-st-surface rounded p-3 border border-st-border">
          <div className="text-xs text-st-muted mb-1">Output</div>
          <div className="text-xs text-st-green font-mono break-all">
            {genResult}
          </div>
        </div>
      )}
    </div>
  );
}
