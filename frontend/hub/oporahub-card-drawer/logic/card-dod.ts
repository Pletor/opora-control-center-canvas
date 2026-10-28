import type { CardEntry } from "./card-header";

// Jediná definice hotovo (kontrakt §3) jako sedm dílků v hlavičce: kroky · akceptace karty · brána ·
// sloučeno · plán zapsán · cesta ověřena · uzavřel člověk. Zdrojem je backendové `cards[].dod` (opora_card_done,
// boolean na požadavek + druh brány; u nesplněné brány cesty i `blockingJourneys`, docs/brana-cesty.md §5). Výpočet na klientovi (`computeDod`) je jen náhrada pro starší server bez `dod`;
// z něj se u backendového stavu bere jen odstín „rozpracováno“ u nesplněných dílků.
export const DOD_KEYS = ["steps", "card_acceptance", "gate_ready", "merged", "plan_written_back", "journeys", "human_close"] as const;
export type DodKey = typeof DOD_KEYS[number];
export type DodState = "done" | "active" | "todo" | "unknown";
export type DodSegment = { key: DodKey; label: string; state: DodState; detail: string; progress: number };
export type DodView = { source: "backend" | "computed"; done: boolean; segments: DodSegment[];
  /** Druh brány z backendu: `review` (brána OporaHubu), `external` (ochrana větve na GitHubu) nebo `local`
   * (projekt bez GitHubu: sloučení ohlášené `local-merge` + kontroly na commitu, docs/lokalni-slouceni.md). */
  gate: "review" | "external" | "local" | null };

const LABEL: Record<DodKey, string> = {
  steps: "Kroky", card_acceptance: "Akceptace karty", gate_ready: "Brána", merged: "Sloučeno",
  plan_written_back: "Plán zapsán", journeys: "Cesta ověřena", human_close: "Uzavřel člověk",
};

export type DodFacts = {
  card: CardEntry | null;
  /** Postup kroků z výsledků běhu, když agent-state `steps` ještě nenese. */
  steps?: { total: number; done: number } | null;
  /** Akceptace karty doložená proti přijatému zadání; `null` = klient to neumí zjistit. */
  acceptance?: boolean | null;
  gateStatus?: string | null;
  prState?: string | null;
  /** Druhy událostí karty (`merge.done`, `writeback.done`, `card.closed`, …). */
  eventKinds?: Set<string>;
  /** Člověk kartu uzavřel (process-sync `doneConfirmed`). */
  closed?: boolean;
};

/** Backendové `dod`: boolean pod jménem každého požadavku (agent-state), nebo jen `{done, missing: [klíč]}`.
 * Starší server bez brány cesty `journeys` nenese: ta se pak bere jako splněná (karta mimo cesty). */
export function backendDod(raw: unknown): Record<DodKey, boolean> | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const value: Record<string, unknown> = { journeys: true, ...(raw as Record<string, unknown>) };
  if (DOD_KEYS.every(key => typeof value[key] === "boolean"))
    return Object.fromEntries(DOD_KEYS.map(key => [key, value[key]])) as Record<DodKey, boolean>;
  if (Array.isArray(value.missing)) {
    const missing = new Set(value.missing.filter(item => typeof item === "string"));
    return Object.fromEntries(DOD_KEYS.map(key => [key, !missing.has(key)])) as Record<DodKey, boolean>;
  }
  return null;
}

function backendGate(raw: unknown): DodView["gate"] {
  const gate = raw && typeof raw === "object" ? (raw as Record<string, unknown>).gate : null;
  return gate === "review" || gate === "external" || gate === "local" ? gate : null;
}

function stepsSegment(facts: DodFacts): Omit<DodSegment, "key" | "label"> {
  const steps = facts.card?.steps ?? facts.steps ?? null;
  if (!steps || steps.total === 0) return { state: "unknown", detail: "bez kroků", progress: 0 };
  const progress = Math.min(1, steps.done / steps.total);
  return { state: steps.done >= steps.total ? "done" : steps.done > 0 ? "active" : "todo", detail: `${steps.done}/${steps.total}`, progress };
}

export function computeDod(facts: DodFacts): Record<DodKey, DodState> {
  const card = facts.card, kinds = facts.eventKinds ?? new Set<string>(), reason = card?.reason ?? "";
  const closed = facts.closed === true || reason === "card_closed" || kinds.has("card.closed");
  const writtenBack = closed || reason === "plan_written_back" || reason === "awaiting_human_close" || kinds.has("writeback.done");
  const merged = writtenBack || facts.prState === "merged" || reason === "merged" || reason === "merged_without_plan_writeback" || kinds.has("merge.done");
  const gate = facts.gateStatus ?? card?.gate?.status ?? null;
  return {
    steps: stepsSegment(facts).state,
    card_acceptance: facts.acceptance === true || merged ? "done" : facts.acceptance === false ? "todo" : "unknown",
    gate_ready: gate === "ready" || merged ? "done" : gate === "blocked" || gate === "pending" ? "active" : "todo",
    merged: merged ? "done" : facts.prState === "open" ? "active" : "todo",
    plan_written_back: writtenBack ? "done" : merged ? "active" : "todo",
    // Ověření cest klient sám nezjistí: bez backendového `dod` jen uzavřená karta je jistě ověřená.
    journeys: closed ? "done" : "unknown",
    human_close: closed ? "done" : reason === "awaiting_human_close" ? "active" : "todo",
  };
}

/** Cesty, které brání uzavření (backend `dod.blockingJourneys`): „Kampaň: zastaralé; …“, jinak prázdný text. */
export function blockingJourneysText(raw: unknown): string {
  const list = raw && typeof raw === "object" ? (raw as Record<string, unknown>).blockingJourneys : null;
  if (!Array.isArray(list)) return "";
  return list.flatMap((item) => {
    const { name, reason } = (item && typeof item === "object" ? item : {}) as Record<string, unknown>;
    return typeof name === "string" && typeof reason === "string" ? [`${name}: ${reason}`] : [];
  }).join("; ");
}

/** Dílky definice hotovo v pevném pořadí kontraktu. */
export function dodView(facts: DodFacts): DodView {
  const fromBackend = backendDod(facts.card?.dod);
  const gate = fromBackend ? backendGate(facts.card?.dod) : null;
  const computed = computeDod(facts);
  const steps = stepsSegment(facts);
  const segments = DOD_KEYS.map(key => {
    const state: DodState = fromBackend ? (fromBackend[key] ? "done" : computed[key] === "active" ? "active" : "todo") : computed[key];
    const progress = key === "steps" ? (state === "done" ? 1 : steps.progress) : state === "done" ? 1 : 0;
    const detail = key === "steps" ? steps.detail : key === "gate_ready" && gate === "external" ? "GitHub"
      : key === "gate_ready" && gate === "local" ? "lokálně"
      : key === "journeys" && state !== "done" ? blockingJourneysText(facts.card?.dod)
      : state === "unknown" ? "nenapojeno" : "";
    return { key, label: LABEL[key], state, detail, progress };
  });
  return { source: fromBackend ? "backend" : "computed", done: segments.every(item => item.state === "done"), segments, gate };
}
