export interface HealthStatus {
  connected: boolean;
  status: string;
  db: string;
  timestamp: number;
}

export interface PipelineSummary {
  saved: number;
  applied: number;
  interviewing: number;
  offered: number;
  total: number;
}

export interface BackendConfig {
  apiUrl: string;
  healthCheckInterval: number;
  badgeUpdateInterval: number;
}

export interface SavedJob {
  id: number;
  url: string;
  title: string;
  company: string;
  location?: string;
  salary_range?: string;
  source: string;
  jd_text?: string;
  fit_score?: number;
  status: string;
  created_at: string;
}

export interface PageContext {
  url: string;
  type: "job_listing" | "ats_form" | "company_page" | "unknown";
  board?: string;
  data?: Record<string, string>;
}

export interface GapAnalysisResult {
  fit_score: number;
  strong_matches: string[];
  partial_matches: string[];
  gaps: string[];
  recommendations: string[];
  jd_keywords: string[];
  analysis_mode: "ai" | "rule_based";
  cached_at?: number;
  job_url: string;
}

export interface JobExtraction {
  title: string;
  company: string;
  location: string | null;
  salary: string | null;
  description: string;
  url: string;
  source: string;
}
