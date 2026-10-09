// Kola karty (docs/navrh-schranka-zadani.md, „Kola karty“): uzavřená v1 se zamrazí do historie,
// v2 začíná načisto. Tvary odpovídají GET /api/desktop-v3/card-rounds (backend/editor/agent_memory/card_rounds.py).
// Model jen počítá přepínač kol, nabídku „Otevřít v2“ a výtah zamrazeného kola; nic neukládá.

/** Stav uzlu `round`: aktuální kolo karty (chybí = kolo 1). Mění ho jen otevření kola člověkem. */
export type CardRound = { number: number; openedAt: string; by: string; reason: string };

type Stage = { id?: string; kind: string; lens: string; title: string; status: string; note: string; doneBy?: string };
type Proof = { status: string; url: string; note: string };

/** Zamrazený záznam kola (`opora.card-round/1`), jen pole, která UI ukazuje. */
export type RoundRecord = {
  schema: string;
  nodeId: string;
  round: number;
  openedAt: string;
  openReason: string;
  closedAt: string;
  frozenAt: string;
  brief: { goal: Record<string, string>; text: string; fragments: { fragmentId: string; revision: number; title?: string; text?: string; available: boolean }[] };
  done: { confirmed: boolean; at: string; by: string; note: string } | null;
  pipeline: { profile: string; items: Stage[] } | null;
  blocks: { id: string; number: string; title: string; state: { status: string; note?: string };
    ports?: { id: string; label: string; status?: "chosen" | "rejected"; reason?: string }[] }[];
  /** Kritéria karty v kole (starší záznam je nemá). */
  criteria?: { id: string; text: string; checked: boolean }[];
  /** Rozhodnutí karty (`state.decisions` s nodeId) v okamžiku zamrazení. */
  decisions?: { id: string; text: string; by: string; createdAt: string }[];
  evidence: { tests: Proof; review: Proof; merge: Proof; checksRun: { checkId: string; command: string; exitCode: number }[] } | null;
  ideas: { id: string; text: string; source: string; status: "open" | "done" }[];
  criticFindings: Stage[];
  errors: { failedStages: Stage[]; agentFailures: string; agentFixes: string; handoffErrors: { edgeId: string; errors: string }[] };
  commits: { realization: { commit: string; prUrl: string } | null; merge: Proof | null; touched: string[] };
  agentWorkspace: Record<string, string>;
  agentResults: { id: string; agent: string; createdAt: string; doneProposed: boolean; note: string }[];
  nextBrief?: { round: number; fragments: { fragmentId: string; revision: number; title?: string; text?: string }[] };
};

export type RoundsResponse = { nodeId: string; current: number; round: CardRound | null; rounds: RoundRecord[] };

export function roundNumber(round: CardRound | undefined | null): number {
  return round?.number ?? 1;
}

/** Přepínač kol „v1 ✓ · v2 ●“: minulá kola hotová, aktuální běží (✓, když je uzavřené i ono). */
export type RoundChip = { round: number; label: string; mark: "✓" | "●"; current: boolean };
export function roundChips(current: number, closed: boolean): RoundChip[] {
  return Array.from({ length: Math.max(1, current) }, (_, index) => {
    const round = index + 1;
    const isCurrent = round === current;
    return { round, label: "v" + round, mark: !isCurrent || closed ? "✓" : "●", current: isCurrent };
  });
}

/**
 * Nabídka „Otevřít v2 podle nového zadání“: jen u uzavřené karty v zapisovatelném prostoru.
 * `prominent` = zadání ve schránce se po uzavření změnilo (⚠), jinak jen ruční volba.
 */
export function roundOffer(closed: boolean, readOnly: boolean, briefChanged: number): "prominent" | "manual" | null {
  if (!closed || readOnly) return null;
  return briefChanged > 0 ? "prominent" : "manual";
}

export function openRoundLabel(current: number): string {
  return `Otevřít v${current + 1} podle nového zadání`;
}

const PASSED = new Set(["passed", "skipped"]);

/**
 * Rozhodnutí kola: volby portů bloků, splněná kritéria a rozhodnutí karty. Další kolo je nepřebírá
 * (nové zadání = nové postupy), zůstávají jen tady jako kontext, z čeho karta vznikla.
 */
export function roundDecisions(record: RoundRecord): { kind: "port" | "criterion" | "decision"; text: string }[] {
  const ports = record.blocks.flatMap((block) => (block.ports ?? []).filter((port) => port.status).map((port) => ({
    kind: "port" as const, text: `blok ${block.number}: „${port.label}“ ${port.status === "chosen" ? "zvoleno" : "zamítnuto"}${port.reason ? ` – ${port.reason}` : ""}` })));
  const criteria = (record.criteria ?? []).filter((item) => item.checked).map((item) => ({ kind: "criterion" as const, text: item.text }));
  const decisions = (record.decisions ?? []).map((item) => ({ kind: "decision" as const, text: item.text }));
  return [...ports, ...criteria, ...decisions];
}

/** Výtah kola pro Historii kol: postup, chyby, nálezy, commity a Podněty v číslech i textu. */
export function roundDigest(record: RoundRecord) {
  const stages = record.pipeline?.items ?? [];
  const errors = record.errors ?? { failedStages: [], agentFailures: "", agentFixes: "", handoffErrors: [] };
  const commits = record.commits ?? { realization: null, merge: null, touched: [] };
  return {
    stages: stages.map((stage) => ({ ...stage, ok: PASSED.has(stage.status) })),
    stagesPassed: stages.filter((stage) => PASSED.has(stage.status)).length,
    blocksMet: record.blocks.filter((block) => block.state.status === "met").length,
    blocks: record.blocks.length,
    evidence: record.evidence ? (["tests", "review", "merge"] as const).map((key) => ({ key, ...record.evidence![key] })) : [],
    findings: record.criticFindings ?? [],
    errorCount: errors.failedStages.length + errors.handoffErrors.length + (errors.agentFailures.trim() ? 1 : 0),
    errors,
    commit: commits.realization?.commit || "",
    prUrl: commits.realization?.prUrl || commits.merge?.url || "",
    touched: commits.touched ?? [],
    ideasOpen: record.ideas.filter((idea) => idea.status === "open").length,
    ideasDone: record.ideas.filter((idea) => idea.status === "done").length,
    results: record.agentResults ?? [],
    decided: roundDecisions(record),
  };
}

/**
 * Kolo, ve kterém rozhodnutí karty vzniklo: nejstarší zamrazené kolo, které ho drží (stejně jako
 * `context.decisions[].fromRound` v node-brief, `card_rounds.mark_decisions`). Nové rozhodnutí aktuálního kola chybí.
 */
export function decisionRounds(records: RoundRecord[]): Map<string, number> {
  const origin = new Map<string, number>();
  for (const record of [...records].sort((a, b) => a.round - b.round)) {
    for (const item of record.decisions ?? []) if (!origin.has(item.id)) origin.set(item.id, record.round);
  }
  return origin;
}

/** Štítek původu rozhodnutí „z v1“ (obecně „z vN“); rozhodnutí aktuálního kola štítek nemá. */
export function fromRoundLabel(round: number | undefined): string {
  return round ? `z v${round}` : "";
}

/** Karty, jejichž rozhodnutí mohou pocházet z dřívějšího kola: mají rozhodnutí a běží v kole ≥ 2. */
export function cardsWithRoundDecisions(decisions: { nodeId: string }[], nodes: Record<string, { round?: CardRound }>): string[] {
  const ids = new Set(decisions.map((item) => item.nodeId).filter((id) => id && roundNumber(nodes[id]?.round) >= 2));
  return [...ids].sort();
}
