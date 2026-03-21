import { DEFAULT_CONFIG } from "@shared/config";
import type { SavedJob, JobExtraction, GapAnalysisResult } from "@shared/types";

let baseUrl = DEFAULT_CONFIG.apiUrl;

export function setBaseUrl(url: string) {
  baseUrl = url;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function checkHealth(): Promise<{ connected: boolean; status: string; db: string }> {
  try {
    const data = await apiGet<{ status: string; db: string }>("/api/health");
    return { connected: true, ...data };
  } catch {
    return { connected: false, status: "unreachable", db: "unknown" };
  }
}

export async function getPipelineSummary() {
  try {
    const data = await apiGet<Record<string, unknown>>("/api/analytics/summary");
    return data;
  } catch {
    return null;
  }
}

// --- Saved Jobs ---

export async function saveJob(job: JobExtraction): Promise<SavedJob> {
  return apiPost('/api/saved-jobs', {
    url: job.url,
    title: job.title,
    company: job.company,
    location: job.location,
    salary_range: job.salary,
    jd_text: job.description,
    source: job.source,
    status: 'saved',
  });
}

export async function checkJobUrl(url: string): Promise<{ exists: boolean; saved_job?: SavedJob }> {
  try {
    const jobs = await apiGet<SavedJob[]>(`/api/saved-jobs?url=${encodeURIComponent(url)}`);
    if (jobs && jobs.length > 0) {
      return { exists: true, saved_job: jobs[0] };
    }
    return { exists: false };
  } catch {
    return { exists: false };
  }
}

export async function getSavedJobs(): Promise<SavedJob[]> {
  try {
    return await apiGet<SavedJob[]>('/api/saved-jobs');
  } catch {
    return [];
  }
}

// --- Gap Analysis ---

export async function runGapAnalysis(jdText: string): Promise<GapAnalysisResult> {
  const response = await apiPost<Record<string, unknown>>('/api/gap-analysis', { jd_text: jdText });
  // Normalize the backend response to our GapAnalysisResult shape
  return {
    fit_score: (response.fit_score ?? response.coverage_pct ?? 0) as number,
    strong_matches: (response.strong_matches ?? []) as string[],
    partial_matches: (response.partial_matches ?? []) as string[],
    gaps: (response.gaps ?? []) as string[],
    recommendations: (response.recommendations ?? []) as string[],
    jd_keywords: (response.jd_keywords ?? []) as string[],
    analysis_mode: (response.analysis_mode ?? "rule_based") as "ai" | "rule_based",
    job_url: '',
  };
}

export async function persistGapAnalysis(savedJobId: number, result: GapAnalysisResult): Promise<void> {
  await apiPost('/api/gap-analyses', {
    saved_job_id: savedJobId,
    strong_matches: result.strong_matches,
    partial_matches: result.partial_matches,
    gaps: result.gaps,
    overall_score: result.fit_score,
    recommendation: result.recommendations.join('; '),
    notes: `Analysis mode: ${result.analysis_mode}`,
  });
}
