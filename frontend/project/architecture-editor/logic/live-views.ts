// Převod živého stavu (`useDomainLive`) na hotová data pro dílky přehledu a mapy domény. Bez Reactu,
// aby ArchitectureEditor jen skládal a dílky dostaly přesně to, co vykreslí.
import type { Graph } from "@/shared/types/logic/types";
import type { DomainLive } from "./use-domain-live";
import { domainLive, pagesTouched, pageWorkCounts } from "../live-status/logic/live-model";
import { staleNote } from "../live-status/logic/live-poll";
import { webView, type WebView } from "../live-status/logic/web-slots";
import type { LiveWorkView } from "../live-status/components/LiveDomainPanel";
import type { PageWork } from "../domain-map/components/PageCard";

type Live = Pick<DomainLive, "worktreeLive" | "work" | "web">;

/** Žeton webu a stav práce jedné domény; `work` je `null` u projektu bez worktree (panel se pak nevykreslí). */
export function panelViews(live: Live, domainId: string): { web: WebView; work: LiveWorkView | null } {
  const web = webView(live.web, domainId);
  if (!live.worktreeLive) return { web, work: null };
  return { web, work: { domain: domainLive(live.work.data, domainId), loaded: live.work.data !== null, stale: staleNote(live.work), loading: live.work.loading, error: live.work.error } };
}

/** Odznaky „N worktree“ na kartách stránek a stránky zvýrazněné vybraným worktree. */
export function pageWork(graph: Graph, live: Live, domainId: string, worktreeId: string | null): PageWork | undefined {
  const domain = live.worktreeLive ? domainLive(live.work.data, domainId) : null;
  if (!domain) return undefined;
  const selected = domain.worktrees.find((item) => item.id === worktreeId);
  const ids = selected ? [...selected.cards.map((card) => card.nodeId), ...selected.sessions.map((s) => s.nodeId).filter((id): id is string => !!id)] : [];
  return { counts: pageWorkCounts(graph, domain.worktrees), highlighted: pagesTouched(graph, ids) };
}
