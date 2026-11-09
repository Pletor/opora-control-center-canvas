import type {FlowGraph, FlowVersion, FlowWorkflow, NodeRun} from '@/shared/flow-editor/logic/flow-types';

export type Review = {operation: string; identifier: string; digest: string; workflow: FlowWorkflow; selected: FlowVersion | null; active: FlowVersion | null; nodeRun: NodeRun | null};
export const titles: Record<string, string> = {version_candidate: 'Navrhnout verzi ke schválení', version_activate: 'Aktivovat verzi', version_approve: 'Schválit záměr stránky', version_reject: 'Zamítnout verzi', version_rollback: 'Vrátit předchozí verzi', approval_decision: 'Rozhodnout o čekajícím kroku'};

/** Legacy native versions may omit positions; review only supplies missing display coordinates. */
export function displayGraph(graph: FlowGraph): FlowGraph {
  let x = Math.max(-320, ...graph.nodes.filter(n => n.position).map(n => n.position!.x)) + 320;
  return {...graph, nodes: graph.nodes.map(n => n.position ? n : {...n, position: {x: (x += 320) - 320, y: 0}})};
}

export function selection(search: string, project: string, workspace: string) {
  const q = new URLSearchParams(search), operation = q.get('flowOperation'), identifier = q.get('flowReview');
  return q.get('project') === project && q.get('workspace') === workspace && operation && identifier && operation in titles ? {operation, identifier} : null;
}

export function actionable(r: Review) {
  const status = r.selected?.status;
  switch (r.operation) {
    case 'version_candidate': return status === 'draft';
    case 'version_activate': return r.workflow.kind !== 'page_intent' && (status === 'candidate' || status === 'retired');
    case 'version_approve': return r.workflow.kind === 'page_intent' && status === 'candidate';
    case 'version_reject': return r.workflow.kind === 'page_intent' ? status === 'candidate' : r.workflow.kind === 'library_flow' && (status === 'draft' || status === 'candidate');
    case 'version_rollback': return !!r.active && status === 'retired';
    case 'approval_decision': return r.nodeRun?.status === 'waiting' && r.selected?.graph.nodes.find(n => n.id === r.nodeRun?.node_id)?.type === 'approval.human';
    default: return false;
  }
}

export function actionRequest(r: Review, reason: string, decision?: string) {
  if (!actionable(r)) throw new Error('Tento stav už nelze rozhodnout. Obnovte podklady.');
  const operation = r.operation;
  const path = operation === 'approval_decision' ? `node-runs/${r.identifier}/decision` : operation === 'version_rollback' ? `workflows/${r.identifier}/rollback` : `versions/${r.identifier}/${operation.replace('version_', '')}`;
  const body = operation === 'approval_decision' ? {decision} : operation === 'version_reject' ? {reason} : {};
  return {url: `/api/flow/${path}?expectedReviewDigest=${encodeURIComponent(r.digest)}`, body};
}
