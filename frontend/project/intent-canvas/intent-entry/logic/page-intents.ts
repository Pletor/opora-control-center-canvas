// Stav záměru každé stránky projektu pro odznak u tlačítka „Záměr“ (kontrakt
// `docs/navrhy/2026-11-03-platno-2-zamer-stranky.md` §4–§5): `GET /api/flow/page-intents?project=<id>` vrací
// `{"pages": [{pageId, state, workflowId?, activeN?, candidateN?, doneCount}]}`. Endpoint, který ještě není (404),
// nebo jiná chyba čtení znamená „stav neznámý“: tlačítko zůstane, odznak ne.
import { api } from "@/shared/types/logic/types";

export type PageIntentState = "none" | "pending" | "approved" | "stale";
export type PageIntent = { pageId: string; state: PageIntentState; workflowId?: string; activeN?: number; candidateN?: number; doneCount: number };
export type PageIntents = ReadonlyMap<string, PageIntent>;
export type IntentBadge = { label: string; tone: PageIntentState; title: string };

const STATES = new Set<PageIntentState>(["none", "pending", "approved", "stale"]);
export const pageIntentsUrl = (project: string) => `/api/flow/page-intents?${new URLSearchParams({ project })}`;

export function parsePageIntents(raw: unknown): PageIntents {
  const pages = raw && typeof raw === "object" ? (raw as { pages?: unknown }).pages : null;
  const rows = Array.isArray(pages) ? pages as PageIntent[] : [];
  return new Map(rows.filter((row) => row && typeof row.pageId === "string" && STATES.has(row.state)).map((row) => [row.pageId, row]));
}

/** null = stav neznámý (endpoint chybí nebo selhal), mapa = stav každé stránky, kterou server zná. */
export const loadPageIntents = (project: string): Promise<PageIntents | null> =>
  api<unknown>(pageIntentsUrl(project)).then(parsePageIntents, () => null);

/** Odznak u tlačítka „Záměr“: bez záměru, čeká, schválený vN, zastaralý (stránka se změnila po schválení). */
export function intentBadge(intent: PageIntent | undefined): IntentBadge | null {
  if (!intent) return null;
  const done = `${intent.doneCount} kritérií hotovo`;
  if (intent.state === "pending") return { label: "čeká", tone: "pending", title: `Kandidát v${intent.candidateN ?? "?"} čeká na schválení · ${done}` };
  if (intent.state === "approved") return { label: intent.activeN ? `schválený v${intent.activeN}` : "schválený", tone: "approved", title: done };
  if (intent.state === "stale") return { label: "zastaralý", tone: "stale", title: `Stránka se změnila po schválení v${intent.activeN ?? "?"} · ${done}` };
  return { label: "bez záměru", tone: "none", title: "Stránka zatím nemá záměr" };
}
