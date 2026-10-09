// Člověk smí uvolnit převzetí karty kterémukoli agentovi bez tokenu; lidskou relaci přidá `api()` sám.
import { api } from "@/shared/types/logic/types";

export const releaseLeaseBody = (project: string, workspace: string, nodeId: string) =>
  ({ project, workspace, nodeId, op: "release" as const });

export function releaseLease(project: string, workspace: string, nodeId: string): Promise<unknown> {
  return api("/api/desktop-v3/lease", releaseLeaseBody(project, workspace, nodeId));
}
