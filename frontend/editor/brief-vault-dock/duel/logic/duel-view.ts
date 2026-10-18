// Čistý pohled na duel Schránky (docs/schranka-duel.md): tvary odpovědí GET /api/brief-vault/duel a /vision,
// procenta, prahy 40 % / 75 %, slovní stav trendu představy, řazení výměn, „Na tahu“, kola a rozpad příspěvků.
// Výpočet P (nekalibrovaná síla argumentů pro B, ne pravděpodobnost) a trendu dělá server; tady se jen čte a formátuje. Bez Reactu (test vedle).

export type DuelSide = "A" | "B" | "human" | "judge";
export type TurnKind = "claim" | "grill" | "answer" | "concede" | "synthesis" | "note";
export type DuelStatus = "open" | "grill" | "synthesis" | "decided";
export type Outcome = "keep" | "adopt" | "synthesis";
export type TrendState = "approaching" | "receding" | "unclear" | "insufficient";

export type DuelTurn = { id: string; side: DuelSide; kind: TurnKind; text: string; refs?: string[];
  evidence?: { source: string; quote?: string }[]; by?: string; actor?: string; at?: string };
export type DuelScore = { turnId: string; judge?: string; strength: number; supports: "A" | "B"; rebuttedBy?: string | null };
/** `applied` / `appliedRevision` / `reason`: zda server nový směr uplatnil do zadání (chybí = neznámo, nic se nepíše). */
export type DuelDecision = { outcome: Outcome; text?: string; p?: number; by?: string; actor?: string; at?: string; override?: { reason: string; ruleOutcome: Outcome | null } | null;
  applied?: boolean; appliedRevision?: number; reason?: string };
export type Duel = {
  fragment: { id: string; revision: number; title?: string };
  subject: { kind: "fragment" | "node" | "project"; id: string };
  incumbent: { text: string; ref?: { fragmentId: string; revision: number } | null };
  challenger: { text: string; by?: string; actor?: string };
  turns: DuelTurn[];
  scores: DuelScore[];
  status: DuelStatus;
  decision: DuelDecision | null;
};
export type Contribution = { turnId: string; side: "A" | "B"; kind: string; strength: number; weight: number; delta: number; reason: string };
export type Probability = { p: number; logit: number; n: number; contributions: Contribution[] };
export type Trajectory = { p: number | null; slope: number | null; se: number | null; n: number; last: number | null; state: TrendState };
export type DuelResponse = { duel: Duel; probability: Probability; onTurn: { side: DuelSide; grillId?: string | null }[];
  rounds: { A: number; B: number }; canDecide: boolean; trajectory: Trajectory | null };
export type Vision = { id: string; revision: number; text: string; title?: string; points?: unknown[] };
/** Odpověď zápisu duelu (POST /api/brief-vault): turn/score nesou odvozený stav, decide rozhodnutí a poučení. */
export type DuelWrite = { fragment?: { id: string; revision: number; title?: string }; duel?: Omit<Duel, "fragment">;
  probability?: Probability; onTurn?: DuelResponse["onTurn"]; rounds?: DuelResponse["rounds"]; canDecide?: boolean;
  decision?: DuelDecision; lesson?: { lesson?: string; kind?: string } | null; lessonSkipped?: string };
export type VisionResponse = { vision: Vision | null; trajectory: Trajectory | null };

/** Mez kol na stranu (§2). */
export const MAX_ROUNDS = 4;
/** Prahy rozhodnutí (§3.2): ≤ 40 % keep, ≥ 75 % (a n ≥ 3) adopt. */
export const KEEP_AT = 0.4;
export const ADOPT_AT = 0.75;

/** P není pravděpodobnost: heuristika ze skóre soudců bez kalibrace na skutečné výsledky (docs/schranka-duel.md §3). */
export const STRENGTH_LABEL = "Síla argumentů pro B (nekalibrovaná)";
export const STRENGTH_HINT = "Heuristika ze skóre soudců – není pravděpodobnost ani ověření výsledku.";

const fmt = (value: number, digits: number) => value.toLocaleString("cs-CZ", { minimumFractionDigits: digits, maximumFractionDigits: digits });

/** „62 %“ (nezlomitelná mezera); neznámé = „—“. */
export function percent(p: number | null | undefined): string {
  return typeof p === "number" && Number.isFinite(p) ? `${Math.round(Math.min(1, Math.max(0, p)) * 100)} %` : "—";
}

/** Znaménkové číslo „+0,42“ / „−0,18“ pro rozpad a sklon. */
export function signed(value: number, digits = 2): string {
  const text = fmt(Math.abs(value), digits);
  return value > 0 ? "+" + text : value < 0 ? "−" + text : text;
}

/** Kam P padá vůči prahům: keep ≤ 40 %, adopt ≥ 75 % s n ≥ 3, jinak syntéza. */
export function zoneOf(p: number, n: number): Outcome {
  if (p >= ADOPT_AT && n >= 3) return "adopt";
  if (p <= KEEP_AT) return "keep";
  return "synthesis";
}

export const OUTCOME_LABEL: Record<Outcome, string> = { keep: "zůstává A", adopt: "platí B", synthesis: "syntéza" };
export const STATUS_LABEL: Record<DuelStatus, string> = { open: "otevřený", grill: "výměny", synthesis: "syntéza", decided: "rozhodnutý" };
export const KIND_LABEL: Record<TurnKind, string> = { claim: "argument", grill: "otázka", answer: "odpověď", concede: "uznání", synthesis: "syntéza", note: "poznámka" };
export const SIDE_LABEL: Record<DuelSide, string> = { A: "A", B: "B", human: "člověk", judge: "soudce" };
const TREND_LABEL: Record<TrendState, string> = { approaching: "přibližujeme se", receding: "oddalujeme se", unclear: "nejasné", insufficient: "málo dat" };

export const statusLabel = (status: string | undefined): string => STATUS_LABEL[status as DuelStatus] ?? (status || "—");
export const trendLabel = (state: string | undefined): string => TREND_LABEL[state as TrendState] ?? "málo dat";

/** Řádek trendu představy: „přibližujeme se · P 72 % · sklon +0,40 · n 5 · poslední 7,5“. */
export function trendLine(trajectory: Trajectory | null | undefined): string {
  if (!trajectory) return "Trend představy: málo dat.";
  const parts = ["Trend představy: " + trendLabel(trajectory.state)];
  if (trajectory.state !== "insufficient" && trajectory.p != null) parts.push("P " + percent(trajectory.p));
  if (trajectory.slope != null) parts.push("sklon " + signed(trajectory.slope));
  parts.push("n " + trajectory.n);
  if (trajectory.last != null) parts.push("poslední " + fmt(trajectory.last, 1));
  return parts.join(" · ");
}

/** Výměny v čase (nejstarší nahoře); stejný čas nechá pořadí serveru. */
export function sortTurns(turns: DuelTurn[]): DuelTurn[] {
  return turns.map((turn, index) => ({ turn, index }))
    .sort((a, b) => (a.turn.at ?? "").localeCompare(b.turn.at ?? "") || a.index - b.index)
    .map((item) => item.turn);
}

/** Krátká čísla výměn: #1, #2, … podle pořadí v `duel.turns` (server výměny jen přidává, takže číslo je stabilní). */
export function turnNumbers(turns: DuelTurn[]): Map<string, number> {
  return new Map(turns.map((turn, index) => [turn.id, index + 1]));
}

/** „#3“ pro známou výměnu; neznámé id zkráceně (celé jde do title). */
export function turnRef(numbers: Map<string, number>, id: string): string {
  const number = numbers.get(id);
  return number ? `#${number}` : `#${id.length > 8 ? id.slice(0, 6) + "…" : id}`;
}

/** Co má kdo udělat, prakticky s tím, co napsat: „Na tahu B: odpověz na #3 – napiš: odpověď #3: …“.
 * Když lze rozhodnout, přidá „Lze rozhodnout – napiš: rozhodni“. Rozhodnutý duel nemá nikoho na tahu. */
export function onTurnLines(onTurn: DuelResponse["onTurn"], status: string, numbers: Map<string, number>, canDecide = false): string[] {
  if (status === "decided") return ["Rozhodnuto, nikdo není na tahu."];
  const lines = !onTurn.length ? ["Na tahu kdokoli – napiš: A: <argument> nebo B: <argument>"]
    : onTurn.map((item) => {
      const side = SIDE_LABEL[item.side] ?? item.side;
      if (!item.grillId) return item.side === "A" || item.side === "B" ? `Na tahu ${side} – napiš: ${side}: <argument>` : `Na tahu ${side}`;
      const ref = turnRef(numbers, item.grillId);
      return `Na tahu ${side}: odpověz na ${ref} – napiš: odpověď ${ref}: …`;
    });
  if (canDecide) lines.push("Lze rozhodnout – napiš: rozhodni");
  return lines;
}

export const roundsLabel = (rounds: { A: number; B: number }): string => `Kola: A ${rounds.A}/${MAX_ROUNDS} · B ${rounds.B}/${MAX_ROUNDS}`;

/** Hodnocení soudců u výměny: průměr síly a kolik soudců. */
export function scoresOf(scores: DuelScore[], turnId: string): { mean: number; count: number; supports: string } | null {
  const own = scores.filter((score) => score.turnId === turnId);
  if (!own.length) return null;
  const mean = own.reduce((sum, score) => sum + score.strength, 0) / own.length;
  const sides = [...new Set(own.map((score) => score.supports))].join("/");
  return { mean, count: own.length, supports: sides };
}

export const scoreLine = (score: ReturnType<typeof scoresOf>): string =>
  score ? `skóre ${fmt(score.mean, 1)}/10 pro ${score.supports} · ${score.count} ${score.count === 1 ? "soudce" : "soudců"}` : "";

/** Rozpad příspěvků: největší vliv nahoře, aby šlo výsledek obhájit. */
export function contributionRows(contributions: Contribution[]): (Contribution & { deltaText: string })[] {
  return contributions.slice().sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
    .map((item) => ({ ...item, deltaText: signed(item.delta) }));
}

/** Za koho člověk v duelu mluví: strana jeho poslední výměny A/B (jinak nikoho). */
export function humanSide(turns: DuelTurn[]): "A" | "B" | null {
  for (let index = turns.length - 1; index >= 0; index--) {
    const turn = turns[index];
    if (turn.actor === "human" && (turn.side === "A" || turn.side === "B")) return turn.side;
  }
  return null;
}

/** Shrnutí duelu pro seznam (ze stromu nebo z GET duel). */
export type DuelItem = { id: string; title: string; status: string; p: number | null; open: boolean };

/** Seznam duelů: otevřené nahoře, jinak pořadí stromu. */
export function sortDuelItems(items: DuelItem[]): DuelItem[] {
  return items.slice().sort((a, b) => Number(b.open) - Number(a.open));
}

/** Okamžitá obnova z odpovědi zápisu (bez čekání na poll): nové pole přepíše staré, fragment (revize) se sloučí. */
export function applyWrite(prev: DuelResponse, write: DuelWrite): DuelResponse {
  if (!write.duel) return prev;
  const decided = write.duel.status === "decided";
  return {
    ...prev,
    duel: { ...write.duel, fragment: { ...prev.duel.fragment, ...(write.fragment ?? {}) },
      // Rozhodnutí z odpovědi decide (s `applied`) doplní to ve stavu duelu.
      decision: write.decision ? { ...(write.duel.decision ?? {}), ...write.decision } : write.duel.decision ?? null },
    probability: write.probability ?? prev.probability,
    onTurn: write.onTurn ?? (decided ? [] : prev.onTurn),
    rounds: write.rounds ?? prev.rounds,
    canDecide: write.canDecide ?? (decided ? false : prev.canDecide),
  };
}

/** Výsledek jednou větou. „platí od teď“ jen při `applied === true`; `applied === false` ukáže jen důvod serveru
 * doslova (ne „platí dál A“: předmět mohl mezitím změnit někdo jiný); karta (`subject.kind === "node"`) se sama
 * nemění, věta řekne, podle čeho ji upravit; bez `applied` (starší data) „stav uplatnění neznámý“. */
export function outcomeLine(decision: DuelDecision, challenger?: string, subjectKind?: string): string {
  if (decision.outcome === "keep") return "Zůstává A";
  const adopt = decision.outcome === "adopt";
  if (!adopt && decision.outcome !== "synthesis") return "Rozhodnuto: " + decision.outcome;
  const text = adopt ? decision.text || challenger || "" : decision.text ?? "";
  const won = adopt ? "Vyhrál nový směr (B)" : "Syntéza vyhrála";
  if (subjectKind === "node") return `${won} – karta se automaticky nemění; uprav ji podle: ${text}`;
  if (decision.applied === true) return (adopt ? "Vyhrál nový směr (B)" : "Syntéza") + " – platí od teď: " + text;
  if (decision.applied === false) return `${won}, ale ${adopt ? "neuplatnil" : "neuplatnila"} se` + (decision.reason ? ": " + decision.reason : "");
  return adopt ? "Vyhrál nový směr (B) – stav uplatnění neznámý" : `Syntéza: ${text} – stav uplatnění neznámý`;
}

/** Druhý řádek jen u skutečného uplatnění; důvod neuplatnění už nese `outcomeLine`, neopakuje se. */
export function appliedLine(decision: DuelDecision, subjectKind?: string): string {
  if (decision.outcome === "keep" || subjectKind === "node") return "";
  return decision.applied === true ? "uplatněno: zadání má nový text" : "";
}

/** Kdo duel vyhrál, bez tvrzení, že to už platí (to říká `outcomeLine`). */
const DECIDED_LABEL: Record<Outcome, string> = { keep: "zůstává A", adopt: "vyhrál B", synthesis: "syntéza" };

/** „Rozhodnuto: vyhrál B při síle B 80 % · přebito člověkem: důvod (pravidlo: syntéza)“. */
export function decisionLine(decision: DuelDecision): string {
  const parts = ["Rozhodnuto: " + (DECIDED_LABEL[decision.outcome] ?? decision.outcome) + (decision.p != null ? ` při síle B ${percent(decision.p)}` : "")];
  if (decision.override) {
    const rule = decision.override.ruleOutcome ? OUTCOME_LABEL[decision.override.ruleOutcome] ?? decision.override.ruleOutcome : "ještě nerozhodlo";
    parts.push(`přebito člověkem: ${decision.override.reason} (pravidlo: ${rule})`);
  }
  return parts.join(" · ");
}

/** Řádek ukazatele síly za „n … hodnocených“. Otevřený duel: „směřuje k: …“ podle zóny P. Rozhodnutý duel: jen pravda
 * z `decision` (výsledek, uplatnění, karta, přebití člověkem), nikdy zóna P – ta může říkat opak. */
export function oddsVerdict(duel: Pick<Duel, "status" | "decision" | "subject">, zone: Outcome): string {
  if (duel.status !== "decided") return "směřuje k: " + OUTCOME_LABEL[zone];
  const decision = duel.decision;
  if (!decision) return "rozhodnuto";
  const overridden = decision.override ? " (přebito člověkem)" : "";
  if (decision.outcome === "keep") return "rozhodnuto: zůstává A" + overridden;
  const adopt = decision.outcome === "adopt";
  if (!adopt && decision.outcome !== "synthesis") return "rozhodnuto: " + decision.outcome + overridden;
  const won = adopt ? "vyhrál B" : "syntéza";
  const state = duel.subject?.kind === "node" ? "karta se automaticky nemění"
    : decision.applied === true ? (adopt ? "uplatněno" : "uplatněna")
    : decision.applied === false ? (adopt ? "neuplatněno" : "neuplatněna")
    : "stav uplatnění neznámý";
  return `rozhodnuto: ${won}, ${state}${overridden}`;
}

/** Věta o poučení po rozhodnutí; jiný zápis = "". */
export function lessonNotice(write: DuelWrite): string {
  if (write.lessonSkipped) return "Poučení přeskočeno (duel bez disciplíny).";
  if (write.lesson) return "Poučení zapsáno" + (write.lesson.lesson ? `: ${write.lesson.lesson}` : ".");
  return "";
}
