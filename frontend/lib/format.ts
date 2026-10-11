const SKILL_DISPLAY: Record<string, string> = {
  "machine learning": "Machine Learning",
  postgresql: "PostgreSQL",
  javascript: "JavaScript",
  typescript: "TypeScript",
  kubernetes: "Kubernetes",
  python: "Python",
  docker: "Docker",
  fastapi: "FastAPI",
  django: "Django",
  react: "React",
  sql: "SQL",
  aws: "AWS",
};

const FLAG_DISPLAY: Record<string, string> = {
  MISSING_MUST_HAVE: "Missing must-have",
  INCOMPLETE_RESUME: "Incomplete resume",
};

const FACTOR_LABEL: Record<string, string> = {
  must: "Must-have skills",
  preferred: "Preferred skills",
  experience: "Experience",
  projects: "Projects",
  education: "Education",
};

export function prettySkill(s: string): string {
  const k = s.trim().toLowerCase();
  if (SKILL_DISPLAY[k]) return SKILL_DISPLAY[k];
  return s.trim().replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function prettyFlag(f: string): string {
  return FLAG_DISPLAY[f] || f.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

export function prettyFactor(k: string): string {
  return FACTOR_LABEL[k] || k.replace(/_/g, " ");
}

export function prettyName(filename: string): string {
  return filename
    .replace(/\.[^.]+$/, "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Row band by score: green >= 85, yellow 70–85, red below 70. */
export function bandByScore(total: number): "green" | "yellow" | "red" {
  if (total >= 85) return "green";
  if (total >= 70) return "yellow";
  return "red";
}
