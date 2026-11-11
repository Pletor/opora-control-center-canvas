export type PageIconName = "frontend" | "backend" | "database" | "security" | "logic" | "user" | "rule" | "layout" | "page" | "tree" | "area";

/** Outline pictograms (currentColor, 24 grid). Meaning is always carried by the adjacent label. */
const PATHS: Record<PageIconName, string> = {
  frontend: "M4 5h16v11H4zM9 20h6M12 16v4",
  logic: "M8 4C5 4 6 10 3 12c3 2 2 8 5 8M16 4c3 0 2 6 5 8-3 2-2 8-5 8",
  backend: "M12 8a4 4 0 100 8 4 4 0 000-8zM12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2",
  database: "M4 6c0-3 16-3 16 0v12c0 3-16 3-16 0zM4 6c0 3 16 3 16 0M4 12c0 3 16 3 16 0",
  security: "M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z",
  area: "M12 2l9 5v10l-9 5-9-5V7zM3 7l9 5 9-5M12 12v10",
  user: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 21c0-4 4-6 8-6s8 2 8 6",
  rule: "M10 6h10M10 12h10M10 18h10M4 6l1.5 1.5L8 5M4 12l1.5 1.5L8 11M4 18l1.5 1.5L8 17",
  layout: "M3 4h18v16H3zM3 9h18M9 9v11",
  page: "M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h5",
  tree: "M5 4v16M5 8h6M5 16h6M11 6h8v4h-8zM11 14h8v4h-8z",
};

export default function PageIcon({ name, className, size = 18 }: { name: PageIconName; className?: string; size?: number }) {
  return <svg className={className} viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor"
    strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={PATHS[name]}/></svg>;
}
