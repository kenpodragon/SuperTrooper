import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, interviews } from '../../api/client';
import type { Interview } from '../../api/client';

interface PrepResult {
  id?: number;
  company?: string;
  role?: string;
  prep_notes?: string;
  questions?: string[];
  talking_points?: string[];
  message?: string;
}

interface DebriefForm {
  interview_id: number;
  rating: number;
  went_well: string;
  went_poorly: string;
  questions_asked: string;
  notes: string;
}

const outcomeColor: Record<string, string> = {
  passed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  pending: 'bg-yellow-100 text-yellow-700',
  ghosted: 'bg-gray-100 text-gray-500',
};

const emptyDebrief: DebriefForm = {
  interview_id: 0,
  rating: 3,
  went_well: '',
  went_poorly: '',
  questions_asked: '',
  notes: '',
};

export default function Interviews() {
  const qc = useQueryClient();
  const [showDebrief, setShowDebrief] = useState<number | null>(null);
  const [debrief, setDebrief] = useState<DebriefForm>(emptyDebrief);
  const [prepResult, setPrepResult] = useState<PrepResult | null>(null);
  const [prepLoading, setPrepLoading] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['interviews'],
    queryFn: () => interviews.list('?limit=50'),
  });

  const allInterviews = data ?? [];
  const now = new Date();
  const upcoming = allInterviews.filter((i: Interview) => i.date && new Date(i.date) >= now);
  const past = allInterviews.filter((i: Interview) => !i.date || new Date(i.date) < now);

  const generatePrep = async (interviewId: number) => {
    setPrepLoading(interviewId);
    setPrepResult(null);
    try {
      const result = await api.post<PrepResult>('/interviews/prep', { interview_id: interviewId });
      setPrepResult(result);
    } catch (e) {
      setPrepResult({ message: String(e) });
    } finally {
      setPrepLoading(null);
    }
  };

  const submitDebrief = useMutation({
    mutationFn: (data: DebriefForm) =>
      api.post<{ status: string }>('/interviews/debrief', {
        interview_id: data.interview_id,
        rating: data.rating,
        went_well: data.went_well,
        went_poorly: data.went_poorly,
        questions_asked: data.questions_asked,
        notes: data.notes,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['interviews'] });
      setShowDebrief(null);
      setDebrief(emptyDebrief);
    },
    onError: (err: any) => alert(err?.response?.data?.error || 'Failed to save debrief'),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Interviews</h1>
        <div className="flex gap-3 items-center">
          <a
            href="/mock-interviews"
            className="px-4 py-2 bg-blue-50 text-blue-600 text-sm rounded hover:bg-blue-100"
          >
            Mock Interviews
          </a>
          <span className="text-sm text-gray-500">{allInterviews.length} interviews</span>
        </div>
      </div>

      {/* Upcoming Interviews */}
      {upcoming.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Upcoming</h2>
          {upcoming.map((i: Interview) => (
            <div key={i.id} className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0">
              <div>
                <p className="text-sm font-medium text-gray-900">{i.company_name}</p>
                <p className="text-xs text-gray-500">{i.role} - {i.type}</p>
                <p className="text-xs text-gray-400">{i.date ? new Date(i.date).toLocaleString() : '-'}</p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => generatePrep(i.id)}
                  disabled={prepLoading === i.id}
                  className="text-xs px-3 py-1 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 disabled:opacity-50"
                >
                  {prepLoading === i.id ? 'Generating...' : 'Generate Prep'}
                </button>
                <button
                  onClick={() => { setShowDebrief(i.id); setDebrief({ ...emptyDebrief, interview_id: i.id }); }}
                  className="text-xs px-3 py-1 bg-gray-50 text-gray-600 rounded hover:bg-gray-100"
                >
                  Debrief
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Prep Result */}
      {prepResult && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <div className="flex justify-between items-start">
            <h3 className="text-sm font-semibold text-blue-900 mb-2">Interview Prep</h3>
            <button onClick={() => setPrepResult(null)} className="text-xs text-blue-400 hover:text-blue-600">Dismiss</button>
          </div>
          {prepResult.message && !prepResult.prep_notes && (
            <p className="text-sm text-red-600">{prepResult.message}</p>
          )}
          {prepResult.prep_notes && (
            <p className="text-sm text-gray-700 mb-2">{prepResult.prep_notes}</p>
          )}
          {prepResult.talking_points && prepResult.talking_points.length > 0 && (
            <div className="mb-2">
              <p className="text-xs font-medium text-blue-700 mb-1">Talking Points</p>
              <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
                {prepResult.talking_points.map((tp, idx) => <li key={idx}>{tp}</li>)}
              </ul>
            </div>
          )}
          {prepResult.questions && prepResult.questions.length > 0 && (
            <div>
              <p className="text-xs font-medium text-blue-700 mb-1">Likely Questions</p>
              <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
                {prepResult.questions.map((q, idx) => <li key={idx}>{q}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Debrief Form */}
      {showDebrief != null && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Post-Interview Debrief</h2>
          <div className="space-y-4 max-w-lg">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Rating (1-5)</label>
              <div className="flex gap-2">
                {[1, 2, 3, 4, 5].map(n => (
                  <button
                    key={n}
                    onClick={() => setDebrief(p => ({ ...p, rating: n }))}
                    className={`w-8 h-8 rounded text-sm font-medium ${
                      debrief.rating === n ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">What went well</label>
              <textarea
                rows={3}
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={debrief.went_well}
                onChange={e => setDebrief(p => ({ ...p, went_well: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">What didn't go well</label>
              <textarea
                rows={3}
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={debrief.went_poorly}
                onChange={e => setDebrief(p => ({ ...p, went_poorly: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Questions asked</label>
              <textarea
                rows={3}
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={debrief.questions_asked}
                onChange={e => setDebrief(p => ({ ...p, questions_asked: e.target.value }))}
                placeholder="One per line"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Additional notes</label>
              <textarea
                rows={2}
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={debrief.notes}
                onChange={e => setDebrief(p => ({ ...p, notes: e.target.value }))}
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => submitDebrief.mutate(debrief)}
                disabled={submitDebrief.isPending}
                className="px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-50"
              >
                {submitDebrief.isPending ? 'Saving...' : 'Save Debrief'}
              </button>
              <button
                onClick={() => { setShowDebrief(null); setDebrief(emptyDebrief); }}
                className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* All Interviews Table */}
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
              <th className="text-left px-4 py-3 font-medium text-gray-500">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
            )}
            {(past.length > 0 ? past : allInterviews).map((i: Interview) => (
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
                <td className="px-4 py-3">
                  <div className="flex gap-1">
                    <button
                      onClick={() => generatePrep(i.id)}
                      disabled={prepLoading === i.id}
                      className="text-xs px-2 py-1 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 disabled:opacity-50"
                    >
                      Prep
                    </button>
                    <button
                      onClick={() => { setShowDebrief(i.id); setDebrief({ ...emptyDebrief, interview_id: i.id }); }}
                      className="text-xs px-2 py-1 bg-gray-50 text-gray-600 rounded hover:bg-gray-100"
                    >
                      Debrief
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
