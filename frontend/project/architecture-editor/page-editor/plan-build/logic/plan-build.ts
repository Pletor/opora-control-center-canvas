// Stavba plátna 3 z plátna 2 (F3, docs/navrhy/2026-11-11-platno-3-folie.md „Srdce staví plátno 3“): srdce z plánu
// stránky nebo domény navrhne procesy, oblasti milníků, karty a vazby (`POST /api/page-plan/{id}/build-plan`). Výsledek
// je jen nepřijatý návrh grafu srdce; přijímá člověk. Tolerantní převod odpovědi a věty pro panel, bez Reactu, test vedle.
import { api } from "@/shared/types/logic/types";

export type PlanBuild = {
  counts: { areas: number; cards: number; edges: number };
  existing: { frames: number; areas: number; cards: number };
  /** Id procesu (sektoru „Plán práce“) první stránky, existuje-li; jinak null. */
  frameId: string | null;
  proposal: { id: string; reused: boolean } | null;
  skippedBoxes: string[]; skippedPages: string[]; unmatched: string[]; orphans: string[];
};

const num = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value : 0);
const rec = (value: unknown) => (value && typeof value === "object" ? value as Record<string, unknown> : {});
const names = (value: unknown, key: string) => (Array.isArray(value) ? value : []).map((item) => String(rec(item)[key] ?? "")).filter(Boolean);

export function parsePlanBuild(raw: unknown): PlanBuild {
  const value = rec(raw), counts = rec(value.counts), existing = rec(value.existing), skipped = rec(value.skipped);
  const proposal = rec(value.proposal), pages = Array.isArray(value.pages) ? value.pages : [];
  const frame = rec(pages[0]).frameId;
  return {
    counts: { areas: num(counts.areas), cards: num(counts.cards), edges: num(counts.edges) },
    existing: { frames: num(existing.frames), areas: num(existing.areas), cards: num(existing.cards) },
    frameId: typeof frame === "string" ? frame : null,
    proposal: typeof proposal.id === "string" ? { id: proposal.id, reused: proposal.reused === true } : null,
    skippedBoxes: names(skipped.boxes, "name"), skippedPages: names(skipped.pages, "name"),
    unmatched: (Array.isArray(value.unmatched) ? value.unmatched : []).map((item) => `${rec(item).name} → ${rec(item).dataTo}`),
    orphans: names(value.orphans, "name"),
  };
}

/** Věty panelu: co návrh přidá, co už stojí a co srdce vynechalo. */
export function planBuildLines(build: PlanBuild): string[] {
  const { counts, existing } = build;
  const lines = [build.proposal
    ? `Návrh srdce${build.proposal.reused ? " (už čeká)" : ""}: ${counts.areas} oblastí, ${counts.cards} karet, ${counts.edges} vazeb. Přijímá se v OporaHubu.`
    : existing.cards || existing.areas ? "Plátno 3 už má všechno z plánu stránky, návrh nevznikl."
    : "Stránka zatím nemá prvky logiky, srdce nemá z čeho stavět. Přidejte logiku boxům na plátně 2."];
  if (existing.cards || existing.areas) lines.push(`Už existuje: ${existing.cards} karet, ${existing.areas} oblastí.`);
  if (build.skippedBoxes.length) lines.push(`Boxy bez prvku logiky (bez karty): ${build.skippedBoxes.join(", ")}.`);
  if (build.skippedPages.length) lines.push(`Stránky bez logiky: ${build.skippedPages.join(", ")}.`);
  if (build.unmatched.length) lines.push(`Data mimo prvky stránky: ${build.unmatched.join("; ")}.`);
  if (build.orphans.length) lines.push(`Karty bez prvku (nemažou se): ${build.orphans.join(", ")}.`);
  return lines;
}

/** Stavba pro stránku nebo doménu (`id`). */
export async function buildPlan(scope: { project: string; workspace: string }, id: string): Promise<PlanBuild> {
  return parsePlanBuild(await api<unknown>(`/api/page-plan/${encodeURIComponent(id)}/build-plan`, scope));
}
