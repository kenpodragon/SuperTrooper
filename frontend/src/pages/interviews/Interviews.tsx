import { useQuery } from '@tanstack/react-query';
import { interviews } from '../../api/client';
import type { Interview } from '../../api/client';

const outcomeColor: Record<string, string> = {
  passed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  pending: 'bg-yellow-100 text-yellow-700',
  ghosted: 'bg-gray-100 text-gray-500',
};

export default function Interviews() {
  const { data, isLoading } = useQuery({
    queryKey: ['interviews'],
    queryFn: () => interviews.list('?limit=50'),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Interviews</h1>
        <span className="text-sm text-gray-500">{data?.length ?? 0} interviews</span>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Company</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Role</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Type</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Date</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Outcome</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Thank You</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
            )}
            {(data ?? []).map((i: Interview) => (
              <tr key={i.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{i.company_name || '-'}</td>
                <td className="px-4 py-3 text-gray-700">{i.role || '-'}</td>
                <td className="px-4 py-3 text-gray-500">{i.type || '-'}</td>
                <td className="px-4 py-3 text-gray-500">{i.date ? new Date(i.date).toLocaleDateString() : '-'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${outcomeColor[i.outcome || ''] || 'bg-gray-100 text-gray-600'}`}>
                    {i.outcome || 'pending'}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500">{i.thank_you_sent ? 'Sent' : 'No'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
