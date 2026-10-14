// Brány cyklu v detailu fragmentu jen pro čtení (docs/schranka-neurony.md §3, §6, §9 body 4, 8, 9): stav každé
// brány, kdo ji zapnul (autor a druh aktéra), payload česky, proč cyklus stojí a stav fronty agentů (/next).
// Schránku ovládají agenti přes API; UI nic nepřepíná. Bez Reactu.
import type { FragmentDetail, GateEntry, GateName } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { GATES, gateTitle } from "@/editor/node-detail/brief-vault/logic/gate-bar";

const DECIDED = GATES.indexOf("decided");

const LABELS: Record<string, string> = { benefit: "přínos", risk: "riziko", type: "typ", done: "hotovo", prediction: "předpověď",
  tests: "testy", criticRounds: "kol kritika", verdict: "rozhodnutí", reason: "důvod", actual: "skutečnost", unexpected: "nečekané",
  lesson: "poučení", kind: "druh", predictionError: "predikční chyba", hash: "otisk plánu", summary: "souhrn", planId: "plán" };
const VALUES: Record<string, string> = { pass: "projdou", fail: "selžou", yes: "ano", other: "jinak", no: "ne", pattern: "vzor",
  antipattern: "antivzor", true: "ano", false: "ne" };

/** Payload jako řádky „klíč: hodnota“ česky; velké části plánu (`plan`, `sourceRevisions`…) a chyba předpovědi
 *  (ukazuje se zvlášť) se vynechají. */
export function payloadLines(payload: Record<string, unknown> | null | undefined): string[] {
  if (!payload) return [];
  return Object.entries(payload).flatMap(([key, value]) => {
    if (key === "predictionError") return [];
    if (value && typeof value === "object") {
      if (!["prediction", "actual"].includes(key)) return [];
      return payloadLines(value as Record<string, unknown>).map((line) => `${LABELS[key] ?? key} · ${line}`);
    }
    return [`${LABELS[key] ?? key}: ${VALUES[String(value)] ?? String(value)}`];
  });
}

/** „agent Hermes“ / „člověk Martin“: kdo zápis udělal (`by`) a jaký aktér to byl (`actor`). */
export function whoLabel(by: string | undefined, actor: string | undefined): string {
  const kind = actor === "human" ? "člověk" : actor === "agent" ? "agent" : actor || "neznámý";
  return by ? `${kind} ${by}` : kind;
}

export type GateRow = {
  gate: GateName;
  title: string;
  on: boolean;
  /** Zapnutý záznam s jiným otiskem vstupů: platí jako vypnutý. */
  stale: boolean;
  entry?: GateEntry;
  next: boolean;
  /** Proč cyklus u další brány na řadě stojí (jinak `""`). */
  waiting: string;
};

/** Řádky bran detailu: stav, záznam a proč stojí další brána na řadě. */
export function gateRows(detail: FragmentDetail): GateRow[] {
  const step = detail.gateStep ?? 0;
  return GATES.map((gate, index) => {
    const entry = detail.gateDetail?.[gate];
    const on = !!detail.gates?.[gate];
    const next = index === step && !on && !(detail.deadEnd && index > DECIDED);
    let waiting = "";
    if (next && detail.fragment.kind !== "brief") waiting = "Brány cyklu má jen fragment zadání.";
    else if (next && !detail.effectiveDiscipline) waiting = "Fragment nemá disciplínu (ani po předcích); agent ji musí přiřadit.";
    return { gate, title: gateTitle(gate), on, stale: !!entry?.value && !entry.valid, entry, next, waiting };
  });
}

/** Důvod slepé uličky z payloadu brány `decided`. */
export function deadEndReason(detail: FragmentDetail): string {
  const reason = detail.gateDetail?.decided?.payload?.reason;
  return typeof reason === "string" ? reason : "";
}

/** Odpověď `GET /api/brief-vault/next` (fronta agentů, nezávazná). */
export type NextWork = {
  fragment: { id: string; title: string; effectiveDiscipline: string; revision: number } | null;
  gate?: GateName;
  needs?: "proposal" | "confirm";
  proposal?: { payload: Record<string, unknown>; by: string; actor: string; at: string; note: string };
  blocked: number;
};

/** Věta o frontě agentů disciplíny z pohledu fragmentu. */
export function queueText(next: NextWork | undefined, fragmentId: string): string {
  if (!next) return "";
  const blocked = next.blocked ? ` · ${next.blocked} čeká na návrh nebo schválení člověka` : "";
  if (!next.fragment || !next.gate) return `Fronta agentů disciplíny je prázdná${blocked}.`;
  const what = `${gateTitle(next.gate)} (${next.needs === "confirm" ? "čeká na potvrzení návrhu" : "čeká na návrh"})`;
  const who = next.fragment.id === fragmentId ? "tento fragment" : `„${next.fragment.title}“`;
  return `Fronta agentů: další na řadě ${who} · ${what}${blocked}.`;
}
