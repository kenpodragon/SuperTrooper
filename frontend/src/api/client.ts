const BASE = import.meta.env.VITE_API_URL || '/api';

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};

// --- Typed API functions ---

export interface Application {
  id: number;
  company_id?: number;
  company_name?: string;
  role?: string;
  date_applied?: string;
  source?: string;
  status?: string;
  resume_version?: string;
  jd_url?: string;
  contact_name?: string;
  contact_email?: string;
  notes?: string;
  last_status_change?: string;
  created_at?: string;
  updated_at?: string;
}

export interface SavedJob {
  id: number;
  url?: string;
  title: string;
  company?: string;
  company_id?: number;
  location?: string;
  salary_range?: string;
  source?: string;
  jd_text?: string;
  fit_score?: number;
  status?: string;
  notes?: string;
  created_at?: string;
}

export interface Contact {
  id: number;
  name: string;
  company?: string;
  company_id?: number;
  title?: string;
  relationship?: string;
  email?: string;
  phone?: string;
  linkedin_url?: string;
  relationship_strength?: string;
  last_contact?: string;
  notes?: string;
}

export interface Interview {
  id: number;
  application_id?: number;
  date?: string;
  type?: string;
  interviewers?: string[];
  outcome?: string;
  feedback?: string;
  thank_you_sent?: boolean;
  notes?: string;
  company_name?: string;
  role?: string;
}

export interface CareerHistory {
  id: number;
  employer: string;
  title: string;
  start_date?: string;
  end_date?: string;
  location?: string;
  industry?: string;
  team_size?: number;
  is_current?: boolean;
}

export interface Bullet {
  id: number;
  career_history_id: number;
  text: string;
  type: string;
  tags?: string[];
  display_order: number;
  ai_analysis?: {
    strength: 'strong' | 'moderate' | 'weak';
    star_check?: Record<string, boolean>;
    feedback?: string;
    suggested_skills?: string[];
    content_hash_at_analysis?: string;
  };
  ai_analyzed_at?: string;
  content_hash?: string;
  is_default?: boolean;
  updated_at?: string;
  created_at?: string;
  role_suitability?: string[];
  employer?: string;
}

export interface CareerHistoryJob {
  id: number;
  employer: string;
  title: string;
  location?: string;
  start_date?: string;
  end_date?: string;
  start_date_raw?: string;
  end_date_raw?: string;
  start_date_iso?: string;
  end_date_iso?: string;
  metadata?: Record<string, string>;
}

export interface Recipe {
  id: number;
  name: string;
  description?: string;
  headline?: string;
  template_id: number;
  is_active?: boolean;
  created_at?: string;
}

export interface GapAnalysis {
  id: number;
  application_id?: number;
  saved_job_id?: number;
  overall_score?: number;
  recommendation?: string;
  strong_matches?: unknown;
  partial_matches?: unknown;
  gaps?: unknown;
  created_at?: string;
}

export interface Company {
  id: number;
  name: string;
  sector?: string;
  hq_location?: string;
  size?: string;
  fit_score?: number;
  priority?: string;
  target_role?: string;
  notes?: string;
}

export interface ActivityItem {
  id: number;
  action: string;
  entity_type?: string;
  entity_id?: number;
  details?: Record<string, unknown>;
  created_at?: string;
}

// API functions
export const applications = {
  list: (params = '') => api.get<Application[]>(`/applications${params}`),
  get: (id: number) => api.get<Application>(`/applications/${id}`),
  create: (data: Partial<Application>) => api.post<Application>('/applications', data),
  update: (id: number, data: Partial<Application>) => api.patch<Application>(`/applications/${id}`, data),
};

export const savedJobs = {
  list: (params = '') => api.get<SavedJob[]>(`/saved-jobs${params}`),
  get: (id: number) => api.get<SavedJob>(`/saved-jobs/${id}`),
  create: (data: Partial<SavedJob>) => api.post<SavedJob>('/saved-jobs', data),
  update: (id: number, data: Partial<SavedJob>) => api.patch<SavedJob>(`/saved-jobs/${id}`, data),
  del: (id: number) => api.del(`/saved-jobs/${id}`),
  apply: (id: number) => api.post<Application>(`/saved-jobs/${id}/apply`, {}),
};

export const contacts = {
  list: (params = '') => api.get<Contact[]>(`/contacts${params}`),
  create: (data: Partial<Contact>) => api.post<Contact>('/contacts', data),
  update: (id: number, data: Partial<Contact>) => api.patch<Contact>(`/contacts/${id}`, data),
  del: (id: number) => api.del(`/contacts/${id}`),
};

export const interviews = {
  list: (params = '') => api.get<Interview[]>(`/interviews${params}`),
  create: (data: Partial<Interview>) => api.post<Interview>('/interviews', data),
  update: (id: number, data: Partial<Interview>) => api.patch<Interview>(`/interviews/${id}`, data),
};

export const companies = {
  list: (params = '') => api.get<Company[]>(`/companies${params}`),
  get: (id: number) => api.get<Company>(`/companies/${id}`),
};

export const recipes = {
  list: () => api.get<Recipe[]>('/resume/recipes'),
  get: (id: number) => api.get<Recipe>(`/resume/recipes/${id}`),
};

export const bullets = {
  list: (params = '') => api.get<Bullet[]>(`/bullets${params}`),
};

export const activity = {
  list: (params = '') => api.get<ActivityItem[]>(`/activity${params}`),
};

// --- AI Generate Slot ---

export interface GenerateSlotSuggestion {
  text: string;
  confidence: number;
  source: string;
  bullet_id?: number;
}

export interface GenerateSlotResult {
  suggestions: GenerateSlotSuggestion[];
  analysis_mode: string;
}

export interface GenerateSlotContext {
  job_id?: number;
  existing_bullets?: string[];
  target_role?: string;
  instructions?: string;
}

export function recipeGenerateSlot(
  recipeId: number,
  slotType: string,
  context: GenerateSlotContext,
): Promise<GenerateSlotResult> {
  return api.post<GenerateSlotResult>(
    `/resume/recipes/${recipeId}/ai-generate-slot`,
    { slot_type: slotType, context },
  );
}

export const analytics = {
  funnel: () => api.get<Record<string, unknown>[]>('/analytics/funnel'),
};

export const gapAnalyses = {
  list: (params = '') => api.get<GapAnalysis[]>(`/gap-analyses${params}`),
  get: (id: number) => api.get<GapAnalysis>(`/gap-analyses/${id}`),
};

// --- ATS Score for Recipes ---

export interface AtsScoreResult {
  ats_score: number;
  keyword_matches: Record<string, boolean>;
  match_percentage: number;
  keywords_found: number;
  keywords_checked: number;
  formatting_flags: string[];
  suggestions?: string[];
  missing_keywords?: string[];
  analysis_mode: string;
}

export async function recipeAtsScore(
  recipeId: number,
  jdText?: string,
  applicationId?: number
): Promise<AtsScoreResult> {
  return api.post<AtsScoreResult>(`/resume/recipes/${recipeId}/ats-score`, {
    jd_text: jdText,
    application_id: applicationId,
  });
}

// --- AI Review for Recipes ---

export interface AiReviewFeedbackItem {
  section: string;
  issue: string;
  severity: 'high' | 'medium' | 'low';
}

export interface AiReviewTargetRole {
  role: string;
  score: number;
  gaps: string[];
  suggestions: string[];
}

export interface AiReviewResult {
  generic: {
    score: number;
    feedback: AiReviewFeedbackItem[];
    strengths: string[];
  };
  target_roles: AiReviewTargetRole[];
  analysis_mode: 'ai' | 'rule_based';
}

export async function recipeAiReview(recipeId: number): Promise<AiReviewResult> {
  return api.post<AiReviewResult>(`/resume/recipes/${recipeId}/ai-review`, {});
}

export const staleApps = {
  list: (days = 14) => api.get<Application[]>(`/applications/stale?days=${days}`),
};

export const freshJobs = {
  list: (params = '') => api.get<any[]>(`/fresh-jobs${params}`),
  triage: (id: number, action: string) => api.post<any>(`/fresh-jobs/${id}/triage`, { action }),
  batchTriage: (ids: number[], action: string) => api.post<any>('/fresh-jobs/batch-triage', { job_ids: ids, action }),
};

export const notifications = {
  list: (params = '') => api.get<any[]>(`/notifications${params}`),
  markRead: (id: number) => api.patch<any>(`/notifications/${id}/read`, {}),
  dismiss: (id: number) => api.del(`/notifications/${id}`),
  markAllRead: () => api.patch<any>('/notifications/read-all', {}),
};

export const mockInterviews = {
  list: (params = '') => api.get<any[]>(`/mock-interviews${params}`),
  get: (id: number) => api.get<any>(`/mock-interviews/${id}`),
  create: (data: any) => api.post<any>('/mock-interviews', data),
  answer: (id: number, questionId: number, answer: string) =>
    api.patch<any>(`/mock-interviews/${id}/answer`, { question_id: questionId, user_answer: answer }),
  evaluate: (id: number) => api.patch<any>(`/mock-interviews/${id}/evaluate`, {}),
};

export interface OutreachMessage {
  id: number;
  contact_id?: number;
  contact_name?: string;
  application_id?: number;
  channel: string;
  direction: string;
  subject?: string;
  body?: string;
  sent_at?: string;
  response_received?: boolean;
  notes?: string;
  created_at?: string;
}

export interface ConversationData {
  messages: OutreachMessage[];
  touchpoints: Array<{ id: number; type: string; channel?: string; direction?: string; notes?: string; logged_at?: string }>;
}

export interface SendMessagePayload {
  contact_id: number;
  channel: 'gmail' | 'linkedin';
  action?: 'send' | 'draft';
  subject?: string;
  body: string;
  application_id?: number;
}

export const crm = {
  relationships: (params = '') => api.get<any>(`/crm/relationships${params}`),
  health: (params = '') => api.get<any>(`/crm/health${params}`),
  tasks: (params = '') => api.get<any[]>(`/crm/networking-tasks${params}`),
  logTouchpoint: (data: any) => api.post<any>('/crm/touchpoints', data),
  sendMessage: (data: SendMessagePayload) => api.post<{ result: any; outreach: OutreachMessage }>('/crm/send-message', data),
  updateDraft: (id: number, data: { subject?: string; body: string; action?: 'update' | 'send' }) =>
    api.put<{ result: any; outreach: OutreachMessage }>(`/crm/drafts/${id}`, data),
  deleteDraft: (id: number) => api.del<{ deleted: number }>(`/crm/drafts/${id}`),
  wordsmith: (body: string, contactId?: number, channel = 'linkedin') =>
    api.post<{ body: string; mode: string }>('/crm/wordsmith', { body, contact_id: contactId, channel }),
  generateOutreach: (data: {
    contact_id: number; type?: string; use_ai?: boolean; channel?: string;
    prompt?: string; existing_subject?: string; existing_body?: string;
  }) => api.post<{ outreach: { subject: string; body: string; channel: string; mode: string } }>('/crm/generate-outreach', data),
  conversations: (contactId: number, params = '') =>
    api.get<ConversationData>(`/crm/conversations/${contactId}${params}`),
};

export const marketIntel = {
  list: (params = '') => api.get<any[]>(`/market-intelligence${params}`),
  summary: () => api.get<any>('/market-intelligence/summary'),
};

// --- Emails ---

export interface Email {
  id: number;
  gmail_id?: string;
  thread_id?: string;
  from_name?: string;
  from_address?: string;
  to_address?: string;
  subject?: string;
  snippet?: string;
  date?: string;
  labels?: string[];
  category?: string;
  application_id?: number | null;
  created_at?: string;
}

export interface EmailIntelStatus {
  total_emails: number;
  scanned: number;
  unlinked_categorized: number;
  breakdown: Record<string, number>;
}

export const emails = {
  list: (params = '') => api.get<Email[]>(`/emails${params}`),
  intelligenceStatus: () => api.get<EmailIntelStatus>('/email-intelligence/status'),
};
