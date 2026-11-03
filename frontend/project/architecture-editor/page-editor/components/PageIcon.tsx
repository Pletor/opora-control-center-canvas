import type { IconName } from "../logic/library-families";
import type { Tone } from "../logic/canvas-model";

export type PageIconName = IconName | Tone | "web" | "app" | "admin" | "android" | "ios" | "page" | "area" | "tree" | "library";

/** Outline pictograms (currentColor, 24 grid). Meaning is always carried by the adjacent label. */
const PATHS: Record<PageIconName, string> = {
  frontend: "M4 5h16v11H4zM9 20h6M12 16v4",
  style: "M4 20l4-1L19 8l-3-3L5 16zM14 7l3 3",
  logic: "M8 4C5 4 6 10 3 12c3 2 2 8 5 8M16 4c3 0 2 6 5 8-3 2-2 8-5 8",
  backend: "M12 8a4 4 0 100 8 4 4 0 000-8zM12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2",
  tenant: "M3 11l9-7 9 7M5 10v10h14V10M10 20v-6h4v6",
  database: "M4 6c0-3 16-3 16 0v12c0 3-16 3-16 0zM4 6c0 3 16 3 16 0M4 12c0 3 16 3 16 0",
  security: "M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z",
  tests: "M9 3h6M10 3v6l-5 10h14l-5-10V3",
  cache: "M13 2L4 14h7l-1 8 9-12h-7z",
  cloud: "M7 18h10a4 4 0 000-8 6 6 0 00-11.5 1.5A3.3 3.3 0 007 18z",
  infrastructure: "M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01",
  area: "M12 2l9 5v10l-9 5-9-5V7zM3 7l9 5 9-5M12 12v10",
  web: "M12 3a9 9 0 100 18 9 9 0 000-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18",
  app: "M4 4h16v16H4zM9 9h6v6H9z",
  android: "M6 6h12v15H6zM9 6L7.5 3.5M15 6l1.5-2.5M10 10h.01M14 10h.01",
  ios: "M7 2.5h10v19H7zM10.5 5h3M11 18.5h2",
  admin: "M12 9a3 3 0 100 6 3 3 0 000-6zM12 3v3M12 18v3M3 12h3M18 12h3M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2",
  page: "M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h5",
  tree: "M5 4v16M5 8h6M5 16h6M11 6h8v4h-8zM11 14h8v4h-8z",
  library: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
};

export default function PageIcon({ name, className, size = 18 }: { name: PageIconName; className?: string; size?: number }) {
  return <svg className={className} viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor"
    strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={PATHS[name]}/></svg>;
}
