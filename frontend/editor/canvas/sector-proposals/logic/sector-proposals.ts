// Hromadné potvrzení návrhů uzavření v sektoru (vráceno po #30, audit sirotků #4). Čistá logika bez Reactu:
// které návrhy v sektoru čekají, které smí jít hromadně a jak vypadá jeden zápis na /api/desktop-v3/confirm-proposals.
import type { Graph } from "@/shared/types/logic/types";
import type { DesktopState, StateResponse } from "@/shared/desktop-state/logic/types";
import type { BoardIndex } from "@/editor/canvas/board/logic/board-index";
import { proposalsIn } from "@/editor/canvas/node-card/logic/completion-proposals";
import { batchConfirmable, evidenceReadiness, missingLabel, type EvidenceReadiness } from "@/editor/canvas/node-card/logic/evidence-readiness";

export type SectorProposal = { id: string; name: string; note: string; readiness: EvidenceReadiness; batch: boolean; why: string };

/** Server přijme v jednom zápisu nejvýš tolik karet (`backend/editor/agent_memory/confirm_proposals.py`). */
export const BATCH_MAX = 200;

/** Proč karta hromadně nejde, nebo prázdný řetězec, když jde. */
function blockedWhy(readiness: EvidenceReadiness): string {
  if (!readiness.ready) return missingLabel(readiness);
  if (readiness.notApplicable.length) return `obsahuje N/A: ${readiness.notApplicable.join(", ")}`;
  return "";
}

/** Čekající návrhy agenta pod sektorem (do hloubky), každý s připraveností důkazů a příznakem hromadného potvrzení. */
export function sectorProposals(graph: Graph, state: DesktopState, sectorId: string, index?: BoardIndex): SectorProposal[] {
  return proposalsIn(graph, state, sectorId, index).map((p) => {
    const node = index?.byId.get(p.id) ?? graph.nodes.find((n) => n.id === p.id);
    const readiness = evidenceReadiness(state.nodes[p.id]?.evidence, node);
    const why = blockedWhy(readiness);
    return { ...p, readiness, batch: !why && batchConfirmable(readiness), why };
  });
}

/** Id karet, které jedno kliknutí potvrdí: jen s hotovými důkazy bez N/A, nejvýš `BATCH_MAX`. */
export const batchIds = (proposals: SectorProposal[]) => proposals.filter((p) => p.batch).map((p) => p.id).slice(0, BATCH_MAX);

/** Popisek tlačítka podle stavu. */
export const confirmLabel = (count: number, busy: boolean) => (busy ? "Potvrzuji…" : `✓ Potvrdit návrhy (${count})`);

export type ConfirmDeps = {
  /** Revize stavu přečtená těsně před zápisem. */
  fetchRevision: () => Promise<number>;
  /** POST /api/desktop-v3/confirm-proposals. */
  post: (body: object) => Promise<StateResponse>;
};

/** Jeden zápis za člověka. Revize až těsně před zápisem: stav mezitím mění agenti a stará revize by zápis odmítla. */
export async function confirmSector(project: string, workspace: string, sectorId: string, nodeIds: string[], deps: ConfirmDeps): Promise<StateResponse> {
  if (!nodeIds.length) throw new Error("V sektoru není žádný návrh k hromadnému potvrzení.");
  const expectedRevision = await deps.fetchRevision();
  return deps.post({ project, workspace, sectorId, nodeIds, expectedRevision });
}
