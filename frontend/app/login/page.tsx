"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { login, register, setSession, isLoggedIn } from "@/lib/api";
import { useEffect } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (isLoggedIn()) router.replace("/");
  }, [router]);

  async function submit() {
    setErr("");
    if (mode === "register" && password !== password2) {
      setErr("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      const fn = mode === "register" ? register : login;
      const session = await fn(email.trim(), password);
      setSession(session.token, session.email);
      router.replace("/");
    } catch (e) {
      const msg = (e as Error).message;
      setErr(
        msg === "API 409" ? "That email is already registered."
        : msg === "API 401" ? "Wrong email or password."
        : msg === "API 422" ? "Password must be at least 8 characters."
        : "Backend unreachable on :8000 — is it running?"
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="vetted-panel w-full max-w-sm p-6">
        <p className="text-[10px] tracking-widest" style={{ color: "var(--muted)" }}>
          VETTED · RECRUITER ACCESS
        </p>
        <h1 className="font-display text-3xl mt-1">
          {mode === "login" ? "Sign in" : "Create account"}
        </h1>
        <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
          Applicant data is protected — every route requires a signed-in recruiter.
        </p>
        <form
          className="mt-4 space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <div>
            <label htmlFor="email" className="text-xs font-semibold">Email</label>
            <input id="email" type="email" autoComplete="email" required value={email}
              onChange={(e) => setEmail(e.target.value)} className="vetted-input mt-1 text-xs" />
          </div>
          <div>
            <label htmlFor="password" className="text-xs font-semibold">Password</label>
            <input id="password" type="password" autoComplete={mode === "register" ? "new-password" : "current-password"}
              required minLength={mode === "register" ? 8 : 1} value={password}
              onChange={(e) => setPassword(e.target.value)} className="vetted-input mt-1 text-xs" />
          </div>
          {mode === "register" && (
            <div>
              <label htmlFor="password2" className="text-xs font-semibold">Confirm password</label>
              <input id="password2" type="password" autoComplete="new-password" required value={password2}
                onChange={(e) => setPassword2(e.target.value)} className="vetted-input mt-1 text-xs" />
            </div>
          )}
          {err && (
            <p className="text-xs text-red-600" role="alert">{err}</p>
          )}
          <button type="submit" disabled={busy}
            className="vetted-btn-dark w-full text-sm disabled:opacity-50">
            {busy ? "Working…" : mode === "login" ? "Sign in →" : "Create account →"}
          </button>
        </form>
        <p className="mt-3 text-xs text-center">
          {mode === "login" ? "No account yet? " : "Already registered? "}
          <button className="underline" onClick={() => { setMode(mode === "login" ? "register" : "login"); setErr(""); }}>
            {mode === "login" ? "Register" : "Sign in"}
          </button>
        </p>
        <p className="mt-3 text-center">
          <Link href="/" className="text-xs underline" style={{ color: "var(--muted)" }}>
            Back to app
          </Link>
        </p>
      </div>
    </div>
  );
}
