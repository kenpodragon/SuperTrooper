import { useQuery } from '@tanstack/react-query';
import { recipes, bullets } from '../../api/client';
import type { Recipe, Bullet } from '../../api/client';

export default function Resumes() {
  const { data: recipeList, isLoading: loadingRecipes } = useQuery({
    queryKey: ['recipes'],
    queryFn: () => recipes.list(),
  });
  const { data: bulletList, isLoading: loadingBullets } = useQuery({
    queryKey: ['bullets'],
    queryFn: () => bullets.list('?limit=20'),
  });

  // recipes endpoint returns { recipes: [...], count } or just [...]
  const recipeItems: Recipe[] = Array.isArray(recipeList) ? recipeList : (recipeList as { recipes?: Recipe[] })?.recipes ?? [];
  const bulletItems: Bullet[] = Array.isArray(bulletList) ? bulletList : [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Resume Builder</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Recipes */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Recipes</h2>
          {loadingRecipes && <p className="text-sm text-gray-400">Loading...</p>}
          {recipeItems.map((r: Recipe) => (
            <div key={r.id} className="flex justify-between py-2 border-b border-gray-100 last:border-0">
              <div>
                <p className="text-sm font-medium text-gray-900">{r.name}</p>
                <p className="text-xs text-gray-400">{r.description || 'No description'}</p>
              </div>
              <div className="flex gap-2 items-center">
                {r.is_active && <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Active</span>}
                <button className="text-xs bg-blue-50 text-blue-600 px-3 py-1 rounded hover:bg-blue-100">
                  Generate
                </button>
              </div>
            </div>
          ))}
          {!loadingRecipes && recipeItems.length === 0 && <p className="text-sm text-gray-400">No recipes found</p>}
        </div>

        {/* Bullet Browser */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Bullet Browser</h2>
          {loadingBullets && <p className="text-sm text-gray-400">Loading...</p>}
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {bulletItems.map((b: Bullet) => (
              <div key={b.id} className="py-2 border-b border-gray-100 last:border-0">
                <p className="text-sm text-gray-700">{b.text}</p>
                <div className="flex gap-2 mt-1">
                  <span className="text-xs text-gray-400">{b.employer}</span>
                  {b.tags?.slice(0, 3).map(t => (
                    <span key={t} className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">{t}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
