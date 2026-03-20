import { useQuery } from '@tanstack/react-query';
import { contacts } from '../../api/client';
import type { Contact } from '../../api/client';

const strengthColor: Record<string, string> = {
  strong: 'bg-green-100 text-green-700',
  warm: 'bg-yellow-100 text-yellow-700',
  cold: 'bg-blue-100 text-blue-700',
  stale: 'bg-gray-100 text-gray-500',
};

export default function Contacts() {
  const { data, isLoading } = useQuery({
    queryKey: ['contacts'],
    queryFn: () => contacts.list('?limit=100'),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Contacts</h1>
        <span className="text-sm text-gray-500">{data?.length ?? 0} contacts</span>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Name</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Company</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Title</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Relationship</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Strength</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Last Contact</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
            )}
            {(data ?? []).map((c: Contact) => (
              <tr key={c.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{c.name}</td>
                <td className="px-4 py-3 text-gray-700">{c.company || '-'}</td>
                <td className="px-4 py-3 text-gray-500">{c.title || '-'}</td>
                <td className="px-4 py-3 text-gray-500">{c.relationship || '-'}</td>
                <td className="px-4 py-3">
                  {c.relationship_strength && (
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${strengthColor[c.relationship_strength] || 'bg-gray-100 text-gray-600'}`}>
                      {c.relationship_strength}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-500">{c.last_contact || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
