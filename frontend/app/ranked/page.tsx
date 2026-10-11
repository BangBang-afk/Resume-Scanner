"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { listJobs, type JobSummary } from "@/lib/api";

export default function RankedIndex() {
  const router = useRouter();
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    listJobs()
      .then((d) => {
        const list = d.jobs || [];
        setJobs(list);
        if (list.length > 0) router.push("/jobs/" + list[0].id);
      })
      .catch(() => setErr("Backend unreachable on :8000."));
  }, [router]);

  return (
    <div>
      <p className="text-[10px] tracking-widest" style={{ color: "var(--muted)" }}>
        RANKED CANDIDATES
      </p>
      <h1 className="font-display text-4xl">Ranked candidates</h1>
      {err && <p className="mt-2 text-xs text-red-600">{err}</p>}
      <div className="mt-4">
        {jobs.map((j) => (
          <Link key={j.id} href={"/jobs/" + j.id} className="vetted-card mb-2 flex gap-4 p-3 text-xs">
            <span className="flex-1 font-semibold">{j.title}</span>
            <span style={{ color: "var(--muted)" }}>{j.resumes} resumes →</span>
          </Link>
        ))}
        {jobs.length === 0 && !err && (
          <p className="text-xs" style={{ color: "var(--muted)" }}>
            No scans yet — run one first.
          </p>
        )}
      </div>
    </div>
  );
}
