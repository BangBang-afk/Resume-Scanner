"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { clearSession, getEmail, isLoggedIn } from "@/lib/api";

/** Redirects to /login when there is no session. Returns the signed-in email or null. */
export function useRequireAuth(): string | null {
  const router = useRouter();
  const [email] = useState<string | null>(() => getEmail());
  useEffect(() => {
    if (typeof localStorage !== "undefined" && !isLoggedIn()) {
      router.replace("/login");
    }
  }, [router]);
  return email;
}

export function SignOutButton() {
  const router = useRouter();
  return (
    <button
      className="vetted-btn-ghost w-full text-xs"
      onClick={() => {
        clearSession();
        router.replace("/login");
      }}
    >
      Sign out {getEmail() ? `· ${getEmail()}` : ""}
    </button>
  );
}
