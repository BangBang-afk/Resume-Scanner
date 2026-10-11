"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createJob, getRanking, listJobs, uploadResumes, type JobSummary } from "@/lib/api";

export default function ScanPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [top, setTop] = useState<Record<string, number>>({});
  const [title, setTitle] = useState("Python Backend Developer");
  const [jd, setJd] = useState(
    "Python backend developer. Required: Python, FastAPI, PostgreSQL. Preferred: Docker, AWS. 3 years experience building APIs."
  );
  const [required, setRequired] = useState("Python, FastAPI, PostgreSQL");
  const [preferred, setPreferred] = useState("Docker, AWS");
  const [years, setYears] = useState(3);
  const [blind, setBlind] = useState(() =>
    typeof localStorage === "undefined" ? true : localStorage.getItem("vetted-blind") !== "0"
  );
  const [files, setFiles] = useState<FileList | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    listJobs()
      .then(async (d) => {
        const list = d.jobs || [];
        setJobs(list);
        const settled = await Promise.all(
          list.map((j) => getRanking(j.id).catch(() => null))
        );
        const t: Record<string, number> = {};
        settled.forEach((r, i) => {
          if (r?.ranking?.[0]) t[list[i].id] = r.ranking[0].total;
        });
        setTop(t);
      })
      .catch(() => setErr("Backend unreachable on :8000."));
  }, []);

  async function runScan() {
    if (!files || files.length === 0) {
      setErr("Drop resumes first.");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const job = await createJob({
        title,
        jd_text: jd,
        required: required.split(",").map((s) => s.trim()).filter(Boolean),
        preferred: preferred.split(",").map((s) => s.trim()).filter(Boolean),
        min_years: years,
      });
      await uploadResumes(job.id, files);
      router.push("/jobs/" + job.id + (blind ? "?blind=1" : ""));
    } catch {
      setErr("Backend unreachable on :8000.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <p className="text-[10px] tracking-widest" style={{ color: "var(--muted)" }}>
        NEW SCAN
      </p>
      <div className="mt-2 grid grid-cols-3 gap-6">
        <div className="col-span-2">
          <h1 className="font-display text-4xl leading-tight">
            Read every resume as if it were the only one.
          </h1>
          <p className="mt-2 max-w-md text-xs" style={{ color: "var(--muted)" }}>
            Vetted scores each resume against the evidence a role actually needs, and shows you
            the exact lines behind every number.
          </p>
          <div
            className="vetted-panel mt-6 flex flex-col items-center justify-center gap-2 border-dashed p-10 text-center"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              setFiles(e.dataTransfer.files);
            }}
            aria-label="Resume upload: drag and drop files here, or use the Select files button"
          >
            <p className="font-medium">Drop resumes here</p>
            <p className="text-[10px]" style={{ color: "var(--muted)" }}>
              PDF, DOCX or TXT · up to 200 files per batch
            </p>
            <div className="flex gap-2">
              <label className="vetted-btn-dark cursor-pointer text-xs">
                Select files
                <input
                  type="file"
                  multiple
                  accept=".pdf,.docx,.txt"
                  className="hidden"
                  onChange={(e) => setFiles(e.target.files)}
                />
              </label>
            </div>
            {files && files.length > 0 && <p className="text-xs">{files.length} files ready</p>}
          </div>
          <h2 className="mt-8 text-sm font-bold">Recent scans</h2>
          <div className="mt-2">
            {jobs.map((j) => (
              <Link
                key={j.id}
                href={"/jobs/" + j.id}
                className="vetted-card mb-2 flex items-center gap-4 p-3 text-xs"
              >
                <span className="flex-1 font-semibold">{j.title}</span>
                <span style={{ color: "var(--muted)" }}>{j.resumes} resumes</span>
                <span className="font-bold">{top[j.id] ?? "—"}</span>
              </Link>
            ))}
            {jobs.length === 0 && (
              <p className="text-xs" style={{ color: "var(--muted)" }}>
                No scans yet.
              </p>
            )}
          </div>
        </div>
        <div className="vetted-panel h-fit p-4">
          <p className="text-[10px] tracking-widest" style={{ color: "var(--muted)" }}>
            SCAN AGAINST
          </p>
          <input value={title} onChange={(e) => setTitle(e.target.value)} className="vetted-input mt-2 text-xs" />
          <textarea value={jd} onChange={(e) => setJd(e.target.value)} rows={4} className="vetted-input mt-2 text-xs" />
          <div className="mt-2 grid grid-cols-2 gap-2">
            <input value={required} onChange={(e) => setRequired(e.target.value)} className="vetted-input text-xs" title="Required" />
            <input value={preferred} onChange={(e) => setPreferred(e.target.value)} className="vetted-input text-xs" title="Preferred" />
          </div>
          <label className="mt-2 block text-xs">Min years: {years}</label>
          <input
            type="range"
            min={0}
            max={10}
            value={years}
            onChange={(e) => setYears(Number(e.target.value))}
            className="w-full"
            aria-label="Minimum years of experience (0–10)"
          />
          <p className="mt-3 text-[10px] tracking-widest" style={{ color: "var(--muted)" }}>
            WEIGHTED CRITERIA
          </p>
          {[["Must-have skills", 40], ["Preferred skills", 20], ["Experience", 20], ["Projects", 10], ["Education", 10]].map(([k, v]) => (
            <div key={k as string} className="mt-2 text-xs">
              <div className="flex justify-between">
                <span>{k}</span>
                <span>{v}%</span>
              </div>
              <div className="vetted-bar">
                <div style={{ width: v + "%" }} />
              </div>
            </div>
          ))}
          <label className="mt-3 flex items-center justify-between text-xs">
            Blind mode
            <input type="checkbox" checked={blind} onChange={(e) => setBlind(e.target.checked)} />
          </label>
          <button onClick={runScan} disabled={busy} className="vetted-btn-dark mt-3 w-full text-sm disabled:opacity-50">
            {busy ? "Scanning…" : "Run scan →"}
          </button>
          {err && (
            <p className="mt-2 text-xs text-red-600" role="alert">
              {err}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
