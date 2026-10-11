"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRequireAuth, SignOutButton } from "./require-auth";
import ThemeToggle from "./theme-toggle";

const NAV = [
  { href: "/", label: "Scan" },
  { href: "/ranked", label: "Ranked" },
  { href: "/candidates", label: "Candidates" },
  { href: "/roles", label: "Roles" },
  { href: "/shortlists", label: "Shortlists" },
  { href: "/settings", label: "Settings" },
];

export default function Sidebar() {
  const path = usePathname();
  // Session gate: every signed-in view renders here; signed-out redirects to /login.
  useRequireAuth();
  return (
    <aside className="flex w-44 shrink-0 flex-col gap-1 p-4">
      <Link href="/" className="mb-4 flex items-center gap-1 text-sm font-bold">
        <span aria-hidden="true" style={{ color: "var(--accent)" }}>●</span> Vetted
      </Link>
      {NAV.map((n) => (
        <Link
          key={n.href}
          href={n.href}
          className="rounded px-2 py-1 text-xs"
          aria-current={path === n.href || (n.href === "/ranked" && path.startsWith("/jobs/")) ? "page" : undefined}
          style={
            path === n.href || (n.href === "/ranked" && path.startsWith("/jobs/"))
              ? { background: "var(--card)", border: "1px solid var(--line)", fontWeight: 700 }
              : { color: "var(--muted)" }
          }
        >
          {n.label}
        </Link>
      ))}
      <div className="mt-auto flex flex-col gap-2">
        <SignOutButton />
        <ThemeToggle />
      </div>
    </aside>
  );
}
