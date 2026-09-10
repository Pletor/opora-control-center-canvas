import type { HandoffRun, PlanningRun } from './types';

export const ACTIVE_RUNS = new Set(['starting', 'running', 'stopping', 'verifying']);
export type LiveSession = {
  key: string; id: string; kind: 'planning' | 'handoff'; title: string;
  status: string; label: string; nodeId: string; at: string; createdAt: string;
  output: string; error: string; model: string; provider: string;
  digest: string; cost: number | null; verified: boolean | null;
  events: {kind: string; observedAt?: string; [key: string]: unknown}[];
  planning?: PlanningRun; handoff?: HandoffRun;
};
const labels: Record<string, string> = {stopped_local:'Lokální proces zastaven', prepared:'Připraveno — model neběží', starting:'Spouští se', running:'Běží', stopping:'Zastavuje se', verifying:'Ověřuje se', completed:'Dokončeno', failed:'Selhalo', cancelled:'Zastaveno', interrupted:'Přerušeno'};

// Normalizace zachovává identitu a čas zdroje; dokončený text není implementace.
export function planningSession(run: PlanningRun): LiveSession {
  return {key:`planning:${run.id}`,id:run.id,kind:'planning',title:run.message || 'Návrhový běh', status:run.status,
    label:run.status==='completed'?'Návrh dokončen':labels[run.status] || run.status,
    nodeId:run.layer,at:run.updated_at,createdAt:run.created_at,output:run.output || '',error:'',
    model:'nedostupné',provider:'nedostupné',digest:run.digest,
    cost:typeof run.provider_billing==='number' && Number.isFinite(run.provider_billing)?run.provider_billing:null,
    verified:null, events:[],planning:run};
}
export function handoffSession(run: HandoffRun): LiveSession {
  return {key:`handoff:${run.id}`,id:run.id,kind:'handoff',title:run.task, status:run.status,
    label:labels[run.status] || run.status,nodeId:run.scope.node,
    at:run.updatedAt || '',createdAt:run.createdAt || '',output:run.result?.content || '',error:run.error || '',
    model:run.model || 'nedostupné',provider:run.provider || 'nedostupné',digest:run.digest,cost:null,
    verified:run.verification?.passed ?? null,events:run.events || [],handoff:run};
}
export function downloadLiveText(filename:string, text:string, mime='text/plain;charset=utf-8') {
  const url=URL.createObjectURL(new Blob([text],{type:mime}));
  const link=document.createElement('a');link.href=url;link.download=filename;link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}

export async function fetchLiveRuns(kind:'planning'|'handoff',project:string,workspace:string,signal:AbortSignal):Promise<LiveSession[]> {
  const url=kind==='planning'?`/api/llm/runs?${new URLSearchParams({project})}`:`/api/task-handoffs?${new URLSearchParams({project,workspace})}`;
  const response=await fetch(url,{signal});
  const body=await response.json();
  if(!response.ok)throw new Error(typeof body.error==='string'?body.error:`Zdroj odpověděl HTTP ${response.status}`);
  if(!Array.isArray(body.runs))throw new Error('Zdroj nevrátil seznam běhů.');
  return kind==='planning'?(body.runs as PlanningRun[]).filter(r=>r.project_id===project&&r.workspace===workspace).map(planningSession)
    :(body.runs as HandoffRun[]).filter(r=>r.scope.project===project&&r.scope.workspace===workspace).map(handoffSession);
}
