// Co karta Studia ukáže (docs/studio.md §2): druh a ikona, stav slovy, souhrn dětí („4/7 stojí · 1 se staví“), díry a nálezy strážců.
// Čistá logika bez Reactu; karta je jen mapování těchto hodnot na JSX.
import type { StudioItem } from "../../logic/studio-tree";
import type { StudioState, StudioStatus, StudioSummary } from "../../logic/studio-status";
import type { StudioIconName } from "./studio-icons";
import type { GuardTally } from "../../studio-guards/logic/guard-tally";
import type { WorktreeTally } from "../../studio-worktree/logic/worktree-tally";

export const STATE_LABEL: Record<StudioState, string> = {
  plan: "plán", building: "staví se", done: "hotovo", verified: "ověřeno", hole: "díra",
};
export const KIND_LABEL: Record<StudioItem["kind"], string> = {
  domain: "Doména", page: "Stránka", section: "Sekce", component: "Komponenta",
};

/** Ikona podle druhu; komponenta podle vrstvy karty (frontend, backend, databáze, knihovna), jinak krabička. */
export function iconFor(item: StudioItem): StudioIconName {
  if (item.kind === "domain") return "globe";
  if (item.kind === "page") return "layout-dashboard";
  if (item.kind === "section") return "list-ordered";
  const layer = item.node?.card?.layer;
  return layer === "frontend" ? "monitor" : layer === "backend" ? "server-cog" : layer === "database" ? "database-zap" : layer === "library" ? "workflow" : "box";
}

/** Souhrn dětí jednou větou; karta bez potomků řekne jen „bez dětí“. */
export function summaryLine(summary: StudioSummary): string {
  if (!summary.total) return summary.children ? "jen prázdné sekce" : "bez dětí";
  return [`${summary.done}/${summary.total} stojí`, summary.building ? `${summary.building} se staví` : ""].filter(Boolean).join(" · ");
}

/** Odznak děr: „1 díra“, „3 díry“, „5 děr“; s dírami, které už zavírá worktree, „3 díry · 1 v práci“. */
export function holesLine(holes: number, inWork = 0): string {
  const count = `${holes} ${holes === 1 ? "díra" : holes > 1 && holes < 5 ? "díry" : "děr"}`;
  return inWork > 0 ? `${count} · ${inWork} v práci` : count;
}

/** Podtitulek karty: cesta stránky, role sekce, technologie komponenty, host domény. */
export function cardSubtitle(item: StudioItem): string {
  const site = item.node?.site;
  if (site?.kind === "application") return site.environments[0]?.host ?? "";
  if (site?.kind === "page") return site.path;
  if (item.section) return item.section.role;
  return item.node?.card?.tech ?? "";
}

export type StudioCardView = {
  id: string; name: string; kind: StudioItem["kind"]; kindLabel: string; subtitle: string; purpose: string; icon: StudioIconName;
  state: StudioState; stateLabel: string; summary: string; holes: number; children: number;
  /** Na kartu váže uzel MODELu domény: agent dostane jeho cíl v briefu (docs/studio.md §4a). */
  modelTarget: boolean;
  /** Otevřené nálezy strážců karty a jejích potomků (docs/strazci.md §5); `null` = žádný. */
  guards: GuardTally | null;
  /** Odznak děr jednou větou („3 díry · 1 v práci“); prázdný = bez děr. */
  holesText: string;
  /** Worktree karty a potomků (docs/navrhy/2026-10-28-kontrola-mapy-a-worktree.md §5); `null` = ve worktree se tu nepracuje. */
  worktree: WorktreeTally | null;
};

export function cardView(item: StudioItem, status: StudioStatus, modelTarget = false): StudioCardView {
  return {
    id: item.id, name: item.name, kind: item.kind, kindLabel: KIND_LABEL[item.kind], subtitle: cardSubtitle(item), purpose: item.purpose,
    icon: iconFor(item), state: status.state, stateLabel: STATE_LABEL[status.state], summary: summaryLine(status.summary),
    holes: status.summary.holes, children: status.summary.children, modelTarget,
    guards: status.guards, holesText: status.summary.holes > 0 ? holesLine(status.summary.holes, status.holesInWork) : "", worktree: status.worktree,
  };
}
