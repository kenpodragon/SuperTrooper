import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';

interface Company {
  id: number;
  name: string;
  sector?: string;
  size?: string;
  fit_score?: number;
  priority?: string;
  target_role?: string;
  hq_location?: string;
  stage?: string;
  key_differentiator?: string;
  comp_range?: string;
  notes?: string;
  applications?: { id: number; role: string; status: string; date_applied: string }[];
  contacts?: { id: number; name: string; title: string; relationship_strength: string }[];
}

export default function Companies() {
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['companies'],
    queryFn: () => api.get<Company[]>('/companies?limit=100'),
  });

  const detail = useQuery({
    queryKey: ['company-detail', selectedId],
    queryFn: () => api.get<Company>(`/companies/${selectedId}`),
    enabled: selectedId != null,
  });

  const company = detail.data;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Companies</h1>
        <span className="text-sm text-gray-500">{data?.length ?? 0} companies</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Company List */}
        <div className="lg:col-span-2 bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Name</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Sector</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Fit</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Priority</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Target Role</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
              )}
              {(data ?? []).map((c: Company) => (
                <tr
                  key={c.id}
                  onClick={() => setSelectedId(c.id)}
                  className={`border-b border-gray-100 cursor-pointer ${
                    selectedId === c.id ? 'bg-blue-50' : 'hover:bg-gray-50'
                  }`}
                >
                  <td className="px-4 py-3 font-medium text-gray-900">{c.name}</td>
                  <td className="px-4 py-3 text-gray-500">{c.sector || '-'}</td>
                  <td className="px-4 py-3">
                    {c.fit_score != null && (
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        c.fit_score >= 8 ? 'bg-green-100 text-green-700' :
                        c.fit_score >= 6 ? 'bg-yellow-100 text-yellow-700' :
                        'bg-gray-100 text-gray-500'
                      }`}>{c.fit_score}/10</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {c.priority && (
                      <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                        c.priority === 'A' ? 'bg-green-100 text-green-700' :
                        c.priority === 'B' ? 'bg-blue-100 text-blue-700' :
                        'bg-gray-100 text-gray-500'
                      }`}>{c.priority}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{c.target_role || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Company Detail Panel */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          {!selectedId && (
            <p className="text-sm text-gray-400 text-center py-8">Select a company to view details</p>
          )}
          {detail.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
          {company && (
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-1">{company.name}</h2>
              {company.sector && <p className="text-sm text-gray-500 mb-3">{company.sector} {company.size ? `| ${company.size}` : ''}</p>}

              <div className="space-y-2 mb-4">
                {company.hq_location && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Location</span>
                    <span className="text-gray-900">{company.hq_location}</span>
                  </div>
                )}
                {company.comp_range && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Comp Range</span>
                    <span className="text-gray-900">{company.comp_range}</span>
                  </div>
                )}
                {company.key_differentiator && (
                  <div className="text-sm">
                    <span className="text-gray-500">Differentiator:</span>
                    <p className="text-gray-700 mt-1">{company.key_differentiator}</p>
                  </div>
                )}
                {company.notes && (
                  <div className="text-sm">
                    <span className="text-gray-500">Notes:</span>
                    <p className="text-gray-700 mt-1">{company.notes}</p>
                  </div>
                )}
              </div>

              {/* Applications at company */}
              {company.applications && company.applications.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Applications ({company.applications.length})</h3>
                  {company.applications.map((a) => (
                    <div key={a.id} className="flex justify-between text-sm py-1.5 border-b border-gray-100 last:border-0">
                      <span className="text-gray-900">{a.role}</span>
                      <span className={`px-2 py-0.5 rounded-full text-xs ${
                        a.status === 'Offer' || a.status === 'Accepted' ? 'bg-green-100 text-green-700' :
                        a.status === 'Rejected' || a.status === 'Ghosted' ? 'bg-red-100 text-red-600' :
                        'bg-blue-100 text-blue-700'
                      }`}>{a.status}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Contacts at company */}
              {company.contacts && company.contacts.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Contacts ({company.contacts.length})</h3>
                  {company.contacts.map((ct) => (
                    <div key={ct.id} className="text-sm py-1.5 border-b border-gray-100 last:border-0">
                      <span className="text-gray-900 font-medium">{ct.name}</span>
                      {ct.title && <span className="text-gray-400 ml-1">- {ct.title}</span>}
                    </div>
                  ))}
                </div>
              )}

              {/* Monitor Button */}
              <button className="w-full mt-2 px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700">
                Monitor Careers Page
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
