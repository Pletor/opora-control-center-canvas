// Drátový tvar `GET /api/oporahub/agent-state` (docs/oporahub-agent-state.md, schemaVersion 1).
// Parser je přísný na to, co UI promítá: neznámá etapa nebo zdraví se nezobrazí jako „v pořádku“.

export const STAGE_IDS = ["plan", "proposal", "acceptance", "claim", "work", "evidence", "review",
  "pull_request", "merge", "plan_writeback"] as const;
export type StageId = typeof STAGE_IDS[number];
export const HEALTHS = ["ok", "waiting", "blocking", "not_connected"] as const;
export type Health = typeof HEALTHS[number];
export type AgentStage = { id: StageId; count: number; health: Health; reason: string };
export type AgentBudget = { remainingAttempts: number | null; remainingRepairRounds: number | null };
export type AgentAction = {
  id: string; verb: string; method: string; path: string; targetId: string | null;
  preconditions: Record<string, unknown>; status: "ready" | "blocked"; blockReason?: string; budget?: AgentBudget;
  /** Akce, která potřebuje pozornost (opakovaný nález → kontrola). */
  attention?: boolean;
};
/** Etapa jedné karty (`cards[]`): kde ve smyčce karta stojí; plátno z ní kreslí odznak. */
export type AgentCardStage = { nodeId: string; stage: StageId; health: Health; reason: string; executionId: string | null };
export type AgentDecision = { id: string; kind: string; targetId: string | null; title: string; actionId: string };
export type AgentGap = { id: string; stage: string; reason: string };
export type AgentHeads = {
  acceptedHead: string | null; acceptedRevision: string | null; graphDigest: string; workingDiffers: boolean;
  contextVersion: string; budgetPolicyHead: Record<string, string>;
};
export type AgentState = {
  schemaVersion: 1; generatedAt: string; projectId: string; workspaceId: string; heads: AgentHeads;
  stages: AgentStage[]; riskMix: { low: number; elevated: number; critical: number };
  decisions: AgentDecision[]; actions: AgentAction[]; gaps: AgentGap[]; truncated: boolean;
  /** Chybí u serveru před vlnou 5; UI pak odznaky na plátně nekreslí. */
  cards?: AgentCardStage[];
};

const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string" && value.length <= 16000;
const nullableText = (value: unknown) => value === null || text(value);
const count = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) >= 0;

function stage(value: unknown): value is AgentStage {
  return object(value) && STAGE_IDS.includes(value.id as StageId) && count(value.count)
    && HEALTHS.includes(value.health as Health) && text(value.reason);
}
function action(value: unknown): value is AgentAction {
  if (!object(value) || !text(value.id) || !text(value.verb) || !text(value.method) || !text(value.path)) return false;
  if (!nullableText(value.targetId) || !object(value.preconditions)) return false;
  if (value.status !== "ready" && value.status !== "blocked") return false;
  if (value.blockReason !== undefined && !text(value.blockReason)) return false;
  if (value.attention !== undefined && typeof value.attention !== "boolean") return false;
  return value.budget === undefined || (object(value.budget)
    && (value.budget.remainingAttempts === null || count(value.budget.remainingAttempts))
    && (value.budget.remainingRepairRounds === null || count(value.budget.remainingRepairRounds)));
}
const decision = (value: unknown): value is AgentDecision => object(value) && text(value.id) && text(value.kind)
  && nullableText(value.targetId) && text(value.title) && text(value.actionId);
const cardStage = (value: unknown): value is AgentCardStage => object(value) && text(value.nodeId)
  && STAGE_IDS.includes(value.stage as StageId) && HEALTHS.includes(value.health as Health) && text(value.reason)
  && nullableText(value.executionId);
const gap = (value: unknown): value is AgentGap => object(value) && text(value.id) && text(value.stage) && text(value.reason);

/** Ověří tvar a rozsah; dokument jiného projektu nebo prostoru se nikdy nezobrazí. */
export function parseAgentState(raw: unknown, project: string, workspace: string): AgentState {
  if (!object(raw) || raw.schemaVersion !== 1) throw new Error("Stav pro agenty má nepodporovanou verzi schématu.");
  if (raw.projectId !== project || raw.workspaceId !== workspace) throw new Error("Stav pro agenty patří jinému prostoru.");
  const heads = raw.heads, risk = raw.riskMix;
  if (!object(heads) || !nullableText(heads.acceptedHead) || !text(heads.graphDigest) || typeof heads.workingDiffers !== "boolean"
    || !text(heads.contextVersion) || !object(heads.budgetPolicyHead) || !Object.values(heads.budgetPolicyHead).every(text))
    throw new Error("Stav pro agenty nemá platné hlavy.");
  if (!object(risk) || ![risk.low, risk.elevated, risk.critical].every(count)) throw new Error("Stav pro agenty nemá platný mix rizika.");
  const stages = raw.stages, actions = raw.actions, decisions = raw.decisions, gaps = raw.gaps;
  if (!Array.isArray(stages) || !stages.every(stage) || stages.map(item => item.id).join() !== STAGE_IDS.join())
    throw new Error("Stav pro agenty nemá úplnou smyčku etap.");
  if (!Array.isArray(actions) || !actions.every(action)) throw new Error("Stav pro agenty má neplatné akce.");
  if (!Array.isArray(decisions) || !decisions.every(decision) || decisions.length > 3) throw new Error("Stav pro agenty má neplatná rozhodnutí.");
  if (!Array.isArray(gaps) || !gaps.every(gap)) throw new Error("Stav pro agenty má neplatné mezery.");
  if (raw.cards !== undefined && (!Array.isArray(raw.cards) || !raw.cards.every(cardStage))) throw new Error("Stav pro agenty má neplatné etapy karet.");
  if (!text(raw.generatedAt) || typeof raw.truncated !== "boolean") throw new Error("Stav pro agenty je neúplný.");
  return raw as unknown as AgentState;
}

export const agentStateEndpoint = (project: string, workspace: string) =>
  `/api/oporahub/agent-state?${new URLSearchParams({ project, workspace })}`;

export type AgentStateRead = { kind: "unchanged" } | { kind: "fresh"; state: AgentState; etag: string };
type Transport = (input: string, init: RequestInit) => Promise<Response>;

/** Podmíněné čtení: se známým ETagem pošle If-None-Match a 304 znamená „beze změny“. */
export async function readAgentState(project: string, workspace: string, etag: string, signal: AbortSignal,
  transport: Transport = (input, init) => fetch(input, init)): Promise<AgentStateRead> {
  const headers: Record<string, string> = etag ? { "If-None-Match": etag } : {};
  const response = await transport(agentStateEndpoint(project, workspace), { signal, headers, cache: "no-store", redirect: "error" });
  if (response.status === 304 && etag) return { kind: "unchanged" };
  if (!response.ok) throw new Error(`Stav pro agenty není dostupný (HTTP ${response.status}).`);
  const raw = await response.text();
  if (raw.length > 2 * 1024 * 1024) throw new Error("Stav pro agenty překročil povolenou velikost.");
  return { kind: "fresh", state: parseAgentState(JSON.parse(raw), project, workspace), etag: response.headers.get("ETag") ?? "" };
}

/** JSON pro `<script type="application/json">`: `<` se escapuje, aby text nemohl ukončit značku. */
export function mirrorJson(state: AgentState | null) {
  return JSON.stringify(state).replace(/</g, "\\u003c");
}
