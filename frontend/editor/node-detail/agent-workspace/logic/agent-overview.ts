// Přehled nad pracovním prostorem: jeden krátký pohled, ze kterého nový agent hned pozná, kde
// stojí — kolik z pěti polí paměti je napsaných, co v komunikaci čeká na jeho odpověď, jestli má
// karta cíl a definici hotovo, jaký je doporučený další krok a proč je případně zápis zamčený.
// Modul je čistý: čte jen právě načtený node-brief (`orientation`, `communication`) a záznam
// prostoru, nic nenačítá, nic neukládá a nic nedomýšlí. Chybějící údaj je přiznaná mezera, ne nula.
import { SECTIONS, type AgentWorkspaceRecord, type SectionKey } from "@/editor/node-detail/agent-workspace/logic/agent-workspace";

type UnknownRecord = Record<string, unknown>;
const record = (value: unknown): UnknownRecord =>
  value !== null && typeof value === "object" && !Array.isArray(value) ? (value as UnknownRecord) : {};
const list = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
const text = (value: unknown): string => (typeof value === "string" ? value : "");
/** Boolean z briefu, nebo `null` = brief se k tomu nevyjádřil. Mlčení není záruka. */
const flag = (value: unknown): SafetyFlag => (typeof value === "boolean" ? value : null);

export type WorkState = "empty" | "human" | "agent";
export type Presence = "present" | "missing";
export type SafetyFlag = boolean | null;
export type ReadOnlyReason = null | "closed" | "main";
export type OverviewSafety = { modelInvocation: SafetyFlag; automaticAck: SafetyFlag; ownershipTransfer: SafetyFlag };
export type OverviewModel = {
  path: string[];
  work: { state: WorkState; updatedAt: string; filled: number; total: 5 };
  communication: { available: boolean; awaitingReceipt: number; needsClarification: number; openQuestions: number; hasMore: boolean };
  verification: { goal: Presence; dod: Presence; gaps: number };
  nextAction: { label: string; kind: string };
  safety: OverviewSafety;
  readOnlyReason: ReadOnlyReason;
};

/** Věty k důvodu zámku; jedna přesná místo dosavadní dvojznačné „uzavřená nebo main“. */
export const READ_ONLY_TEXT: Record<"closed" | "main", string> = {
  closed: "Karta je uzavřená: paměť a zprávy jsou jen ke čtení.",
  main: "Main je jen ke čtení; pracuj v pracovním prostoru.",
};

/** Stav komunikace, který backend považuje za funkční; cokoli jiného je výpadek, ne prázdná historie. */
const COMMUNICATION_OK = ["", "present", "ok"];

function communicationOf(brief: UnknownRecord): OverviewModel["communication"] {
  const communication = record(brief.communication);
  const incomingPage = record(communication.incoming);
  const outgoingPage = record(communication.outgoing);
  const available = Object.keys(communication).length > 0 &&
    COMMUNICATION_OK.includes(text(communication.status)) && COMMUNICATION_OK.includes(text(incomingPage.status));
  if (!available) return { available: false, awaitingReceipt: 0, needsClarification: 0, openQuestions: 0, hasMore: false };
  const answered = new Set(list(outgoingPage.messages).map((item) => text(record(item).replyToMessageId)).filter(Boolean));
  let awaitingReceipt = 0;
  let needsClarification = 0;
  let openQuestions = 0;
  for (const item of list(incomingPage.messages)) {
    const message = record(item);
    const receipt = record(message.receipt);
    if (!Object.keys(receipt).length) awaitingReceipt += 1;
    if (text(receipt.disposition) === "needs_clarification") needsClarification += 1;
    if (text(message.kind) === "question" && !answered.has(text(message.id))) openQuestions += 1;
  }
  return {
    available: true, awaitingReceipt, needsClarification, openQuestions,
    hasMore: incomingPage.hasMore === true || outgoingPage.hasMore === true,
  };
}

function workOf(source: AgentWorkspaceRecord | null | undefined): OverviewModel["work"] {
  const space = record(source);
  const filled = SECTIONS.filter(({ key }) => text(space[key]).trim().length > 0).length;
  const by: WorkState = text(space.by) === "agent" ? "agent" : "human";
  return { state: filled === 0 ? "empty" : by, updatedAt: text(space.updatedAt), filled, total: 5 };
}

/** Stav z briefu má přednost; když ho brief neuvádí, rozhodne skutečný obsah, ne optimismus. */
function presenceOf(source: UnknownRecord, hasContent: boolean): Presence {
  const status = text(source.status);
  if (status) return status === "present" ? "present" : "missing";
  return hasContent ? "present" : "missing";
}

/**
 * Jeden model pro horní pás záložky Agenti. `closed` a `mainReadOnly` dává rodič
 * (viz `briefReadOnlyFlags`), protože jen on ví, co karta i pohled skutečně dovolují.
 */
export function overviewModel(
  value: unknown,
  workspaceRecord: AgentWorkspaceRecord | null | undefined,
  { closed, mainReadOnly }: { closed: boolean; mainReadOnly: boolean },
): OverviewModel {
  const brief = record(value);
  const orientation = record(brief.orientation);
  const goal = record(orientation.goal);
  const dod = record(orientation.definitionOfDone);
  const nextAction = record(orientation.nextAction);
  const safety = record(orientation.safety);
  return {
    path: list(record(orientation.scope).path).map(text),
    work: workOf(workspaceRecord),
    communication: communicationOf(brief),
    verification: {
      goal: presenceOf(goal, text(goal.goal).trim().length > 0),
      dod: presenceOf(dod, text(dod.acceptance).trim().length > 0 || list(dod.blockConditions).length > 0),
      gaps: list(orientation.contextGaps).length,
    },
    nextAction: { label: text(nextAction.label), kind: text(nextAction.kind) },
    safety: {
      modelInvocation: flag(safety.automaticModelInvocation),
      automaticAck: flag(safety.automaticAck),
      ownershipTransfer: flag(safety.ownershipTransfer),
    },
    readOnlyReason: closed ? "closed" : mainReadOnly ? "main" : null,
  };
}

/** Autoritativní důvod zámku: uzavřená karta (`loop.done.confirmed`) a main bez zápisu (`readOnly`). */
export function briefReadOnlyFlags(value: unknown): { closed: boolean; mainReadOnly: boolean } {
  const brief = record(value);
  return { closed: record(record(brief.loop).done).confirmed === true, mainReadOnly: brief.readOnly === true };
}

const SAFETY_WORDS: { key: keyof OverviewSafety; negative: string; positive: string; name: string }[] = [
  { key: "modelInvocation", negative: "model nespouští", positive: "model spouští", name: "spouštění modelu" },
  { key: "automaticAck", negative: "převzetí nepotvrzuje automaticky", positive: "převzetí potvrzuje automaticky", name: "automatické potvrzení převzetí" },
  { key: "ownershipTransfer", negative: "vlastnictví nepřevádí", positive: "vlastnictví převádí", name: "převod vlastnictví" },
];

/** Jedna věta o zárukách: zaručené jen tam, kde brief říká false; mlčení se přizná jako „neuvedeno“. */
export function safetyLine(safety: OverviewSafety): string {
  const guaranteed: string[] = [];
  const reported: string[] = [];
  const unknown: string[] = [];
  for (const word of SAFETY_WORDS) {
    const value = safety[word.key];
    if (value === false) guaranteed.push(word.negative);
    else if (value === true) reported.push(word.positive);
    else unknown.push(word.name);
  }
  const sentences: string[] = [];
  if (guaranteed.length) sentences.push(`Aplikace ${guaranteed.join(", ")}.`);
  if (reported.length) sentences.push(`Brief hlásí: ${reported.join(", ")}.`);
  if (unknown.length) sentences.push(`Neuvedeno: ${unknown.join(", ")}.`);
  return sentences.join(" ");
}

/** Popisek u složené sekce: prázdné pole se přizná, vyplněné ukáže délku bez otevírání. */
export function sectionIndicator(value: string): string {
  const length = value.length;
  if (!value.trim()) return "prázdné";
  if (length === 1) return "1 znak";
  return `${length} ${length < 5 ? "znaky" : "znaků"}`;
}

/** Které z pěti sekcí se otevřou samy: ty, které už něco nesou. Prázdné zůstávají složené. */
export function sectionsOpenByDefault(source: AgentWorkspaceRecord | null | undefined): Record<SectionKey, boolean> {
  const space = record(source);
  const open = {} as Record<SectionKey, boolean>;
  for (const { key } of SECTIONS) open[key] = text(space[key]).trim().length > 0;
  return open;
}
