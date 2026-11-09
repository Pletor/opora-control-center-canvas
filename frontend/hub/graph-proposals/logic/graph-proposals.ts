import type { CanvasNode, EdgeCarries, Graph, GraphEdge, SpecFields } from "@/shared/types/logic/types";
import type { PlanDocument } from "@/hub/plan-changes/logic/plan-changes";
import type { GraphChanges } from "./graph-edits";
import type { DesktopState } from "@/shared/desktop-state/logic/types";

export type ProposedDocument = { nodeId: string; ownerWorkspace: string; expectedRevision: number } &
  ({ kind: "text"; before: string; value: string } | { kind: "spec"; before: SpecFields; value: SpecFields });

export type GraphContext = { acceptedHead: string | null; graphDigest: string; graphManifestId: string | null;
  readOnly: boolean; requiresBaseAdoption: boolean; adoptionDocuments: PlanDocument[]; acceptedGraph?: Graph | null; workingGraph?: Graph;
  architectureContext?: { accepted: Graph | null; working: Graph; differs: boolean }; stateRevision?: number };
export type GraphSummary = { id: string; parentRevision: string | null; subject: string; by: { kind: string; name: string };
  createdAt: string; supersedes: string | null; supersededBy?: string; latestProposalId?: string;
  requiresBaseAdoption: boolean; accepted: boolean; nodeCount: number; edgeCount: number };
export type GraphProposal = GraphSummary & { schemaVersion?: 1 | 2 | 3 | 4; kind?: "graph-additions" | "graph-changes"; graphDigest: string; baseGraph: Graph; parentGraphManifestId: string | null;
  contentEffects?: { documents: ProposedDocument[]; after: DesktopState; afterDigest: string };
  contentBase?: { requiresAdoption: boolean; digest: string; entries: { kind: string; target: string; field: string; value: unknown; revision?: number }[] };
  additions: { nodes: CanvasNode[]; edges: GraphEdge[] }; refs: Record<string, string>; adoptionDocuments: PlanDocument[];
  specifications: { nodeId: string; fields: SpecFields }[]; positions: Record<string, { x: number; y: number }>;
  inside: Record<string, string>; changes?: GraphChanges; architectureDocuments?: PlanDocument[]; acceptedGraph?: Graph; resultGraph?: Graph; acceptedResultGraph?: Graph;
  stateEffects?: { revision: number; before: unknown; after: unknown; beforeDigest: string; affectedDigest: string; effects: Record<string, unknown>;
    removedNodeIds: string[]; removedEdgeIds: string[]; rewiredEdgeIds: string[]; checkedNodeIds: string[] } };
export type DraftNode = { ref: string; kind: "node" | "sector" | "area"; name: string; parent: string;
  goal: string; non_goals: string; acceptance: string; width: string; height: string };
/** `carries` prázdné = neurčeno; do návrhu se pak klíč vůbec nepošle. */
export type DraftEdge = { from: string; to: string; carries: EdgeCarries | "" };
export const newDraftNode = (ref: string): DraftNode => ({ ref, kind: "node", name: "", parent: "", goal: "", non_goals: "", acceptance: "", width: "1200", height: "800" });
export const kindNames = { node: "Karta", sector: "Sektor", area: "Oblast" };

/** Deliberate projection: clients never submit derived IDs, coordinates, author or verdict. */
export function graphPayload(project: string, workspace: string, subject: string, context: GraphContext,
  nodes: DraftNode[], edges: DraftEdge[]) {
  if (!subject.trim() || !nodes.length) throw new Error("Vyplňte důvod návrhu a alespoň jeden nový prvek.");
  if (context.readOnly) throw new Error("Pracovní prostor musí být zapisovatelný.");
  const refs = new Set(nodes.map(node => node.ref));
  if (refs.size !== nodes.length || nodes.some(node => !/^[A-Za-z][A-Za-z0-9_-]*$/.test(node.ref) || !node.name.trim()))
    throw new Error("Každý prvek potřebuje jedinečnou značku a název.");
  const validRef = (ref: string) => refs.has(ref) || /^@[A-Za-z0-9_-]+$/.test(ref);
  if (nodes.some(node => node.parent && (!validRef(node.parent) || node.parent === node.ref))
    || edges.some(edge => !validRef(edge.from) || !validRef(edge.to) || edge.from === edge.to))
    throw new Error("Zkontrolujte rodiče a oba konce každé vazby.");
  if (nodes.some(node => node.kind === "area" && [node.width, node.height].some(value => !/^\d+$/.test(value) || Number(value) < 120 || Number(value) > 20000)))
    throw new Error("Rozměry oblasti musí být celá čísla od 120 do 20000.");
  return { project, workspace, subject: subject.trim(), parentRevision: context.acceptedHead, expectedGraphDigest: context.graphDigest,
    plan: { nodes: nodes.map(node => ({ ref: node.ref, kind: node.kind, name: node.name.trim(), parent: node.parent || null,
      ...(node.kind === "area" ? { size: { w: Number(node.width), h: Number(node.height) } } : { spec: { goal: node.goal, non_goals: node.non_goals, acceptance: node.acceptance } }) })),
      edges: edges.map(edge => ({ from: edge.from, to: edge.to, port: "next" as const, ...(edge.carries ? { carries: edge.carries } : {}) })) } };
}

export const isGraphChange = (proposal: GraphProposal) => [2, 3, 4].includes(proposal.schemaVersion ?? 1);
export function adoptionKey(proposal: GraphProposal) { return isGraphChange(proposal) ? proposal.id : JSON.stringify([proposal.id, proposal.graphDigest]); }
function adoptionFingerprint(documents: PlanDocument[]) {
  return JSON.stringify([...documents].sort((left, right) => left.nodeId.localeCompare(right.nodeId)).map(document => [document.nodeId,
    document.ownerWorkspace, document.revision, document.fields.goal, document.fields.non_goals, document.fields.acceptance]));
}
export function graphProposalStale(context: GraphContext, proposal: GraphProposal) {
  return proposal.parentRevision !== context.acceptedHead || proposal.graphDigest !== context.graphDigest
    || (isGraphChange(proposal) && context.stateRevision !== undefined && proposal.stateEffects?.revision !== context.stateRevision)
    || (proposal.schemaVersion !== 4 && proposal.requiresBaseAdoption && adoptionFingerprint(proposal.adoptionDocuments) !== adoptionFingerprint(context.adoptionDocuments));
}
export function graphReadState(loaded: PromiseSettledResult<GraphContext>, history: PromiseSettledResult<{ items: GraphSummary[]; acceptedHead: string | null }>) {
  const message = (error: unknown) => error instanceof Error ? error.message : String(error);
  let context = loaded.status === "fulfilled" ? loaded.value : null;
  const items = history.status === "fulfilled" ? history.value.items : [];
  let error = loaded.status === "rejected" ? message(loaded.reason) : "";
  if (history.status === "rejected") error += " " + message(history.reason);
  if (context && history.status === "fulfilled" && context.acceptedHead !== history.value.acceptedHead) {
    context = null; error = "Kontext se během čtení změnil. Obnovte data.";
  }
  return { context, items, error: error.trim() };
}
export function graphActionPayload(project: string, workspace: string, context: GraphContext, proposal: GraphProposal,
  action: "accept" | "rebase", acknowledgement: string) {
  if (proposal.supersededBy) throw new Error("Tento návrh byl nahrazen. Otevřete aktuální návrh a zkontrolujte jeho obsah.");
  if (proposal.accepted || context.readOnly) throw new Error("Tento návrh nelze nyní měnit.");
  const payload = { project, workspace, expectedAcceptedHead: context.acceptedHead, expectedGraphDigest: context.graphDigest };
  if (action === "rebase") {
    if (proposal.schemaVersion === 4) throw new Error("Úplný snímek vyžaduje nový návrh nad aktuálním grafem.");
    return payload;
  }
  if (graphProposalStale(context, proposal))
    throw new Error("Kontext návrhu je zastaralý. Obnovte data a výslovně vytvořte nový návrh nad aktuálním základem.");
  if (isGraphChange(proposal)) {
    if (!proposal.changes || !proposal.stateEffects) throw new Error("Chybí úplné podklady pro kontrolu změn.");
    if (proposal.schemaVersion === 3 && !proposal.contentEffects) throw new Error("Chybí úplný navržený obsah.");
    if (acknowledgement !== proposal.id) throw new Error("Výslovně potvrďte kontrolu všech změn a dopadů odstranění tohoto návrhu.");
    if (proposal.schemaVersion === 3 && !proposal.contentBase) throw new Error("Chybí kontrolovaný výchozí obsah. Vytvořte nový návrh.");
    return { ...payload, adoptBaseGraphDigest: proposal.schemaVersion === 4 && proposal.requiresBaseAdoption ? proposal.graphDigest : null, reviewedChangesId: proposal.id,
      ...(proposal.contentBase?.requiresAdoption ? { adoptBaseContentDigest: proposal.contentBase.digest } : {}) };
  }
  if (proposal.requiresBaseAdoption && acknowledgement !== adoptionKey(proposal))
    throw new Error("Nejprve zkontrolujte a potvrďte převzetí přesného výchozího grafu a zadání.");
  return { ...payload, adoptBaseGraphDigest: proposal.requiresBaseAdoption ? proposal.graphDigest : null };
}

/** Selection/scope changes revoke both read and action continuations immediately. */
export class GraphRequests {
  private generation = 0;
  private writing = false;
  invalidate() { this.generation++; }
  next() { const ticket = ++this.generation; return () => ticket === this.generation; }
  beginWrite() { if (this.writing) return null; this.writing = true; return this.next(); }
  endWrite() { this.writing = false; }
  get busy() { return this.writing; }
}
