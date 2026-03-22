import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface MockInterviewQuestion {
  id: number;
  question: string;
  answer?: string;
  feedback?: string;
  score?: number;
}

interface MockInterview {
  id: number;
  job_title: string;
  company: string;
  interview_type: string;
  difficulty: string;
  overall_score?: number;
  questions?: MockInterviewQuestion[];
  created_at?: string;
}

interface MockInterviewDetail extends MockInterview {
  questions: MockInterviewQuestion[];
}

interface AnswerResponse {
  id: number;
  question_id: number;
  score?: number;
  feedback?: string;
}

interface EvaluateResponse {
  id: number;
  overall_score: number;
}

const INTERVIEW_TYPES = ['behavioral', 'technical', 'case', 'system_design', 'culture_fit'];
const DIFFICULTIES = ['easy', 'medium', 'hard'];

function ScoreBadge({ score }: { score?: number }) {
  if (score == null) return <span className="text-xs text-gray-400">Not scored</span>;
  const color = score >= 80 ? 'text-green-700' : score >= 60 ? 'text-yellow-700' : 'text-red-700';
  return <span className={`text-sm font-semibold ${color}`}>{score}/100</span>;
}

export default function MockInterviews() {
  const qc = useQueryClient();
  const [view, setView] = useState<'list' | 'detail'>('list');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [form, setForm] = useState({
    job_title: '', company: '', interview_type: 'behavioral', difficulty: 'medium',
  });

  const list = useQuery({
    queryKey: ['mock-interviews'],
    queryFn: () => api.get<MockInterview[]>('/mock-interviews'),
  });

  const detail = useQuery({
    queryKey: ['mock-interview', selectedId],
    queryFn: () => api.get<MockInterviewDetail>(`/mock-interviews/${selectedId}`),
    enabled: selectedId != null,
  });

  const createInterview = useMutation({
    mutationFn: (data: typeof form) => api.post<MockInterview>('/mock-interviews', data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['mock-interviews'] });
      setShowForm(false);
      setForm({ job_title: '', company: '', interview_type: 'behavioral', difficulty: 'medium' });
      setSelectedId(data.id);
      setView('detail');
    },
    onError: (error: Error) => {
      console.error('Failed to create mock interview:', error.message);
    },
  });

  const submitAnswer = useMutation({
    mutationFn: ({ id, questionId, answer }: { id: number; questionId: number; answer: string }) =>
      api.patch<AnswerResponse>(`/mock-interviews/${id}/answer`, { question_id: questionId, user_answer: answer }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mock-interview', selectedId] }),
    onError: (error: Error) => {
      console.error('Failed to submit answer:', error.message);
    },
  });

  const evaluate = useMutation({
    mutationFn: (id: number) => api.patch<EvaluateResponse>(`/mock-interviews/${id}/evaluate`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mock-interview', selectedId] }),
    onError: (error: Error) => {
      console.error('Failed to evaluate interview:', error.message);
    },
  });

  const interviews = list.data ?? [];
  const current = detail.data;

  if (view === 'detail' && selectedId != null) {
    return (
      <div>
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => setView('list')} className="text-sm text-blue-600 hover:underline">&larr; Back</button>
          <h1 className="text-2xl font-bold text-gray-900">
            {current?.company} &mdash; {current?.interview_type}
          </h1>
        </div>

        {detail.isLoading && <p className="text-sm text-gray-400">Loading...</p>}

        {current && (
          <div>
            <div className="flex items-center gap-4 mb-6">
              <ScoreBadge score={current.overall_score} />
              <span className="text-xs text-gray-400 capitalize">{current.difficulty}</span>
              <span className="text-xs text-gray-400">{current.job_title}</span>
            </div>

            {(current.questions ?? []).map((q: MockInterviewQuestion, idx: number) => (
              <div key={q.id} className="bg-white rounded-lg border border-gray-200 p-4 mb-4">
                <p className="text-sm font-medium text-gray-900 mb-2">Q{idx + 1}. {q.question}</p>
                <textarea
                  rows={4}
                  className="w-full text-sm border border-gray-200 rounded p-2 text-gray-800 focus:outline-none focus:ring-1 focus:ring-blue-400"
                  placeholder="Your answer..."
                  value={answers[q.id] ?? q.answer ?? ''}
                  onChange={e => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                />
                {q.feedback && (
                  <div className="mt-2 p-2 bg-gray-50 rounded text-xs text-gray-600">
                    <span className="font-medium">Feedback: </span>{q.feedback}
                  </div>
                )}
                {q.score != null && (
                  <p className="text-xs text-gray-500 mt-1">Score: <span className="font-medium">{q.score}/100</span></p>
                )}
                <button
                  onClick={() => submitAnswer.mutate({ id: selectedId, questionId: q.id, answer: answers[q.id] ?? q.answer ?? '' })}
                  className="mt-2 text-xs px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  Save Answer
                </button>
              </div>
            ))}

            <button
              onClick={() => evaluate.mutate(selectedId)}
              disabled={evaluate.isPending}
              className="mt-2 px-4 py-2 bg-green-600 text-white text-sm rounded hover:bg-green-700 disabled:opacity-50"
            >
              {evaluate.isPending ? 'Evaluating...' : 'Evaluate All Answers'}
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Mock Interviews</h1>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700"
        >
          + New Interview
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Start New Mock Interview</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Job Title</label>
              <input
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.job_title}
                onChange={e => setForm(p => ({ ...p, job_title: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Company</label>
              <input
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.company}
                onChange={e => setForm(p => ({ ...p, company: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Interview Type</label>
              <select
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none"
                value={form.interview_type}
                onChange={e => setForm(p => ({ ...p, interview_type: e.target.value }))}
              >
                {INTERVIEW_TYPES.map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Difficulty</label>
              <select
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none"
                value={form.difficulty}
                onChange={e => setForm(p => ({ ...p, difficulty: e.target.value }))}
              >
                {DIFFICULTIES.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button
              onClick={() => createInterview.mutate(form)}
              disabled={createInterview.isPending || !form.job_title}
              className="px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-50"
            >
              {createInterview.isPending ? 'Creating...' : 'Start Interview'}
            </button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded">
              Cancel
            </button>
          </div>
        </div>
      )}

      {list.isLoading && <p className="text-sm text-gray-400">Loading...</p>}
      {!list.isLoading && interviews.length === 0 && (
        <p className="text-sm text-gray-400">No mock interviews yet. Start one above.</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {interviews.map((iv: MockInterview) => (
          <div
            key={iv.id}
            className="bg-white rounded-lg border border-gray-200 p-4 cursor-pointer hover:border-blue-300"
            onClick={() => { setSelectedId(iv.id); setView('detail'); }}
          >
            <div className="flex justify-between items-start mb-2">
              <p className="text-sm font-semibold text-gray-900">{iv.company}</p>
              <ScoreBadge score={iv.overall_score} />
            </div>
            <p className="text-xs text-gray-600">{iv.job_title}</p>
            <div className="flex gap-2 mt-2">
              <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded capitalize">{iv.interview_type?.replace('_', ' ')}</span>
              <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded capitalize">{iv.difficulty}</span>
            </div>
            <p className="text-xs text-gray-400 mt-2">
              {iv.created_at ? new Date(iv.created_at).toLocaleDateString() : ''}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
