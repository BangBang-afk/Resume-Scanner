"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listJobs, type JobSummary } from "@/lib/api";

export default function RolesPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => {
    listJobs()
      .then((d) => {
        setJobs(d.jobs || []);
        setErr("");
      })
      .catch(() => setErr("Could not reach the backend. Check it is running, then retry."));
  }, []);
  return (
    <div>
      <h1 className="font-display text-4xl">Roles</h1>
      {err && (
        <div className="vetted-panel mt-2 p-3 text-xs text-red-600" role="alert">
          {err} {" "}
          <button className="underline" onClick={() => location.reload()}>
            Retry
          </button>
        </div>
      )}
      <div className="mt-4">
        {jobs.map((j) => (
          <Link key={j.id} href={"/jobs/" + j.id} className="vetted-card mb-2 flex gap-4 p-3 text-xs">
            <span className="flex-1 font-semibold">{j.title}</span>
            <span style={{ color: "var(--muted)" }}>{j.resumes} resumes</span>
          </Link>
        ))}
        {jobs.length === 0 && !err && <p className="text-xs" style={{ color: "var(--muted)" }}>No roles yet — run a scan.</p>}
      </div>
    </div>
  );
}
