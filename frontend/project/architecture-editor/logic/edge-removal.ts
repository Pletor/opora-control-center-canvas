import type { RemovalPreview } from "@/shared/types/logic/types";

/** Kde je vazba odstraňována: projekt a prostor otevřeného editoru. */
export type EdgeRemovalScope = { project: string; workspace: string };

/**
 * Odstranění vazby jde stejnou cestou jako u uzlu (server mazání přes `/api/graph` odmítá): nejdřív náhled
 * `/api/removal-preview` (`kind=edge`), pak `/api/remove` s jeho otiskem. Vazba nenese obsah karty a jde vrátit
 * přes `recoveryId`, proto editor potvrzuje rovnou, bez dialogu. Tyto funkce jen skládají požadavky.
 */
export function edgeRemovalPreviewUrl(scope: EdgeRemovalScope, edgeId: string): string {
  return "/api/removal-preview?" + new URLSearchParams({ project: scope.project, workspace: scope.workspace, kind: "edge", target: edgeId });
}

/** Tělo `/api/remove` z náhledu; náhled jiné vazby, druhu nebo prostoru je chyba (otisk by patřil něčemu jinému). */
export function edgeRemovalRequest(scope: EdgeRemovalScope, edgeId: string, preview: RemovalPreview) {
  if (preview.kind !== "edge" || preview.target !== edgeId || preview.project !== scope.project || preview.workspace !== scope.workspace)
    throw new Error("Náhled odstranění nepatří k této vazbě. Obnovte mapu.");
  return { project: scope.project, workspace: scope.workspace, kind: "edge" as const, target: edgeId, digest: preview.digest, confirmed: true as const };
}
