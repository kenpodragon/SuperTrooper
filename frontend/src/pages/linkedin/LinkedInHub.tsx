import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

// ── Types ──────────────────────────────────────────────────────────────────

interface ProfileAudit {
  id: number;
  audit_type: string;
  overall_score: number;
  section_scores: Record<string, number>;
  recommendations: { text: string; priority: string; section: string }[];
  created_at: string;
}

interface ThemePillar {
  id: number;
  name: string;
  description?: string;
  color?: string;
  post_count?: number;
}

interface LinkedInPost {
  id: number;
  hook_text: string;
  body?: string;
  status: string;
  post_type?: string;
  theme_pillar_id?: number;
  theme_pillar_name?: string;
  engagement_rate?: number;
  likes?: number;
  comments?: number;
  shares?: number;
  created_at: string;
}

interface ContentAnalytics {
  days: number;
  overall: {
    total_posts: number;
    published: number;
    drafts: number;
    avg_char_count: number | null;
  };
  by_type: { post_type: string; count: number }[];
  by_theme: { theme: string; count: number }[];
  top_posts: unknown[];
}

interface SkillsAudit {
  id: number;
  keep: { name: string; reason?: string }[];
  add: { name: string; reason?: string }[];
  remove: { name: string; reason?: string }[];
  reprioritize: { name: string; from?: number; to?: number; reason?: string }[];
  top_50: string[];
  endorsement_gaps: { name: string; current: number; target: number }[];
  created_at: string;
}

interface VoiceRule {
  id: number;
  category: string;
  rule_text: string;
  created_at?: string;
}

// ── Tab definitions ────────────────────────────────────────────────────────

interface EndorsementStrategy {
  skill_id: number;
  skill_name: string;
  endorsement_count: number;
  priority: string;
  category: string | null;
  proficiency: string | null;
  suggested_endorsers: { name: string; title: string; company: string; relationship_strength: string }[];
}

interface ScheduledPost {
  id: number;
  post_id?: number;
  hook_text?: string;
  scheduled_for: string;
  status: string;
  post_type?: string;
  theme_pillar_name?: string;
}

type Tab = 'scorecard' | 'content' | 'skills' | 'endorsements' | 'schedule' | 'voice';

const TABS: { key: Tab; label: string }[] = [
  { key: 'scorecard', label: 'Profile Scorecard' },
  { key: 'content', label: 'Content Dashboard' },
  { key: 'skills', label: 'Skills Manager' },
  { key: 'endorsements', label: 'Endorsements' },
  { key: 'schedule', label: 'Schedule' },
  { key: 'voice', label: 'Voice Guide' },
];

const PRIORITY_COLORS: Record<string, string> = {
  high: 'bg-red-500/20 text-red-400 border-red-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-green-500/20 text-green-400 border-green-500/30',
};

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-600 text-gray-300',
  published: 'bg-green-600/20 text-green-400',
  scheduled: 'bg-blue-600/20 text-blue-400',
};

const VOICE_CATEGORIES = ['tone', 'structure', 'vocabulary', 'hook', 'cta', 'banned_patterns'];
const PERSONA_OPTIONS = ['executive', 'technical', 'creative', 'academic'];

// ── Helpers ────────────────────────────────────────────────────────────────

function ScoreBar({ label, score }: { label: string; score: number }) {
  const pct = Math.min(100, Math.max(0, score));
  const color = pct >= 80 ? 'bg-green-500' : pct >= 60 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-gray-300 capitalize">{label.replace(/_/g, ' ')}</span>
        <span className="text-white font-medium">{score}%</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="w-6 h-6 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
    </div>
  );
}


function EmptyState({ message, cta, onClick }: { message: string; cta: string; onClick: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <p className="text-gray-500 mb-4">{message}</p>
      <button onClick={onClick} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm">
        {cta}
      </button>
    </div>
  );
}

// ── Profile Scorecard Tab ──────────────────────────────────────────────────

function ProfileScorecard() {
  const qc = useQueryClient();

  const { data: audit, isLoading, error } = useQuery({
    queryKey: ['linkedin-profile-audit'],
    queryFn: () => api.get<ProfileAudit>('/linkedin/profile-audits/latest'),
    retry: false,
  });

  const runAudit = useMutation({
    mutationFn: () => api.post<ProfileAudit>('/linkedin/profile-audits', { audit_type: 'full' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['linkedin-profile-audit'] }),
    onError: (error: Error) => {
      console.error('Failed to run profile audit:', error.message);
    },
  });

  if (isLoading) return <Spinner />;
  if (error && !audit) {
    return (
      <EmptyState
        message="No profile audits yet. Run your first audit to get a LinkedIn profile scorecard."
        cta="Run Your First Profile Audit"
        onClick={() => runAudit.mutate()}
      />
    );
  }
  if (!audit) return null;

  const sections = audit.section_scores ?? {};
  const recs = audit.recommendations ?? [];

  return (
    <div className="space-y-6">
      {/* Overall Score */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 flex items-center gap-6">
        <div className="flex-shrink-0 w-24 h-24 rounded-full border-4 border-green-500 flex items-center justify-center">
          <span className="text-3xl font-bold text-white">{audit.overall_score}</span>
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-white mb-1">Overall Profile Score</h3>
          <p className="text-sm text-gray-400">
            Audited {audit.created_at ? new Date(audit.created_at).toLocaleDateString() : 'recently'}
            {' '}&middot; {audit.audit_type} audit
          </p>
          <button
            onClick={() => runAudit.mutate()}
            disabled={runAudit.isPending}
            className="mt-3 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50"
          >
            {runAudit.isPending ? 'Running...' : 'Run New Audit'}
          </button>
        </div>
      </div>

      {/* Section Scores */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="text-base font-semibold text-white mb-4">Section Scores</h3>
        <div className="space-y-3">
          {Object.entries(sections).map(([section, score]) => (
            <ScoreBar key={section} label={section} score={score as number} />
          ))}
        </div>
      </div>

      {/* Recommendations */}
      {recs.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-base font-semibold text-white mb-3">Recommendations</h3>
          <div className="space-y-2">
            {recs.map((rec, i) => (
              <div key={i} className="flex items-start gap-3 py-2 border-b border-gray-700 last:border-0">
                <span className={`text-xs px-2 py-0.5 rounded-full border ${PRIORITY_COLORS[rec.priority] ?? 'bg-gray-600 text-gray-300'}`}>
                  {rec.priority}
                </span>
                <div className="flex-1">
                  <p className="text-sm text-gray-300">{rec.text}</p>
                  <p className="text-xs text-gray-500 mt-0.5 capitalize">{rec.section?.replace(/_/g, ' ')}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Content Dashboard Tab ──────────────────────────────────────────────────

function ContentDashboard() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<'all' | 'draft' | 'published'>('all');
  const [newPost, setNewPost] = useState({ topic: '', theme_pillar_id: '', post_type: 'thought_leadership' });
  const [showForm, setShowForm] = useState(false);

  const pillars = useQuery({
    queryKey: ['linkedin-theme-pillars'],
    queryFn: () => api.get<ThemePillar[]>('/linkedin/theme-pillars'),
  });

  const posts = useQuery({
    queryKey: ['linkedin-posts', statusFilter],
    queryFn: () => {
      const params = statusFilter !== 'all' ? `?status=${statusFilter}` : '';
      return api.get<LinkedInPost[]>(`/linkedin/posts${params}`);
    },
  });

  const analytics = useQuery({
    queryKey: ['linkedin-content-analytics'],
    queryFn: () => api.get<ContentAnalytics>('/linkedin/analytics/content'),
  });

  const createPost = useMutation({
    mutationFn: (data: typeof newPost) =>
      api.post<LinkedInPost>('/linkedin/posts', {
        ...data,
        theme_pillar_id: data.theme_pillar_id ? Number(data.theme_pillar_id) : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['linkedin-posts'] });
      qc.invalidateQueries({ queryKey: ['linkedin-content-analytics'] });
      setShowForm(false);
      setNewPost({ topic: '', theme_pillar_id: '', post_type: 'thought_leadership' });
    },
    onError: (error: Error) => {
      console.error('Failed to create post:', error.message);
    },
  });

  const deletePillar = useMutation({
    mutationFn: (id: number) => api.del<void>(`/linkedin/theme-pillars/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['linkedin-theme-pillars'] }),
    onError: (error: Error) => {
      console.error('Failed to delete theme pillar:', error.message);
    },
  });

  const pillarList = pillars.data ?? [];
  const postList = posts.data ?? [];
  const stats = analytics.data;

  return (
    <div className="space-y-6">
      {/* Analytics Summary */}
      {stats && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'Total Posts', value: stats.overall?.total_posts ?? 0 },
            { label: 'Published', value: stats.overall?.published ?? 0 },
            { label: 'Drafts', value: stats.overall?.drafts ?? 0 },
          ].map((s) => (
            <div key={s.label} className="bg-gray-800 rounded-lg p-4 border border-gray-700 text-center">
              <p className="text-2xl font-bold text-white">{s.value}</p>
              <p className="text-xs text-gray-400 mt-1">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Theme Pillars */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="text-base font-semibold text-white mb-3">Theme Pillars</h3>
        {pillars.isLoading && <Spinner />}
        {pillarList.length === 0 && !pillars.isLoading && (
          <p className="text-sm text-gray-500">No theme pillars yet.</p>
        )}
        <div className="flex flex-wrap gap-2">
          {pillarList.map((p) => (
            <div key={p.id} className="flex items-center gap-2 bg-gray-700 rounded-full px-3 py-1.5">
              {p.color && <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: p.color }} />}
              <span className="text-sm text-gray-200">{p.name}</span>
              {p.post_count != null && <span className="text-xs text-gray-400">({p.post_count})</span>}
              <button
                onClick={() => deletePillar.mutate(p.id)}
                className="text-gray-500 hover:text-red-400 text-xs ml-1"
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Posts */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-base font-semibold text-white">Posts</h3>
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {(['all', 'draft', 'published'] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={`px-3 py-1 text-xs rounded ${
                    statusFilter === s
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                  }`}
                >
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
            <button
              onClick={() => setShowForm(!showForm)}
              className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-xs"
            >
              + New Post
            </button>
          </div>
        </div>

        {/* New Post Form */}
        {showForm && (
          <div className="bg-gray-900 rounded-lg p-4 mb-4 border border-gray-600">
            <div className="grid grid-cols-3 gap-3 mb-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Topic</label>
                <input
                  className="bg-gray-700 border border-gray-600 text-white rounded px-3 py-2 text-sm w-full"
                  placeholder="What do you want to write about?"
                  value={newPost.topic}
                  onChange={(e) => setNewPost((p) => ({ ...p, topic: e.target.value }))}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Theme Pillar</label>
                <select
                  className="bg-gray-700 border border-gray-600 text-white rounded px-3 py-2 text-sm w-full"
                  value={newPost.theme_pillar_id}
                  onChange={(e) => setNewPost((p) => ({ ...p, theme_pillar_id: e.target.value }))}
                >
                  <option value="">None</option>
                  {pillarList.map((pl) => (
                    <option key={pl.id} value={pl.id}>{pl.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Type</label>
                <select
                  className="bg-gray-700 border border-gray-600 text-white rounded px-3 py-2 text-sm w-full"
                  value={newPost.post_type}
                  onChange={(e) => setNewPost((p) => ({ ...p, post_type: e.target.value }))}
                >
                  {['thought_leadership', 'case_study', 'hot_take', 'story', 'how_to', 'engagement'].map((t) => (
                    <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => createPost.mutate(newPost)}
                disabled={createPost.isPending || !newPost.topic}
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50"
              >
                {createPost.isPending ? 'Creating...' : 'Create Post'}
              </button>
              <button onClick={() => setShowForm(false)} className="bg-gray-700 hover:bg-gray-600 text-gray-300 px-3 py-1.5 rounded text-sm">
                Cancel
              </button>
            </div>
          </div>
        )}

        {posts.isLoading && <Spinner />}
        {!posts.isLoading && postList.length === 0 && (
          <p className="text-sm text-gray-500 py-4 text-center">No posts found.</p>
        )}
        <div className="space-y-2">
          {postList.map((post) => (
            <div key={post.id} className="bg-gray-900 rounded-lg p-3 border border-gray-700">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-200 line-clamp-2">{post.hook_text}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[post.status] ?? 'bg-gray-600 text-gray-300'}`}>
                      {post.status}
                    </span>
                    {post.theme_pillar_name && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-purple-600/20 text-purple-400">
                        {post.theme_pillar_name}
                      </span>
                    )}
                    {post.post_type && (
                      <span className="text-xs text-gray-500">{post.post_type.replace(/_/g, ' ')}</span>
                    )}
                  </div>
                </div>
                {post.status === 'published' && (
                  <div className="text-right shrink-0">
                    <div className="flex gap-3 text-xs text-gray-400">
                      {post.likes != null && <span>{post.likes} likes</span>}
                      {post.comments != null && <span>{post.comments} comments</span>}
                      {post.shares != null && <span>{post.shares} shares</span>}
                    </div>
                    {post.engagement_rate != null && (
                      <p className="text-xs text-green-400 mt-1">{(post.engagement_rate * 100).toFixed(1)}% engagement</p>
                    )}
                  </div>
                )}
              </div>
              <p className="text-xs text-gray-500 mt-2">
                {post.created_at ? new Date(post.created_at).toLocaleDateString() : ''}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Skills Manager Tab ─────────────────────────────────────────────────────

function SkillsManager() {
  const qc = useQueryClient();

  const { data: audit, isLoading, error } = useQuery({
    queryKey: ['linkedin-skills-audit'],
    queryFn: () => api.get<Record<string, unknown>>('/linkedin/skills-audits/latest'),
    retry: false,
    select: (d): SkillsAudit => ({
      id: d.id as number,
      keep: (d.skills_keep ?? d.keep ?? []) as SkillsAudit['keep'],
      add: (d.skills_add ?? d.add ?? []) as SkillsAudit['add'],
      remove: (d.skills_remove ?? d.remove ?? []) as SkillsAudit['remove'],
      reprioritize: (d.skills_reprioritize ?? d.reprioritize ?? []) as SkillsAudit['reprioritize'],
      top_50: (d.top_50 ?? []) as string[],
      endorsement_gaps: (d.endorsement_gaps ?? []) as SkillsAudit['endorsement_gaps'],
      created_at: d.created_at as string,
    }),
  });

  const runAudit = useMutation({
    mutationFn: () => api.post<SkillsAudit>('/linkedin/skills-audits', {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['linkedin-skills-audit'] }),
    onError: (error: Error) => {
      console.error('Failed to run skills audit:', error.message);
    },
  });

  if (isLoading) return <Spinner />;
  if (error && !audit) {
    return (
      <EmptyState
        message="No skills audits yet. Run an audit to optimize your LinkedIn skills section."
        cta="Run Skills Audit"
        onClick={() => runAudit.mutate()}
      />
    );
  }
  if (!audit) return null;

  const SKILL_SECTIONS: { key: keyof Pick<SkillsAudit, 'keep' | 'add' | 'remove' | 'reprioritize'>; label: string; color: string; badgeColor: string }[] = [
    { key: 'keep', label: 'Keep', color: 'border-green-500/40', badgeColor: 'bg-green-500/20 text-green-400' },
    { key: 'add', label: 'Add', color: 'border-blue-500/40', badgeColor: 'bg-blue-500/20 text-blue-400' },
    { key: 'remove', label: 'Remove', color: 'border-red-500/40', badgeColor: 'bg-red-500/20 text-red-400' },
    { key: 'reprioritize', label: 'Reprioritize', color: 'border-yellow-500/40', badgeColor: 'bg-yellow-500/20 text-yellow-400' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">
          Audited {audit.created_at ? new Date(audit.created_at).toLocaleDateString() : 'recently'}
        </p>
        <button
          onClick={() => runAudit.mutate()}
          disabled={runAudit.isPending}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50"
        >
          {runAudit.isPending ? 'Running...' : 'Run Skills Audit'}
        </button>
      </div>

      {/* Four skill sections */}
      <div className="grid grid-cols-2 gap-4">
        {SKILL_SECTIONS.map((section) => {
          const items = (audit[section.key] as { name: string; reason?: string; from?: number; to?: number }[]) ?? [];
          return (
            <div key={section.key} className={`bg-gray-800 rounded-lg p-4 border ${section.color}`}>
              <div className="flex items-center gap-2 mb-3">
                <span className={`text-xs px-2 py-0.5 rounded-full ${section.badgeColor}`}>
                  {section.label}
                </span>
                <span className="text-xs text-gray-500">{items.length} skills</span>
              </div>
              {items.length === 0 && <p className="text-xs text-gray-500 italic">None</p>}
              <div className="space-y-1.5">
                {items.map((item: { name: string; reason?: string; from?: number; to?: number }, i: number) => (
                  <div key={i} className="flex items-center justify-between">
                    <span className="text-sm text-gray-300">{item.name}</span>
                    {item.reason && <span className="text-xs text-gray-500 truncate ml-2 max-w-[50%]">{item.reason}</span>}
                    {item.from != null && item.to != null && (
                      <span className="text-xs text-gray-400">#{item.from} → #{item.to}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Top 50 Skills */}
      {(audit.top_50 ?? []).length > 0 && (
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-base font-semibold text-white mb-3">Top 50 Recommended Skills</h3>
          <div className="flex flex-wrap gap-2">
            {(audit.top_50 ?? []).map((skill, i) => (
              <span key={i} className="text-xs bg-gray-700 text-gray-300 px-2.5 py-1 rounded-full">
                <span className="text-gray-500 mr-1">{i + 1}.</span> {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Endorsement Gaps */}
      {(audit.endorsement_gaps ?? []).length > 0 && (
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-base font-semibold text-white mb-3">Endorsement Gaps</h3>
          <div className="space-y-2">
            {(audit.endorsement_gaps ?? []).map((gap, i) => (
              <div key={i} className="flex items-center justify-between">
                <span className="text-sm text-gray-300">{gap.name}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-red-400">{gap.current} endorsements</span>
                  <span className="text-xs text-gray-500">→</span>
                  <span className="text-xs text-green-400">target {gap.target}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Voice Guide Tab ────────────────────────────────────────────────────────

function VoiceGuide() {
  const qc = useQueryClient();
  const [expandedCats, setExpandedCats] = useState<Set<string>>(new Set(['tone']));
  const [newRule, setNewRule] = useState({ category: 'tone', rule_text: '' });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState('');
  const [voiceTestText, setVoiceTestText] = useState('');
  const [showTemplateMenu, setShowTemplateMenu] = useState(false);

  const { data: rules, isLoading } = useQuery({
    queryKey: ['linkedin-voice-rules'],
    queryFn: () => api.get<VoiceRule[]>('/linkedin/voice-rules'),
  });

  const addRule = useMutation({
    mutationFn: (data: typeof newRule) => api.post<VoiceRule>('/linkedin/voice-rules', data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['linkedin-voice-rules'] });
      setNewRule((p) => ({ ...p, rule_text: '' }));
    },
    onError: (error: Error) => {
      console.error('Failed to add voice rule:', error.message);
    },
  });

  const updateRule = useMutation({
    mutationFn: ({ id, rule_text }: { id: number; rule_text: string }) =>
      api.patch<VoiceRule>(`/linkedin/voice-rules/${id}`, { rule_text }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['linkedin-voice-rules'] });
      setEditingId(null);
    },
    onError: (error: Error) => {
      console.error('Failed to update voice rule:', error.message);
    },
  });

  const deleteRule = useMutation({
    mutationFn: (id: number) => api.del<void>(`/linkedin/voice-rules/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['linkedin-voice-rules'] }),
    onError: (error: Error) => {
      console.error('Failed to delete voice rule:', error.message);
    },
  });

  const loadTemplate = useMutation({
    mutationFn: (persona: string) =>
      api.post<VoiceRule[]>('/linkedin/voice-rules/template', { persona }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['linkedin-voice-rules'] });
      setShowTemplateMenu(false);
    },
    onError: (error: Error) => {
      console.error('Failed to load voice template:', error.message);
    },
  });

  const voiceCheck = useMutation({
    mutationFn: (text: string) =>
      api.post<{ violations: { rule: string; category: string }[]; passed: boolean }>('/linkedin/voice-check', { text }),
    onError: (error: Error) => {
      console.error('Failed to check voice:', error.message);
    },
  });

  const ruleList = rules ?? [];
  const grouped: Record<string, VoiceRule[]> = {};
  VOICE_CATEGORIES.forEach((c) => { grouped[c] = []; });
  ruleList.forEach((r) => {
    if (grouped[r.category]) grouped[r.category].push(r);
    else {
      grouped[r.category] = grouped[r.category] ?? [];
      grouped[r.category].push(r);
    }
  });

  const toggleCat = (cat: string) => {
    setExpandedCats((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      {/* Actions bar */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">{ruleList.length} voice rules configured</p>
        <div className="relative">
          <button
            onClick={() => setShowTemplateMenu(!showTemplateMenu)}
            className="bg-gray-700 hover:bg-gray-600 text-gray-300 px-3 py-1.5 rounded text-sm"
          >
            Load Template
          </button>
          {showTemplateMenu && (
            <div className="absolute right-0 mt-1 bg-gray-800 border border-gray-600 rounded-lg shadow-lg z-10 py-1 w-40">
              {PERSONA_OPTIONS.map((p) => (
                <button
                  key={p}
                  onClick={() => loadTemplate.mutate(p)}
                  className="block w-full text-left px-3 py-2 text-sm text-gray-300 hover:bg-gray-700 capitalize"
                >
                  {p}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Add Rule */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="text-sm font-semibold text-white mb-3">Add New Rule</h3>
        <div className="flex gap-3">
          <select
            className="bg-gray-700 border border-gray-600 text-white rounded px-3 py-2 text-sm"
            value={newRule.category}
            onChange={(e) => setNewRule((p) => ({ ...p, category: e.target.value }))}
          >
            {VOICE_CATEGORIES.map((c) => (
              <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
            ))}
          </select>
          <input
            className="bg-gray-700 border border-gray-600 text-white rounded px-3 py-2 text-sm flex-1"
            placeholder="Rule text..."
            value={newRule.rule_text}
            onChange={(e) => setNewRule((p) => ({ ...p, rule_text: e.target.value }))}
            onKeyDown={(e) => e.key === 'Enter' && newRule.rule_text && addRule.mutate(newRule)}
          />
          <button
            onClick={() => addRule.mutate(newRule)}
            disabled={addRule.isPending || !newRule.rule_text}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50"
          >
            Add
          </button>
        </div>
      </div>

      {/* Rules by Category */}
      {isLoading && <Spinner />}
      {VOICE_CATEGORIES.map((cat) => {
        const catRules = grouped[cat] ?? [];
        if (catRules.length === 0 && !isLoading) return null;
        const expanded = expandedCats.has(cat);
        return (
          <div key={cat} className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
            <button
              onClick={() => toggleCat(cat)}
              className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-750"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-white capitalize">{cat.replace(/_/g, ' ')}</span>
                <span className="text-xs text-gray-500">{catRules.length}</span>
              </div>
              <span className="text-gray-400 text-sm">{expanded ? '▾' : '▸'}</span>
            </button>
            {expanded && (
              <div className="border-t border-gray-700 px-4 py-2">
                {catRules.map((rule) => (
                  <div key={rule.id} className="flex items-center gap-2 py-2 border-b border-gray-700 last:border-0">
                    {editingId === rule.id ? (
                      <>
                        <input
                          className="bg-gray-700 border border-gray-600 text-white rounded px-2 py-1 text-sm flex-1"
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && updateRule.mutate({ id: rule.id, rule_text: editText })}
                        />
                        <button
                          onClick={() => updateRule.mutate({ id: rule.id, rule_text: editText })}
                          className="text-xs text-green-400 hover:text-green-300"
                        >
                          Save
                        </button>
                        <button onClick={() => setEditingId(null)} className="text-xs text-gray-400 hover:text-gray-300">
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <p className="text-sm text-gray-300 flex-1">{rule.rule_text}</p>
                        <button
                          onClick={() => { setEditingId(rule.id); setEditText(rule.rule_text); }}
                          className="text-xs text-blue-400 hover:text-blue-300"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => deleteRule.mutate(rule.id)}
                          className="text-xs text-red-400 hover:text-red-300"
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}

      {/* Voice Check */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="text-sm font-semibold text-white mb-3">Test Voice</h3>
        <textarea
          className="bg-gray-700 border border-gray-600 text-white rounded px-3 py-2 text-sm w-full h-24 resize-none"
          placeholder="Paste your LinkedIn text here to check for voice violations..."
          value={voiceTestText}
          onChange={(e) => setVoiceTestText(e.target.value)}
        />
        <div className="flex items-center gap-3 mt-3">
          <button
            onClick={() => voiceCheck.mutate(voiceTestText)}
            disabled={voiceCheck.isPending || !voiceTestText}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50"
          >
            {voiceCheck.isPending ? 'Checking...' : 'Check Voice'}
          </button>
          {voiceCheck.data && (
            <span className={`text-sm ${voiceCheck.data.passed ? 'text-green-400' : 'text-red-400'}`}>
              {voiceCheck.data.passed ? 'All clear — no violations!' : `${voiceCheck.data.violations.length} violation(s) found`}
            </span>
          )}
        </div>
        {voiceCheck.data && !voiceCheck.data.passed && (
          <div className="mt-3 space-y-1">
            {voiceCheck.data.violations.map((v, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className="text-red-400">&#x2717;</span>
                <span className="text-gray-300">{v.rule}</span>
                <span className="text-xs text-gray-500 capitalize">({v.category})</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Endorsement Strategy Tab ──────────────────────────────────────────────

function EndorsementStrategy() {
  const qc = useQueryClient();

  const { data: strategies, isLoading, error } = useQuery({
    queryKey: ['linkedin-endorsement-strategy'],
    queryFn: () => api.get<{ skills: EndorsementStrategy[]; low_endorsement_count: number }>('/linkedin/endorsement-strategy'),
    select: (d) => d.skills ?? [],
    retry: false,
  });

  // No POST generate endpoint — data comes from skills table via GET
  const generate = {
    mutate: () => qc.invalidateQueries({ queryKey: ['linkedin-endorsement-strategy'] }),
    isPending: false,
  };

  if (isLoading) return <Spinner />;
  if ((error || !strategies || strategies.length === 0) && !isLoading) {
    return (
      <EmptyState
        message="No endorsement strategy yet. Generate one to identify which skills need endorsements and who to ask."
        cta="Generate Endorsement Strategy"
        onClick={() => generate.mutate()}
      />
    );
  }

  const items = strategies ?? [];
  const highPriority = items.filter((s) => s.priority === 'high');
  const medPriority = items.filter((s) => s.priority === 'medium');
  const lowPriority = items.filter((s) => s.priority === 'low');

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">{items.length} skills with endorsement strategies</p>
        <button
          onClick={() => generate.mutate()}
          disabled={generate.isPending}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50"
        >
          {generate.isPending ? 'Generating...' : 'Regenerate Strategy'}
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'High Priority', count: highPriority.length, color: 'text-red-400' },
          { label: 'Medium Priority', count: medPriority.length, color: 'text-yellow-400' },
          { label: 'Low Priority', count: lowPriority.length, color: 'text-green-400' },
        ].map((s) => (
          <div key={s.label} className="bg-gray-800 rounded-lg p-4 border border-gray-700 text-center">
            <p className={`text-2xl font-bold ${s.color}`}>{s.count}</p>
            <p className="text-xs text-gray-400 mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Strategy cards */}
      {items.map((strategy) => (
        <div key={strategy.skill_id} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-white">{strategy.skill_name}</h4>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded-full border ${PRIORITY_COLORS[strategy.priority] ?? 'bg-gray-600 text-gray-300'}`}>
                {strategy.priority}
              </span>
              <span className="text-xs text-gray-400">
                {strategy.endorsement_count} endorsements
              </span>
              {strategy.category && (
                <span className="text-xs text-gray-500">{strategy.category}</span>
              )}
            </div>
          </div>

          {strategy.suggested_endorsers && strategy.suggested_endorsers.length > 0 && (
            <div className="mt-2">
              <p className="text-xs text-gray-500 mb-1">Suggested endorsers:</p>
              <div className="flex flex-wrap gap-2">
                {strategy.suggested_endorsers.map((c, i) => (
                  <span key={i} className="text-xs bg-gray-700 text-gray-300 px-2 py-1 rounded-full" title={`${c.title} at ${c.company} (${c.relationship_strength})`}>
                    {c.name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Post Schedule Tab ────────────────────────────────────────────────────────

function PostSchedule() {
  const qc = useQueryClient();
  const [scheduleForm, setScheduleForm] = useState({ post_id: '', scheduled_for: '' });

  const { data: scheduled, isLoading } = useQuery({
    queryKey: ['linkedin-scheduled-posts'],
    queryFn: () => api.get<ScheduledPost[]>('/linkedin/posts?status=scheduled'),
    retry: false,
  });

  const drafts = useQuery({
    queryKey: ['linkedin-draft-posts'],
    queryFn: () => api.get<LinkedInPost[]>('/linkedin/posts?status=draft'),
  });

  const schedulePost = useMutation({
    mutationFn: (data: { post_id: number; scheduled_for: string }) =>
      api.patch<LinkedInPost>(`/linkedin/posts/${data.post_id}`, {
        status: 'scheduled',
        scheduled_for: data.scheduled_for,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['linkedin-scheduled-posts'] });
      qc.invalidateQueries({ queryKey: ['linkedin-draft-posts'] });
      qc.invalidateQueries({ queryKey: ['linkedin-posts'] });
      setScheduleForm({ post_id: '', scheduled_for: '' });
    },
  });

  const unschedule = useMutation({
    mutationFn: (postId: number) =>
      api.patch<LinkedInPost>(`/linkedin/posts/${postId}`, { status: 'draft', scheduled_for: null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['linkedin-scheduled-posts'] });
      qc.invalidateQueries({ queryKey: ['linkedin-draft-posts'] });
    },
  });

  const scheduledList = scheduled ?? [];
  const draftList = drafts.data ?? [];

  // Group scheduled posts by date
  const byDate: Record<string, ScheduledPost[]> = {};
  scheduledList.forEach((p) => {
    const dateKey = p.scheduled_for ? new Date(p.scheduled_for).toLocaleDateString() : 'Unscheduled';
    if (!byDate[dateKey]) byDate[dateKey] = [];
    byDate[dateKey].push(p);
  });

  return (
    <div className="space-y-6">
      {/* Schedule a draft */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="text-sm font-semibold text-white mb-3">Schedule a Draft Post</h3>
        <div className="flex gap-3">
          <select
            className="bg-gray-700 border border-gray-600 text-white rounded px-3 py-2 text-sm flex-1"
            value={scheduleForm.post_id}
            onChange={(e) => setScheduleForm((p) => ({ ...p, post_id: e.target.value }))}
          >
            <option value="">Select a draft post...</option>
            {draftList.map((d) => (
              <option key={d.id} value={d.id}>
                {d.hook_text?.substring(0, 60) || `Post #${d.id}`}
                {d.post_type ? ` (${d.post_type.replace(/_/g, ' ')})` : ''}
              </option>
            ))}
          </select>
          <input
            type="datetime-local"
            className="bg-gray-700 border border-gray-600 text-white rounded px-3 py-2 text-sm"
            value={scheduleForm.scheduled_for}
            onChange={(e) => setScheduleForm((p) => ({ ...p, scheduled_for: e.target.value }))}
          />
          <button
            onClick={() => {
              if (scheduleForm.post_id && scheduleForm.scheduled_for) {
                schedulePost.mutate({
                  post_id: Number(scheduleForm.post_id),
                  scheduled_for: new Date(scheduleForm.scheduled_for).toISOString(),
                });
              }
            }}
            disabled={!scheduleForm.post_id || !scheduleForm.scheduled_for || schedulePost.isPending}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50 whitespace-nowrap"
          >
            {schedulePost.isPending ? 'Scheduling...' : 'Schedule'}
          </button>
        </div>
      </div>

      {/* Calendar view of scheduled posts */}
      {isLoading && <Spinner />}
      {!isLoading && scheduledList.length === 0 && (
        <div className="text-center py-8">
          <p className="text-gray-500">No posts scheduled. Select a draft post above to schedule it.</p>
        </div>
      )}

      {Object.entries(byDate)
        .sort(([a], [b]) => new Date(a).getTime() - new Date(b).getTime())
        .map(([dateStr, posts]) => (
          <div key={dateStr} className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
            <div className="px-4 py-2 bg-gray-750 border-b border-gray-700">
              <h3 className="text-sm font-medium text-gray-300">{dateStr}</h3>
            </div>
            <div className="divide-y divide-gray-700">
              {posts.map((post) => (
                <div key={post.id} className="px-4 py-3 flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-200 truncate">
                      {post.hook_text || `Post #${post.post_id || post.id}`}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-blue-400">
                        {post.scheduled_for
                          ? new Date(post.scheduled_for).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                          : 'Time TBD'}
                      </span>
                      {post.post_type && (
                        <span className="text-xs text-gray-500">{post.post_type.replace(/_/g, ' ')}</span>
                      )}
                      {post.theme_pillar_name && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-purple-600/20 text-purple-400">
                          {post.theme_pillar_name}
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => unschedule.mutate(post.post_id || post.id)}
                    className="text-xs text-red-400 hover:text-red-300 ml-3"
                  >
                    Unschedule
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
    </div>
  );
}

// ── Main Hub Component ─────────────────────────────────────────────────────

export default function LinkedInHub() {
  const [activeTab, setActiveTab] = useState<Tab>('scorecard');

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">LinkedIn Hub</h1>

      {/* Tab Bar */}
      <div className="flex gap-1 bg-gray-800 rounded-lg p-1 border border-gray-700">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`flex-1 px-4 py-2 text-sm rounded-md transition-colors ${
              activeTab === t.key
                ? 'bg-blue-600 text-white font-medium'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'scorecard' && <ProfileScorecard />}
      {activeTab === 'content' && <ContentDashboard />}
      {activeTab === 'skills' && <SkillsManager />}
      {activeTab === 'endorsements' && <EndorsementStrategy />}
      {activeTab === 'schedule' && <PostSchedule />}
      {activeTab === 'voice' && <VoiceGuide />}
    </div>
  );
}
