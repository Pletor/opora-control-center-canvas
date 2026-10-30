// Odznak PR v barvách GitHubu (fialová sloučeno, zelená otevřené, červená zavřené bez sloučení). Dostává hotový
// `PrBadge` z `logic/pr-badge.ts`; bez odznaku nic nekreslí. Značka a slovo nesou význam i bez barvy.
import type { PrBadge as Badge } from "../logic/pr-badge";
import "../styles/pr-badge.css";

const GLYPH: Record<Badge["tone"], string> = { merged: "✓", open: "○", closed: "✕" };

export default function PrBadge({ badge }: { badge: Badge | null | undefined }) {
  if (!badge) return null;
  return (
    <span className={"pr-badge pr-badge--" + badge.tone} data-oh-pr-state={badge.tone} title={badge.label}>
      <span className="pr-badge__glyph" aria-hidden="true">{GLYPH[badge.tone]}</span>{badge.label}
    </span>
  );
}
