"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getRanking, listJobs, type JobSummary, type RankRow } from "@/lib/api";
import { prettyName } from "@/lib/format";

interface ListedRow extends RankRow {
  job: string;
  jobId: string;
}

export default function CandidatesPage() {
  const [rows, setRows] = useState<ListedRow[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => {
    listJobs()
      .then(async (d) => {
        const list: JobSummary[] = d.jobs || [];
        const settled = await Promise.all(list.map((j) => getRanking(j.id).catch(() => null)));
        const all: ListedRow[] = [];
        settled.forEach((r, i) => {
          (r?.ranking || []).forEach((c) => all.push({ ...c, job: list[i].title, jobId: list[i].id }));
        });
        all.sort((a, b) => b.total - a.total);
        setRows(all);
        setErr("");
      })
      .catch(() => setErr("Could not reach the backend. Check it is running, then retry."));
  }, []);
  return (
    <div>
      <h1 className="font-display text-4xl">Candidates</h1>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{rows.length} across all roles</p>
      {err && (
        <div className="vetted-panel mt-2 p-3 text-xs text-red-600" role="alert">
          {err} {" "}
          <button className="underline" onClick={() => location.reload()}>
            Retry
          </button>
        </div>
      )}
      <div className="mt-4">
        {rows.map((r) => (
          <Link key={r.candidate_id} href={"/jobs/" + r.jobId} className="vetted-card mb-1 flex gap-3 p-2 text-xs">
            <span className="font-display font-bold">{r.total}</span>
            <span className="flex-1">{prettyName(r.filename)}</span>
            <span style={{ color: "var(--muted)" }}>{r.job}</span>
            <b>{r.final_decision}</b>
          </Link>
        ))}
      </div>
    </div>
  );
}
