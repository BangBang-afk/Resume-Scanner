"use client";

import { useEffect, useState } from "react";

function initialDark(): boolean {
  if (typeof localStorage === "undefined") return false;
  return localStorage.getItem("vetted-theme") === "dark";
}

export default function ThemeToggle() {
  const [dark, setDark] = useState(initialDark);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  function toggle() {
    const next = !dark;
    setDark(next);
    localStorage.setItem("vetted-theme", next ? "dark" : "light");
  }

  return (
    <button onClick={toggle} className="vetted-btn-ghost text-xs" aria-label="Toggle theme">
      {dark ? "☀ Light" : "☾ Dark"}
    </button>
  );
}
