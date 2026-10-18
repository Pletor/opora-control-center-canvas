// Brány cyklu v detailu fragmentu jen pro čtení (docs/schranka-neurony.md §3, §6, §9 body 4, 8, 9): stav každé
// brány, kdo ji zapnul (autor a druh aktéra), payload česky, proč cyklus stojí a stav fronty agentů (/next).
// Schránku ovládají agenti přes API; UI nic nepřepíná. Bez Reactu.
import type { FragmentDetail, GateEntry, GateName, GateProposal } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { GATES, gateTitle, roundLabel } from "@/editor/node-detail/brief-vault/logic/gate-bar";

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
    if (key === "predictionError" || key === "steps" || key === "layer" || key === "runTrust") return [];  // razítko běhu má vlastní štítek (cell-view); kroky a vrstva mají vlastní zobrazení
    if (value && typeof value === "object") {
      if (!["prediction", "actual"].includes(key)) return [];
      const inner = { ...(value as Record<string, unknown>) };
      if (key === "actual") for (const own of ["tests", "planApproved", "planScore"]) delete inner[own];  // mají vlastní štítky (verifiedOutcome)
      return payloadLines(inner).map((line) => `${LABELS[key] ?? key} · ${line}`);
    }
    return [`${LABELS[key] ?? key}: ${VALUES[String(value)] ?? String(value)}`];
  });
}

export type VerifiedOutcome = { plan: { text: string; approved: boolean }; tests: { text: string; state: "pass" | "fail" | "untested" } };

/** Dva oddělené údaje brány Ověřeno ze `skutečnosti`: plán (schválen/neschválen + skóre 0–10) a testy (prošly/neprošly/neběžely).
 *  Bez `planApproved` (starší payload) platí `planApproved = tests == "pass"`. `null`, když skutečnost chybí. */
export function verifiedOutcome(actual: unknown): VerifiedOutcome | null {
  if (!actual || typeof actual !== "object") return null;
  const a = actual as Record<string, unknown>;
  const state = a.tests === "pass" || a.tests === "fail" ? a.tests : "untested";
  const approved = typeof a.planApproved === "boolean" ? a.planApproved : state === "pass";
  const score = typeof a.planScore === "number" ? `${a.planScore}/10` : "";
  return {
    plan: { approved, text: `plán ${approved ? "schválen" : "neschválen"}${score ? " " + score : ""}` },
    tests: { state, text: state === "pass" ? "testy prošly" : state === "fail" ? "testy neprošly" : "testy neběžely" },
  };
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

/** Stav návrhu brány česky: kdo ho podal a co se s ním stalo (čeká, použit, zamítnut kým a proč). */
export function proposalStatus(proposal: GateProposal): string {
  const author = `navrhl ${whoLabel(proposal.by, proposal.actor)}`;
  if (proposal.status === "used") return `${author} · použit`;
  if (proposal.status === "pending") return `${author} · čeká na potvrzení`;
  const rejection = proposal.rejection;
  if (rejection?.gateOff) return `${author} · neplatí (brána vypnuta po návrhu)`;
  const note = rejection?.note ? `: ${rejection.note}` : "";
  return `${author} · zamítl ${rejection ? whoLabel(rejection.by, rejection.actor) : "neznámý"}${note}`;
}

/** Důvod slepé uličky z payloadu brány `decided`. */
export function deadEndReason(detail: FragmentDetail): string {
  const reason = detail.gateDetail?.decided?.payload?.reason;
  return typeof reason === "string" ? reason : "";
}

/** Odpověď `GET /api/brief-vault/next` (fronta agentů, nezávazná). */
export type NextWork = {
  fragment: { id: string; title: string; effectiveDiscipline: string; revision: number } | null;
  /** `null` u otevřeného duelu (hlava fronty, docs/schranka-duel.md §4). */
  gate?: GateName | null;
  needs?: "proposal" | "confirm" | "duel";
  hint?: string;
  proposal?: { payload: Record<string, unknown>; by: string; actor: string; at: string; note: string };
  blocked: number;
  /** Rozpad `blocked`: proč fragmenty čekají (návrh, potvrzení, plán, vyčerpaná kola, otevřený duel o směru). */
  blockedBy?: Partial<Record<"proposal" | "confirm" | "plan" | "exhausted" | "duel", number>>;
};

const BLOCK_WORDS: [keyof NonNullable<NextWork["blockedBy"]>, string][] = [["proposal", "na návrh"], ["confirm", "na schválení vložení"],
  ["plan", "na nový plán"], ["exhausted", "vyčerpáno, na člověka"], ["duel", "čeká na duel"]];

/** Věta o frontě agentů disciplíny z pohledu fragmentu. */
export function queueText(next: NextWork | undefined, fragmentId: string): string {
  if (!next) return "";
  const parts = BLOCK_WORDS.filter(([key]) => next.blockedBy?.[key])
    .map(([key, word]) => (key === "duel" ? `${word} ${next.blockedBy?.duel}` : `${next.blockedBy?.[key]}× ${word}`));
  const blocked = next.blocked ? ` · ${next.blocked} čeká` + (parts.length ? ` (${parts.join(", ")})` : " na návrh nebo schválení člověka") : "";
  if (next.needs === "duel" && next.fragment) return `Na řadě duel: ${(next.hint || next.fragment.title).replace(/^Duel:\s*/, "").replace(/\.$/, "")}${blocked}.`;
  if (!next.fragment || !next.gate) return `Fronta agentů disciplíny je prázdná${blocked}.`;
  const what = `${gateTitle(next.gate)} (${next.needs === "confirm" ? "čeká na potvrzení návrhu" : "čeká na návrh"})`;
  const who = next.fragment.id === fragmentId ? "tento fragment" : `„${next.fragment.title}“`;
  return `Fronta agentů: další na řadě ${who} · ${what}${blocked}.`;
}

/** Krátký důvod, proč fragment čeká (návrh / potvrzení / schválení vložení / vyčerpaná kola); `""` = nečeká. */
export function blockReason(detail: FragmentDetail): string {
  if (detail.deadEnd) return "";
  if (detail.exhausted) return "čeká na člověka";
  const gate = GATES[detail.gateStep ?? 0];
  if (!gate || detail.fragment.kind !== "brief" || !detail.effectiveDiscipline) return "";
  if (gate === "placed") return "čeká na schválení vložení";
  if (detail.proposals?.[gate]?.status === "pending") return "čeká na potvrzení návrhu";
  return "čeká na návrh";
}

/** Věta nad bránami: „kolo 2/3 · čeká na návrh“ nebo „vyčerpáno – čeká na člověka“. */
export function roundLine(detail: FragmentDetail): { text: string; exhausted: boolean } | null {
  const round = roundLabel(detail);
  if (!round) return null;
  const reason = round.exhausted ? "" : blockReason(detail);
  return { text: reason ? `${round.text} · ${reason}` : round.text, exhausted: round.exhausted };
}
