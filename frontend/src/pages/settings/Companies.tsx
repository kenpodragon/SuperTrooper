import { useQuery } from '@tanstack/react-query';
import { companies } from '../../api/client';
import type { Company } from '../../api/client';

export default function Companies() {
  const { data, isLoading } = useQuery({
    queryKey: ['companies'],
    queryFn: () => companies.list('?limit=50'),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Companies</h1>
        <span className="text-sm text-gray-500">{data?.length ?? 0} companies</span>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Name</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Sector</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Size</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Fit</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Priority</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Target Role</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
            )}
            {(data ?? []).map((c: Company) => (
              <tr key={c.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{c.name}</td>
                <td className="px-4 py-3 text-gray-500">{c.sector || '-'}</td>
                <td className="px-4 py-3 text-gray-500">{c.size || '-'}</td>
                <td className="px-4 py-3">
                  {c.fit_score != null && (
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      c.fit_score >= 8 ? 'bg-green-100 text-green-700' :
                      c.fit_score >= 6 ? 'bg-yellow-100 text-yellow-700' :
                      'bg-gray-100 text-gray-500'
                    }`}>
                      {c.fit_score}/10
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {c.priority && (
                    <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                      c.priority === 'A' ? 'bg-green-100 text-green-700' :
                      c.priority === 'B' ? 'bg-blue-100 text-blue-700' :
                      'bg-gray-100 text-gray-500'
                    }`}>
                      {c.priority}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-500">{c.target_role || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
