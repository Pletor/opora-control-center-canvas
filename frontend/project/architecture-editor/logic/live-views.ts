// Převod živého stavu (`useDomainLive`) na hotová data pro dílky přehledu a plátna 2. Bez Reactu,
// aby ArchitectureEditor jen skládal a dílky dostaly přesně to, co vykreslí.
import type { DomainLive } from "./use-domain-live";
import { domainLive } from "../live-status/logic/live-model";
import { staleNote } from "../live-status/logic/live-poll";
import { webView, type WebView } from "../live-status/logic/web-slots";
import type { LiveWorkView } from "../live-status/components/LiveDomainPanel";

type Live = Pick<DomainLive, "worktreeLive" | "work" | "web">;

/** Žeton webu a stav práce jedné domény; `work` je `null` u projektu bez worktree (panel se pak nevykreslí). */
export function panelViews(live: Live, domainId: string): { web: WebView; work: LiveWorkView | null } {
  const web = webView(live.web, domainId);
  if (!live.worktreeLive) return { web, work: null };
  return { web, work: { domain: domainLive(live.work.data, domainId), loaded: live.work.data !== null, stale: staleNote(live.work), loading: live.work.loading, error: live.work.error } };
}
