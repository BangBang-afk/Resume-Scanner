function base(): string {
  if (typeof localStorage !== "undefined") {
    const override = localStorage.getItem("vetted-api");
    if (override) return override;
  }
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
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

async function json<T>(res: Response): Promise<T> {
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
  const res = await fetch(apiUrl() + "/jobs", {
    method: "POST",
    headers: headers({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  return json<JobDetail>(res);
}

export async function listJobs(): Promise<{ jobs: JobSummary[] }> {
  const res = await fetch(apiUrl() + "/jobs", { cache: "no-store", headers: headers() });
  return json<{ jobs: JobSummary[] }>(res);
}

export async function getJob(jobId: string): Promise<JobDetail> {
  const res = await fetch(apiUrl() + "/jobs/" + jobId, { cache: "no-store", headers: headers() });
  return json<JobDetail>(res);
}

export async function getRanking(jobId: string): Promise<{ ranking: RankRow[]; pending: { id: string; status: string }[] }> {
  const res = await fetch(apiUrl() + "/jobs/" + jobId + "/ranking", { cache: "no-store", headers: headers() });
  return json<{ ranking: RankRow[]; pending: { id: string; status: string }[] }>(res);
}

export async function getDuplicates(jobId: string): Promise<{ pairs: { a: string; b: string; kind: string; score: number }[] }> {
  const res = await fetch(apiUrl() + "/jobs/" + jobId + "/duplicates", { cache: "no-store", headers: headers() });
  return json<{ pairs: { a: string; b: string; kind: string; score: number }[] }>(res);
}

export async function uploadResumes(jobId: string, files: FileList | File[]): Promise<{ candidate_ids: string[] }> {
  const fd = new FormData();
  Array.from(files).forEach((f) => fd.append("files", f));
  const res = await fetch(apiUrl() + "/jobs/" + jobId + "/resumes", { method: "POST", body: fd, headers: headers() });
  return json<{ candidate_ids: string[] }>(res);
}

export async function getCandidate(cid: string): Promise<CandidateDetail> {
  const res = await fetch(apiUrl() + "/candidates/" + cid, { cache: "no-store", headers: headers() });
  return json<CandidateDetail>(res);
}

export async function getInterview(cid: string): Promise<{ questions: string[] }> {
  const res = await fetch(apiUrl() + "/candidates/" + cid + "/interview-questions", { cache: "no-store", headers: headers() });
  return json<{ questions: string[] }>(res);
}

export async function overrideCandidate(cid: string, new_decision: string, reason: string): Promise<{ ok: boolean }> {
  const res = await fetch(apiUrl() + "/candidates/" + cid + "/override", {
    method: "POST",
    headers: headers({ "Content-Type": "application/json" }),
    body: JSON.stringify({ new_decision, reason }),
  });
  return json<{ ok: boolean }>(res);
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
  const res = await fetch(apiUrl() + "/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return json<{ id: string; email: string; token: string }>(res);
}

export async function register(email: string, password: string): Promise<{ id: string; email: string; token: string }> {
  const res = await fetch(apiUrl() + "/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return json<{ id: string; email: string; token: string }>(res);
}

export async function deleteCandidate(cid: string): Promise<{ ok: boolean }> {
  const res = await fetch(apiUrl() + "/candidates/" + cid, { method: "DELETE", headers: headers() });
  return json<{ ok: boolean }>(res);
}
