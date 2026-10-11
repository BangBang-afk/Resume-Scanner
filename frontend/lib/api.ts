const DEFAULT_API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function base(): string {
  if (typeof localStorage !== "undefined") {
    const override = localStorage.getItem("vetted-api");
    if (override) return override;
  }
  return DEFAULT_API;
}

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const apiUrl = () => base();

// --- Session token -----------------------------------------------------------
const TOKEN_KEY = "vetted-token";
const EMAIL_KEY = "vetted-email";

export function getToken(): string | null {
  if (typeof localStorage === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getEmail(): string | null {
  if (typeof localStorage === "undefined") return null;
  return localStorage.getItem(EMAIL_KEY);
}

export function setSession(token: string, email: string) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(EMAIL_KEY, email);
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EMAIL_KEY);
}

export function isLoggedIn(): boolean {
  return getToken() !== null;
}

export interface JobSummary {
  id: string;
  title: string;
  required: string[];
  preferred: string[];
  resumes: number;
  created_at: string;
}

export interface RankRow {
  candidate_id: string;
  filename: string;
  total: number;
  band: string;
  flags: string[];
  system_decision: string;
  final_decision: string;
  overridden: boolean;
  close_call?: boolean;
  rank?: number;
}

export interface ScoreFactor {
  value: number | null;
  weight: number;
}

export interface CandidateDetail {
  id: string;
  filename: string;
  status: string;
  profile: Record<string, unknown>;
  score: {
    total: number;
    band: string;
    decision: string;
    factors: Record<string, ScoreFactor>;
    matched_skills: string[];
    related_skills: string[];
    missing_skills: string[];
    relevant_years?: number;
  };
  evidence: { quote: string; skill: string }[];
  explanation: {
    summary: string;
    strengths: { point: string; quote?: string | null }[];
    concerns: { point: string; quote?: string | null }[];
  } | null;
  system_decision?: string;
  final_decision?: string;
  overridden: boolean;
  masked_text: string;
}

async function parse<T>(res: Response): Promise<T> {
  if (res.status === 401 && typeof window !== "undefined") {
    clearSession();
    // Full navigation (not router.push) intentionally: resets all cached page
    // state so no stale signed-out view keeps polling the API.
    window.location.assign("/login");
    throw new Error("Signed out");
  }
  if (!res.ok) throw new Error("API " + res.status);
  return res.json() as Promise<T>;
}

function headers(extra?: Record<string, string>): Record<string, string> {
  const h = { ...extra };
  const token = getToken();
  if (token) h["Authorization"] = "Bearer " + token;
  return h;
}

/**
 * Single request layer. If a saved Settings override points at a dead host
 * (old tunnel URL, stopped server), retry once against the built-in default
 * instead of leaving the UI bricked. HTTP errors pass through untouched —
 * only network-level failures trigger the fallback.
 */
async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const primary = base();
  const attempt = async (root: string): Promise<Response> =>
    fetch(root + path, {
      ...init,
      headers: headers((init?.headers as Record<string, string>) || undefined),
    });
  try {
    return await parse<T>(await attempt(primary));
  } catch (e) {
    if (e instanceof TypeError && primary !== DEFAULT_API) {
      return parse<T>(await attempt(DEFAULT_API));
    }
    throw e;
  }
}

export interface JobDetail extends JobSummary {
  jd_text: string;
  min_years: number;
  weights: Record<string, number>;
}

export async function createJob(payload: {
  title: string;
  jd_text: string;
  required?: string[];
  preferred?: string[];
  min_years?: number;
}): Promise<JobDetail> {
  return req<JobDetail>("/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listJobs(): Promise<{ jobs: JobSummary[] }> {
  return req<{ jobs: JobSummary[] }>("/jobs", { cache: "no-store" });
}

export async function getJob(jobId: string): Promise<JobDetail> {
  return req<JobDetail>(`/jobs/${jobId}`, { cache: "no-store" });
}

export async function updateJob(jobId: string, payload: {
  title?: string;
  required?: string[];
  preferred?: string[];
  min_years?: number;
}): Promise<{ ok: boolean; rescored: number }> {
  return req<{ ok: boolean; rescored: number }>(`/jobs/${jobId}/skills`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteJob(jobId: string): Promise<{ ok: boolean; deleted_candidates: number }> {
  return req<{ ok: boolean; deleted_candidates: number }>(`/jobs/${jobId}`, { method: "DELETE" });
}

export async function getRanking(jobId: string): Promise<{ ranking: RankRow[]; pending: { id: string; status: string }[] }> {
  return req<{ ranking: RankRow[]; pending: { id: string; status: string }[] }>(`/jobs/${jobId}/ranking`, { cache: "no-store" });
}

export async function getDuplicates(jobId: string): Promise<{ pairs: { a: string; b: string; kind: string; score: number }[] }> {
  return req<{ pairs: { a: string; b: string; kind: string; score: number }[] }>(`/jobs/${jobId}/duplicates`, { cache: "no-store" });
}

export async function uploadResumes(jobId: string, files: FileList | File[]): Promise<{ candidate_ids: string[] }> {
  const fd = new FormData();
  Array.from(files).forEach((f) => fd.append("files", f));
  return req<{ candidate_ids: string[] }>(`/jobs/${jobId}/resumes`, { method: "POST", body: fd });
}

export async function getCandidate(cid: string): Promise<CandidateDetail> {
  return req<CandidateDetail>(`/candidates/${cid}`, { cache: "no-store" });
}

export async function getInterview(cid: string): Promise<{ questions: string[] }> {
  return req<{ questions: string[] }>(`/candidates/${cid}/interview-questions`, { cache: "no-store" });
}

export async function overrideCandidate(cid: string, new_decision: string, reason: string): Promise<{ ok: boolean }> {
  return req<{ ok: boolean }>(`/candidates/${cid}/override`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_decision, reason }),
  });
}

/** Authenticated CSV download: plain <a href> cannot attach the Bearer token. */
export async function exportCsv(jobId: string, filename: string): Promise<void> {
  const res = await fetch(apiUrl() + "/jobs/" + jobId + "/export.csv", { cache: "no-store", headers: headers() });
  if (!res.ok) throw new Error("Download failed (" + res.status + ")");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function login(email: string, password: string): Promise<{ id: string; email: string; token: string }> {
  return req<{ id: string; email: string; token: string }>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function register(email: string, password: string): Promise<{ id: string; email: string; token: string }> {
  return req<{ id: string; email: string; token: string }>("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function deleteCandidate(cid: string): Promise<{ ok: boolean }> {
  return req<{ ok: boolean }>(`/candidates/${cid}`, { method: "DELETE" });
}

export function exportCsvUrl(jobId: string) {
  return apiUrl() + "/jobs/" + jobId + "/export.csv";
}
