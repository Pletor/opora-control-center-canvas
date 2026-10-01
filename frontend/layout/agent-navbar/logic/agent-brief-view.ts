// Pohled na balíček pro model (`GET /api/desktop-v3/node-brief`, viz `docs/karta-pro-agenty.md`)
// přeložený do toho, co se vejde do police široké 20rem. Balíček drží backend a frontend ho jen
// čte: proto je tady všechno defenzivní — chybějící klíč, `null`, cizí typ i prázdné pole dávají
// prázdnou, ale platnou hodnotu, nikdy výjimku. Modul nic nenačítá (to dělá `use-node-brief.ts`)
// a nic nemění; je to čisté mapování JSON → věty, které člověk v panelu čte.

/** Balíček je cizí JSON: tvar drží server, tady se z něj jen bezpečně čte. */
type Unknown = Record<string, unknown>;

const record = (value: unknown): Unknown =>
  value && typeof value === "object" && !Array.isArray(value) ? (value as Unknown) : {};
const list = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
const text = (value: unknown): string => (typeof value === "string" ? value : "");
const count = (value: unknown): number => (typeof value === "number" && Number.isFinite(value) ? value : 0);
const flag = (value: unknown): boolean => value === true;

/** Karta bez názvu se pozná podle výplně, ne podle prázdného místa — prázdný řádek by se ztratil. */
export const UNNAMED = "(bez názvu)";

/** Kolik znaků z pracovního prostoru se v panelu ukáže; zbytek si člověk otevře v inspektoru. */
export const SPACE_PREVIEW = 300;

/**
 * První neprázdná řádka textu. Předávka souseda je dlouhý zápisník; v seznamu vazeb je místo
 * na jednu větu, a tou první větou agent svoji předávku vždycky začíná.
 */
export function firstLine(value: unknown): string {
  for (const line of text(value).split("\n")) {
    const trimmed = line.trim();
    if (trimmed) return trimmed;
  }
  return "";
}

/** Ořez na `limit` znaků s výpustkou. Ukázka má naznačit tón textu, ne ho nahradit. */
export function truncate(value: unknown, limit: number = SPACE_PREVIEW): string {
  const trimmed = text(value).trim();
  return trimmed.length > limit ? trimmed.slice(0, limit) + "…" : trimmed;
}

/** Stejný slovník fází jako v panelu workflow (`editor/workflow`), aby fáze měla v aplikaci jedno jméno. */
const PHASE_LABEL: Record<string, string> = {
  discover: "Objev",
  define: "Definice",
  build: "Build",
  verify: "Ověření",
  live: "Live",
};

/** Druh karty česky; neznámý druh si ponechá své id, aby se nic neztratilo. */
const KIND_LABEL: Record<string, string> = {
  node: "uzel",
  sector: "sektor",
  area: "oblast",
  comment: "komentář",
};

export const phaseLabel = (phase: string): string => PHASE_LABEL[phase] ?? phase;
export const kindLabel = (kind: string): string => KIND_LABEL[kind] ?? kind;

export type BriefParam = { key: string; value: string };
export type BriefAction = { id: string; label: string; pipelineId: string; params: BriefParam[] };
export type BriefStep = { id: string; text: string; done: boolean };
export type BriefCriterion = { id: string; text: string; checked: boolean };
/** Soused na vazbě nebo rodič: jméno a jedna věta jeho předávky. */
export type BriefNeighbour = { id: string; name: string; handoff: string };

export type BriefSummary = {
  header: {
    name: string;
    kind: string;
    kindLabel: string;
    phase: string;
    phaseLabel: string;
    done: boolean;
    doneNote: string;
  };
  goal: { goal: string; criteria: BriefCriterion[]; stopConditions: string[] };
  harness: { actions: BriefAction[]; steps: BriefStep[] };
  loop: { openBlocks: number; lastReport: string };
  handoffs: {
    incoming: BriefNeighbour[];
    outgoing: BriefNeighbour[];
    parent: BriefNeighbour | null;
    children: number;
  };
  workspace: { frame: string; handoff: string };
};

const params = (value: unknown): BriefParam[] =>
  Object.entries(record(value)).map(([key, item]) => ({ key, value: typeof item === "string" ? item : String(item) }));

const actions = (value: unknown): BriefAction[] =>
  list(value).map((raw) => {
    const action = record(raw);
    return {
      id: text(action.id),
      label: text(action.label) || text(action.pipelineId) || UNNAMED,
      pipelineId: text(action.pipelineId),
      params: params(action.params),
    };
  });

const steps = (value: unknown): BriefStep[] =>
  list(value).map((raw) => {
    const step = record(raw);
    return { id: text(step.id), text: text(step.text), done: flag(step.done) };
  });

const criteria = (value: unknown): BriefCriterion[] =>
  list(value).map((raw) => {
    const criterion = record(raw);
    return { id: text(criterion.id), text: text(criterion.text), checked: flag(criterion.checked) };
  });

/** Texty stop podmínek; balíček je vydává jako pole řetězců, prázdné se zahodí. */
const stopConditions = (value: unknown): string[] =>
  list(value)
    .map((raw) => text(raw).trim())
    .filter((item) => item !== "");

/**
 * Sousedé na vazbách. Balíček nese u příchozí vazby `from`/`fromName`, u odchozí `to`/`toName`;
 * jméno je to, co člověk v panelu hledá, id zbývá jako záchrana, když jméno chybí.
 */
const neighbours = (value: unknown, idKey: "from" | "to", nameKey: "fromName" | "toName"): BriefNeighbour[] =>
  list(value).map((raw) => {
    const edge = record(raw);
    const id = text(edge[idKey]);
    return {
      id,
      name: text(edge[nameKey]) || id || UNNAMED,
      handoff: firstLine(record(edge.agentWorkspace).handoff),
    };
  });

const parentOf = (value: unknown): BriefNeighbour | null => {
  if (!value || typeof value !== "object") return null;
  const parent = record(value);
  const id = text(parent.id);
  if (!id) return null;
  return { id, name: text(parent.name) || UNNAMED, handoff: firstLine(record(parent.agentWorkspace).handoff) };
};

/**
 * Celý pohled jedním voláním: hlavička (kdo jsem, v jaké fázi, jestli je hotovo), cíl a konec,
 * harness (akce a kroky), smyčka (co zbývá, co přišlo naposled), předávky sousedů a vlastní
 * pracovní prostor. Prázdný nebo rozbitý balíček dá prázdný pohled — panel pak ukáže prázdné
 * sekce, ne chybu, protože nevyplněná karta je běžný stav, ne porucha.
 */
export function briefSummary(brief: unknown): BriefSummary {
  const data = record(brief);
  const node = record(data.node);
  const harness = record(data.harness);
  const loop = record(data.loop);
  const done = record(loop.done);
  const graph = record(data.graph);
  const space = record(data.agentWorkspace);
  const report = record(loop.lastReport);
  const kind = text(node.kind);
  const phase = text(harness.phase);
  return {
    header: {
      name: text(node.name) || UNNAMED,
      kind,
      kindLabel: kindLabel(kind),
      phase,
      phaseLabel: phaseLabel(phase),
      done: flag(done.confirmed),
      doneNote: text(done.note).trim(),
    },
    goal: {
      goal: text(record(data.goal).goal).trim(),
      criteria: criteria(record(data.definitionOfDone).criteria),
      stopConditions: stopConditions(harness.stopConditions),
    },
    harness: { actions: actions(harness.actions), steps: steps(harness.steps) },
    loop: {
      openBlocks: count(loop.openBlocks),
      lastReport: truncate(text(report.summary) || text(report.handoff)),
    },
    handoffs: {
      incoming: neighbours(graph.incoming, "from", "fromName"),
      outgoing: neighbours(graph.outgoing, "to", "toName"),
      parent: parentOf(graph.parent),
      children: list(graph.children).length,
    },
    workspace: { frame: truncate(space.frame), handoff: truncate(space.handoff) },
  };
}

/** Odkaz na předávku karty; stejný tvar jako `sectionLink` v inspektoru (`opora://agent-workspace/<id>#<sekce>`). */
export const handoffLink = (nodeId: string): string => `opora://agent-workspace/${nodeId}#handoff`;

/** Celý balíček jako text do schránky: člověk ho vloží agentovi. Odsazení dvěma mezerami jako všude jinde. */
export const briefJson = (brief: unknown): string => JSON.stringify(brief ?? null, null, 2);
