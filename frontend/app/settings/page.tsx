"use client";

import { useState } from "react";

function stored(key: string, fallback: string): string {
  if (typeof localStorage === "undefined") return fallback;
  return localStorage.getItem(key) ?? fallback;
}

export default function SettingsPage() {
  const [api, setApi] = useState(() => stored("vetted-api", ""));
  const [blind, setBlind] = useState(() => stored("vetted-blind", "1") !== "0");
  const [poll, setPoll] = useState(() => stored("vetted-poll-ms", "5000"));
  const [dark, setDark] = useState(() => stored("vetted-theme", "light") === "dark");
  const [saved, setSaved] = useState("");

  function save() {
    if (api.trim()) localStorage.setItem("vetted-api", api.trim().replace(/\/$/, ""));
    else localStorage.removeItem("vetted-api");
    localStorage.setItem("vetted-blind", blind ? "1" : "0");
    localStorage.setItem("vetted-poll-ms", poll);
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("vetted-theme", dark ? "dark" : "light");
    setSaved("Saved — reload pages to apply API + polling.");
  }

  function resetAll() {
    ["vetted-api", "vetted-blind", "vetted-poll-ms", "vetted-theme"].forEach((k) => localStorage.removeItem(k));
    document.documentElement.classList.remove("dark");
    setApi("");
    setBlind(true);
    setPoll("5000");
    setDark(false);
    setSaved("Defaults restored.");
  }

  return (
    <div>
      <h1 className="font-display text-4xl">Settings</h1>
      <div className="vetted-panel mt-4 max-w-md space-y-3 p-4 text-xs">
        <div>
          <label className="font-semibold">Backend API URL</label>
          <input value={api} onChange={(e) => setApi(e.target.value)} placeholder="http://localhost:8000" className="vetted-input mt-1" />
        </div>
        <label className="flex items-center justify-between">
          Blind mode default (hide names)
          <input type="checkbox" checked={blind} onChange={(e) => setBlind(e.target.checked)} />
        </label>
        <div>
          <label className="font-semibold">Ranking refresh rate</label>
          <select value={poll} onChange={(e) => setPoll(e.target.value)} className="vetted-input mt-1">
            <option value="2000">Every 2s (live demo)</option>
            <option value="5000">Every 5s (default)</option>
            <option value="10000">Every 10s (slow venue wifi)</option>
          </select>
        </div>
        <label className="flex items-center justify-between">
          Dark theme
          <input type="checkbox" checked={dark} onChange={(e) => setDark(e.target.checked)} />
        </label>
        <div className="flex gap-2">
          <button onClick={save} className="vetted-btn-dark flex-1">Save</button>
          <button onClick={resetAll} className="vetted-btn-ghost flex-1">Reset defaults</button>
        </div>
        {saved && <p style={{ color: "var(--muted)" }}>{saved}</p>}
      </div>
      <div className="vetted-panel mt-4 max-w-md p-4 text-xs">
        <p className="font-semibold">How scoring works</p>
        <p className="mt-1" style={{ color: "var(--muted)" }}>
          total = 100 × (0.40 must + 0.20 preferred + 0.20 experience + 0.10 projects + 0.10
          education). Missing must-have caps at 69. Decisions: ≥80 shortlist, 60–79 review,
          &lt;60 reject. Row colors: green ≥85, yellow 70–85, red below 70.
        </p>
      </div>
    </div>
  );
}
