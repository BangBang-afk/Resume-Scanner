"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { deleteJob, getJob, listJobs, updateJob, type JobSummary } from "@/lib/api";

export default function RolesPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [required, setRequired] = useState("");
  const [preferred, setPreferred] = useState("");
  const [years, setYears] = useState(2);
  const [note, setNote] = useState("");
  const [confirmDel, setConfirmDel] = useState<string | null>(null);

  async function reload() {
    try {
      const d = await listJobs();
      setJobs(d.jobs || []);
      setErr("");
    } catch {
      setErr("Could not reach the backend. Check it is running, then retry.");
    }
  }

  useEffect(() => {
    void Promise.resolve().then(() => reload());
  }, []);

  async function startEdit(id: string) {
    try {
      const j = await getJob(id);
      setEditing(id);
      setTitle(j.title);
      setRequired((j.required || []).join(", "));
      setPreferred((j.preferred || []).join(", "));
      setYears(j.min_years);
      setNote("");
    } catch {
      setErr("Could not load role details.");
    }
  }

  async function saveEdit(id: string) {
    try {
      const r = await updateJob(id, {
        title: title.trim(),
        required: required.split(",").map((s) => s.trim()).filter(Boolean),
        preferred: preferred.split(",").map((s) => s.trim()).filter(Boolean),
        min_years: years,
      });
      setEditing(null);
      setNote(`Saved — ${r.rescored} resume${r.rescored === 1 ? "" : "s"} re-scored under new details.`);
      reload();
    } catch {
      setErr("Save failed — backend unreachable.");
    }
  }

  async function remove(id: string) {
    try {
      await deleteJob(id);
      setConfirmDel(null);
      reload();
    } catch {
      setErr("Delete failed — backend unreachable.");
    }
  }

  return (
    <div>
      <div className="flex items-end justify-between">
        <h1 className="font-display text-4xl">Roles</h1>
        <Link href="/" className="vetted-btn-dark text-xs">
          + New role
        </Link>
      </div>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
        A role is a job + its required and preferred skills. Resumes scanned under one role stay in that role.
        Editing details re-scores its resumes. Deleting a role removes its resumes too.
      </p>
      {err && (
        <div className="vetted-panel mt-2 p-3 text-xs text-red-600" role="alert">
          {err}{" "}
          <button className="underline" onClick={() => location.reload()}>
            Retry
          </button>
        </div>
      )}
      {note && <p className="mt-2 text-xs text-green-700">{note}</p>}
      <div className="mt-4">
        {jobs.map((j) => (
          <div key={j.id} className="vetted-card mb-2 p-3 text-xs">
            {editing === j.id ? (
              <div className="space-y-2">
                <input value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Role title" className="vetted-input" />
                <input value={required} onChange={(e) => setRequired(e.target.value)} aria-label="Required skills, comma separated" className="vetted-input" />
                <input value={preferred} onChange={(e) => setPreferred(e.target.value)} aria-label="Preferred skills, comma separated" className="vetted-input" />
                <label className="flex items-center gap-2">
                  Min years:
                  <input type="number" min={0} max={50} value={years} onChange={(e) => setYears(Number(e.target.value))} className="vetted-input w-20" />
                </label>
                <div className="flex gap-2">
                  <button onClick={() => saveEdit(j.id)} className="vetted-btn-dark">
                    Save + re-score
                  </button>
                  <button onClick={() => setEditing(null)} className="vetted-btn-ghost">
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-4">
                <Link href={"/jobs/" + j.id} className="flex-1 font-semibold">
                  {j.title}
                </Link>
                <span style={{ color: "var(--muted)" }}>{j.resumes} resumes</span>
                <button onClick={() => startEdit(j.id)} className="vetted-btn-ghost">
                  Edit
                </button>
                {confirmDel === j.id ? (
                  <span className="flex gap-1">
                    <button onClick={() => remove(j.id)} className="rounded bg-red-700 px-2 py-1 text-white">
                      Confirm delete
                    </button>
                    <button onClick={() => setConfirmDel(null)} className="vetted-btn-ghost">
                      Keep
                    </button>
                  </span>
                ) : (
                  <button onClick={() => setConfirmDel(j.id)} className="vetted-btn-ghost">
                    Delete
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
        {jobs.length === 0 && !err && <p className="text-xs" style={{ color: "var(--muted)" }}>No roles yet — run a scan.</p>}
      </div>
    </div>
  );
}
