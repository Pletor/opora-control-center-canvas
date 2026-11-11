import type { Tone } from "../logic/element-tone";

// Jednoduché inline ikony; barvu berou z `currentColor`, aby je obarvil tón dílku.
const PATHS: Record<string, string> = {
  area: "M12 3 4 7v10l8 4 8-4V7l-8-4Zm0 0v18M4 7l8 4 8-4",
  sector: "M4 6h16v4H4zM4 14h16v4H4z",
  frontend: "M3 5h18v14H3zM3 9h18M8 13h8",
  backend: "M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01",
  database: "M12 3c4.4 0 8 1.3 8 3v12c0 1.7-3.6 3-8 3s-8-1.3-8-3V6c0-1.7 3.6-3 8-3Zm-8 3c0 1.7 3.6 3 8 3s8-1.3 8-3",
  library: "M4 7l8-4 8 4-8 4-8-4Zm0 5 8 4 8-4M4 17l8 4 8-4",
  neutral: "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16Z",
  structure: "M12 3v6M5 15v-3h14v3M5 15v6M19 15v6M12 9v3M9 3h6",
  workflow: "M4 12h12m-4-4 4 4-4 4M20 5v14",
  pipeline: "M4 7h6v4H4zM14 13h6v4h-6zM10 9h2v6h2",
};

export type IconName = Tone | "area" | "sector" | "structure" | "workflow" | "pipeline";

export default function StructureIcon({ name, label, className }: { name: IconName; label?: string; className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <path d={PATHS[name] ?? PATHS.neutral} />
    </svg>
  );
}
