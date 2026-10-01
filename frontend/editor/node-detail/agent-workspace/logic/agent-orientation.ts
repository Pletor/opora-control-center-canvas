// Čistý pohled pro start nového agenta. Pracuje pouze s právě načteným node-briefeм;
// nečte soubory ani síť a nemění stav karty nebo komunikace.
type UnknownRecord = Record<string, unknown>;
type SearchHit = { id: string; label: string; source: string };
type ReadingItem = { id: string; label: string; source: string; status: string };
const record = (value: unknown): UnknownRecord => value !== null && typeof value === "object" && !Array.isArray(value) ? value as UnknownRecord : {};
const list = (value: unknown): unknown[] => Array.isArray(value) ? value : [];
const text = (value: unknown): string => typeof value === "string" ? value : "";
const indexed = (value: unknown, needle: string): boolean => {
  const serialized = JSON.stringify(value);
  return typeof serialized === "string" && serialized.toLocaleLowerCase("cs-CZ").includes(needle);
};

export type OrientationSummary = { goal: string; reading: ReadingItem[]; gaps: { id: string; label: string; instruction: string }[]; optionalContext: { id: string; label: string; instruction: string }[]; nextAction: string; readOnly: boolean; path: string[]; definitionOfDone: UnknownRecord; boundaries: UnknownRecord; available: boolean };

/** Krátké údaje do čtyř karet; chybějící hodnota je přiznaná prázdným stavem, ne domyšlená. */
export function orientationSummary(value: unknown): OrientationSummary {
  const brief = record(value); const orientation = record(brief.orientation);
  if (!Object.keys(orientation).length) return { goal: "", reading: [], gaps: [], optionalContext: [], nextAction: "", readOnly: false, path: [], definitionOfDone: {}, boundaries: {}, available: false };
  const scope = record(orientation.scope); const goal = record(orientation.goal);
  const gapsOf = (source: unknown) => list(source).map((item) => { const gap = record(item); return { id: text(gap.id), label: text(gap.label), instruction: text(gap.instruction) }; });
  return {
    goal: text(goal.goal), reading: list(orientation.readingOrder).map((item) => { const entry = record(item); return { id: text(entry.id), label: text(entry.label), source: text(entry.source), status: text(entry.status) }; }),
    gaps: gapsOf(orientation.contextGaps), optionalContext: gapsOf(orientation.optionalContext), nextAction: text(record(orientation.nextAction).label), readOnly: scope.readOnly === true,
    path: list(scope.path).map(text), definitionOfDone: record(orientation.definitionOfDone), boundaries: record(orientation.boundaries), available: true,
  };
}

/** Lokální vyhledávání v načtených podkladech, zprávách, cíli, pravidlech, workspace a blocích. */
export function orientationSearch(value: unknown, query: string): SearchHit[] {
  const needle = query.trim().toLocaleLowerCase("cs-CZ"); if (!needle) return [];
  const brief = record(value); const orientation = record(brief.orientation); const hits: SearchHit[] = [];
  for (const item of list(orientation.materials)) { const material = record(item); const label = text(material.caption) || text(material.path); if (indexed(material, needle)) hits.push({ id: `material:${text(material.id)}`, label, source: `Podklad · ${text(material.sourceNodeId)}` }); }
  const communication = record(brief.communication);
  for (const direction of ["incoming", "outgoing"] as const) for (const item of list(record(communication[direction]).messages)) { const message = record(item); if (indexed(message, needle)) hits.push({ id: `message:${text(message.id)}`, label: text(message.body), source: `${direction === "incoming" ? "Příchozí" : "Odchozí"} zpráva · ${text(message.senderLabel)}` }); }
  const fields: [string, string, unknown][] = [["goal", "Cíl", brief.goal], ["boundaries", "Hranice a pravidla", brief.boundaries], ["workspace", "Pracovní paměť", brief.agentWorkspace]];
  for (const [id, source, content] of fields) if (indexed(content, needle)) hits.push({ id, label: text(record(content).goal) || source, source });
  for (const item of list(brief.blocks)) {
    const block = record(item);
    if (!indexed(block, needle)) continue;
    const number = text(block.number); const title = text(block.title);
    hits.push({ id: `block:${text(block.id)}`, label: [number, title].filter(Boolean).join(" · ") || "Blok", source: number ? `Blok ${number}` : "Blok" });
  }
  return hits;
}
