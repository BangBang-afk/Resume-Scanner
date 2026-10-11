"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  exportCsv,
  getCandidate,
  getDuplicates,
  getInterview,
  getJob,
  getRanking,
  overrideCandidate,
  type CandidateDetail,
  type JobDetail,
  type RankRow,
} from "@/lib/api";
import { bandByScore, prettyFactor, prettyFlag, prettyName, prettySkill } from "@/lib/format";

function rowBg(r: RankRow): [string, string] {
  const band = bandByScore(r.total);
  if (band === "green") return ["var(--green)", "var(--green-ink)"];
  if (band === "yellow") return ["var(--yellow)", "var(--yellow-ink)"];
  return ["var(--red)", "var(--red-ink)"];
}

function pollMs(): number {
  if (typeof localStorage === "undefined") return 5000;
  const v = Number(localStorage.getItem("vetted-poll-ms") || 5000);
  return v >= 2000 ? v : 5000;
}

export default function RankedPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const blindParam = useSearchParams().get("blind");
  const [blindDefault] = useState(() =>
    typeof localStorage === "undefined" ? true : localStorage.getItem("vetted-blind") !== "0"
  );
  const blind = blindParam === "1" || (blindParam === null && blindDefault);
  const [job, setJob] = useState<JobDetail | null>(null);
  const [rows, setRows] = useState<RankRow[]>([]);
  const [pending, setPending] = useState<{ id: string; status: string }[]>([]);
  const [dups, setDups] = useState<{ a: string; b: string; kind: string; score: number }[]>([]);
  const [filter, setFilter] = useState<"all" | "short" | "flag">("all");
  const [sel, setSel] = useState<number>(-1);
  const [detail, setDetail] = useState<CandidateDetail | null>(null);
  const [interview, setInterview] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState("");
  const [csvBusy, setCsvBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [j, r, d] = await Promise.all([getJob(id), getRanking(id), getDuplicates(id)]);
      setJob(j);
      setRows(r.ranking || []);
      setPending(r.pending || []);
      setDups(d.pairs || []);
    } catch {
      setMsg("Backend unreachable on :8000.");
    }
  }, [id]);

  useEffect(() => {
    void Promise.resolve().then(() => refresh());
    const t = setInterval(refresh, pollMs());
    return () => clearInterval(t);
  }, [refresh]);

  async function openAt(i: number) {
    setSel(i);
    try {
      const c = await getCandidate(rows[i].candidate_id);
      setDetail(c);
    } catch {
      setMsg("Could not load candidate — backend unreachable.");
      return;
    }
    try {
      setInterview((await getInterview(rows[i].candidate_id)).questions || []);
    } catch {
      setInterview([]);
    }
  }

  async function decide(d: string) {
    if (!detail) return;
    if (!reason.trim()) {
      setMsg("Give a reason — recruiter has the last word, with receipt.");
      return;
    }
    try {
      await overrideCandidate(detail.id, d, reason);
    } catch {
      setMsg("Override failed — backend unreachable.");
      return;
    }
    setReason("");
    await refresh();
    try {
      if (sel >= 0) setDetail(await getCandidate(detail.id));
    } catch {
      setMsg("Refresh failed — backend unreachable.");
    }
  }

  const shown = rows.filter((r) =>
    filter === "all" ? true : filter === "short" ? r.final_decision === "shortlist" : (r.flags?.length || 0) > 0
  );
  const median = rows.length ? rows[Math.floor(rows.length / 2)].total : "—";
  const above = rows.filter((r) => r.total >= 85).length;
  const nameOf = (r: RankRow) => (blind ? "Candidate " + r.candidate_id.slice(0, 6) : prettyName(r.filename));
  const flagText = (r: RankRow) =>
    (r.flags || []).map(prettyFlag).join(" · ") +
    (r.close_call ? " · Close call" : "") +
    (r.overridden ? " · Overridden" : "");

  return (
    <div>
      <p className="text-[10px] tracking-widest" style={{ color: "var(--muted)" }}>
        RANKED CANDIDATES · {job?.title?.toUpperCase()} · GREEN ≥85 · YELLOW 70–85 · RED &lt;70
      </p>
      <div className="mt-1 flex items-end justify-between">
        <h1 className="font-display text-4xl">Ranked candidates</h1>
        <div className="flex gap-2 text-xs">
          {(["all", "short", "flag"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              aria-pressed={filter === f}
              className={filter === f ? "vetted-btn-dark" : "vetted-btn-ghost"}
            >
              {f === "all" ? `All · ${rows.length}` : f === "short" ? "Shortlisted" : `Flagged ${rows.filter((r) => r.flags?.length).length}`}
            </button>
          ))}
          <button
            onClick={() => {
              setCsvBusy(true);
              exportCsv(id, "ranking-" + id + ".csv")
                .catch(() => setMsg("CSV export failed — still signed in?"))
                .finally(() => setCsvBusy(false));
            }}
            disabled={csvBusy}
            className="vetted-btn-ghost"
            aria-busy={csvBusy}
          >
            ⭳ {csvBusy ? "Exporting…" : "Export"}
          </button>
        </div>
      </div>

      <div className="vetted-panel mt-4 grid grid-cols-4 p-4 text-center">
        {[
          ["RESUMES SCANNED", rows.length + pending.length],
          ["MEDIAN MATCH", median],
          ["ABOVE 85", above],
          ["DUPLICATE PAIRS", dups.length],
        ].map(([k, v]) => (
          <div key={k as string}>
            <p className="text-[10px] tracking-widest" style={{ color: "var(--muted)" }}>
              {k}
            </p>
            <p className="font-display text-3xl">{v}</p>
          </div>
        ))}
      </div>
      {msg && (
        <p className="mt-2 text-xs text-red-600" role="alert">
          {msg}
        </p>
      )}
      {pending.length > 0 && (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          Still scoring: {pending.map((p) => p.id.slice(0, 6) + ":" + p.status).join(", ")}
        </p>
      )}

      <div className="mt-4">
        {shown.map((r) => {
          const i = rows.indexOf(r);
          const [bg, fg] = rowBg(r);
          return (
            <div
              key={r.candidate_id}
              role="button"
              tabIndex={0}
              aria-label={`Open ${nameOf(r)}, score ${r.total}`}
              onClick={() => openAt(i)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  openAt(i);
                }
              }}
              className="mb-1 cursor-pointer rounded p-2 text-xs"
              style={{ background: bg, color: fg }}
            >
              <div className="flex items-center gap-3">
                <span style={{ opacity: 0.6 }}>{String(i + 1).padStart(2, "0")}</span>
                <span className="w-40 font-semibold">{nameOf(r)}</span>
                <span className="font-display text-lg font-bold">{r.total}</span>
                <div
                  className="vetted-bar w-24"
                  role="meter"
                  aria-valuenow={r.total}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`Score ${r.total} of 100`}
                >
                  <div style={{ width: r.total + "%", background: fg }} />
                </div>
                <span className="ml-auto" style={{ opacity: 0.75 }}>
                  {flagText(r)}
                </span>
                <span className="rounded border px-2 py-0.5 font-bold" style={{ borderColor: fg }}>
                  {r.final_decision === "shortlist" ? "SHORTLISTED" : r.final_decision === "reject" ? "PASS" : "IN REVIEW"}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {detail && sel >= 0 && (
        <div className="vetted-panel mt-6 p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[10px]" style={{ color: "var(--muted)" }}>
                RANKED #{sel + 1} OF {rows.length} · TOP {Math.round(((sel + 1) / Math.max(rows.length, 1)) * 100)}%
              </p>
              <h2 className="font-display text-3xl">{blind ? "Candidate " + detail.id.slice(0, 6) : prettyName(detail.filename)}</h2>
              <p className="text-xs" style={{ color: "var(--muted)" }}>
                {job?.title} · {detail.score?.relevant_years ?? "?"} yrs · {detail.filename}
              </p>
            </div>
            <div className="text-right">
              <p className="text-[10px]" style={{ color: "var(--muted)" }}>
                OVERALL MATCH
              </p>
              <p className="font-display text-4xl">{detail.score?.total} / 100</p>
              <div className="mt-1 flex gap-1">
                <button disabled={sel === 0} onClick={() => openAt(sel - 1)} className="vetted-btn-ghost text-xs disabled:opacity-30">
                  ← Prev
                </button>
                <button disabled={sel >= rows.length - 1} onClick={() => openAt(sel + 1)} className="vetted-btn-ghost text-xs disabled:opacity-30">
                  Next →
                </button>
              </div>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-3 gap-4">
            <div className="col-span-2">
              <p className="text-[10px] tracking-widest" style={{ color: "var(--muted)" }}>
                SUMMARY
              </p>
              <p className="mt-1 text-sm">{detail.explanation?.summary}</p>
              {(detail.explanation?.strengths || []).map((s, i: number) => (
                <div key={i} className="vetted-card mt-2 p-2 text-xs" style={{ background: "var(--green)", color: "var(--green-ink)" }}>
                  <b>+ {s.point}</b>
                  {s.quote && <p className="mt-1 italic">“{s.quote}”</p>}
                </div>
              ))}
              {(detail.explanation?.concerns || []).map((s, i: number) => (
                <div key={"c" + i} className="vetted-card mt-2 p-2 text-xs" style={{ background: "var(--yellow)", color: "var(--yellow-ink)" }}>
                  <b>− {s.point}</b>
                </div>
              ))}
              <p className="mt-3 text-[10px] tracking-widest" style={{ color: "var(--muted)" }}>
                INTERVIEW PROBES
              </p>
              {interview.map((q, i) => (
                <p key={i} className="mt-1 text-xs">
                  {i + 1}. {q}
                </p>
              ))}
            </div>
            <div>
              <p className="text-[10px] tracking-widest" style={{ color: "var(--muted)" }}>
                READING
              </p>
              {Object.entries(detail.score?.factors || {}).map(([k, v]) => (
                <div key={k} className="mt-2 text-xs">
                  <div className="flex justify-between">
                    <span>{prettyFactor(k)}</span>
                    <span>{v.value === null ? "N/A" : v.value}</span>
                  </div>
                  <div
                    className="vetted-bar"
                    role="meter"
                    aria-valuenow={v.value === null ? 0 : Math.round(v.value * 100)}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`${prettyFactor(k)}: ${v.value === null ? "not available" : Math.round(v.value * 100) + " of 100"}`}
                  >
                    <div style={{ width: (v.value === null ? 0 : v.value * 100) + "%" }} />
                  </div>
                </div>
              ))}
              <p className="mt-2 text-xs">Matched: {(detail.score?.matched_skills || []).map(prettySkill).join(", ") || "—"}</p>
              <p className="text-xs">Related: {(detail.score?.related_skills || []).map(prettySkill).join(", ") || "—"}</p>
              <p className="text-xs">Missing: {(detail.score?.missing_skills || []).map(prettySkill).join(", ") || "—"}</p>
              <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
                System: {detail.system_decision} → Final: {detail.final_decision}
                {detail.overridden ? " (Overridden by recruiter)" : ""}
              </p>
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Reason (required for override)"
                className="vetted-input mt-2 text-xs"
              />
              <div className="mt-2 flex gap-2">
                <button onClick={() => decide("shortlist")} className="vetted-btn-dark flex-1 text-xs">
                  Shortlist →
                </button>
                <button onClick={() => decide("reject")} className="vetted-btn-ghost flex-1 text-xs">
                  Pass
                </button>
              </div>
              <button onClick={() => { setSel(-1); setDetail(null); }} className="mt-2 text-xs underline">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
