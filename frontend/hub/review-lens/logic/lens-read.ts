import { isObject, scopeQuery } from "@/hub/oporahub-mirror/logic/hub-read";

// Čtení `GET /api/oporahub/review-lens` (docs/oporahub-review-jobs.md, „Diagram PR Lens“): nejnovější
// lens PR karty a nejnovější mapa oblasti z plánu. Spec píše agent, proto je to nedůvěryhodná data:
// tady se jen ověří obálka; obsah grafu ověří schéma PR Lens až v líně načteném plátně.
export type LensKind = "pr" | "area";
export type LensRecord = {
  kind: LensKind; headSha: string | null; prNumber: number | null; repository: string; validatedAt: string;
  current: boolean | null; createdAt: string; by: string; acceptedRevision: string | null; spec: Record<string, unknown> | null;
};
export type LensRead = { nodeId: string; pr: LensRecord | null; area: LensRecord | null };
export type LensSummary = { kind: LensKind; headSha: string | null; nodes: number; edges: number };

const SHA = /^[0-9a-f]{40}$/;
const text = (value: unknown, max = 200) => typeof value === "string" && value.length <= max ? value : "";

export const lensUrl = (project: string, workspace: string, nodeId: string) =>
  `/api/oporahub/review-lens?${scopeQuery({ project, workspace, nodeId })}`;

function record(kind: LensKind, lens: unknown, outer: Record<string, unknown>): LensRecord | null {
  if (!isObject(lens)) return null;
  const head = kind === "pr" && typeof lens.headSha === "string" && SHA.test(lens.headSha) ? lens.headSha : null;
  if (kind === "pr" && !head) return null;
  return {
    kind, headSha: head, prNumber: kind === "pr" && Number.isSafeInteger(lens.prNumber) ? lens.prNumber as number : null,
    repository: text(outer.repository), validatedAt: text(lens.validatedAt, 40), createdAt: text(outer.createdAt, 40), by: text(outer.by),
    current: typeof outer.current === "boolean" ? outer.current : null, acceptedRevision: text(outer.acceptedRevision) || null,
    spec: isObject(lens.spec) && lens.spec.kind === "graph" ? lens.spec : null,
  };
}

/** Přísný parser odpovědi; neznámý tvar je chyba, chybějící lens je `null`. */
export function parseLensRead(raw: unknown): LensRead {
  if (!isObject(raw) || typeof raw.nodeId !== "string") throw new Error("Lens karty má neplatný tvar.");
  const area = isObject(raw.area) ? record("area", raw.area.lens, raw.area) : null;
  return { nodeId: raw.nodeId, pr: record("pr", raw.lens, raw), area };
}

/** Co člověk uvidí: graf změny PR, dokud ho není, mapa oblasti z plánu. */
export function shownLens(read: LensRead | null): LensRecord | null {
  if (!read) return null;
  return read.pr?.spec ? read.pr : read.area?.spec ? read.area : read.pr;
}

const count = (value: unknown) => Array.isArray(value) ? value.length : 0;

/** Souhrn do zrcadla detailu karty: agent v prohlížeči hned ví, ke které hlavě spec patří. */
export function lensSummary(record: LensRecord | null): LensSummary | null {
  if (!record) return null;
  return { kind: record.kind, headSha: record.headSha, nodes: count(record.spec?.nodes), edges: count(record.spec?.edges) };
}

/** Odznak záložky: krátká hlava PR, nebo „plán“, když je jen mapa oblasti před kódem. */
export function lensBadge(read: LensRead | null): string {
  const shown = shownLens(read);
  if (!shown) return "";
  return shown.kind === "area" ? "plán" : (shown.headSha ?? "").slice(0, 7);
}

function plural(value: number, one: string, few: string, many: string) {
  return `${value} ${value === 1 ? one : value >= 2 && value <= 4 ? few : many}`;
}

export const specBytes = (spec: unknown) => new TextEncoder().encode(JSON.stringify(spec ?? null)).length;

/** „spec 7 KB · 10 částí · 9 vazeb“: velikost kanonického JSON a počty karet a hran. */
export function specFacts(spec: Record<string, unknown> | null): string {
  if (!spec) return "bez specu";
  const kb = Math.max(1, Math.round(specBytes(spec) / 1024));
  return `spec ${kb} KB · ${plural(count(spec.nodes), "část", "části", "částí")} · ${plural(count(spec.edges), "vazba", "vazby", "vazeb")}`;
}
