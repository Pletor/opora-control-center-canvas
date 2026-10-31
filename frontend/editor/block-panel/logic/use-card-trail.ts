// Čtení stopy práce jedné karty pro panel bloku. Identita jako u historie běhů v detailu karty: nejdřív
// lidská UI session (`useUiSession`), pak jednorázové čtení. Nový snímek agent-state (`refreshKey`) čte znovu,
// takže panel drží krok s plátnem bez vlastního polleru.
import { useEffect, useRef } from "react";
import { useUiSession } from "@/hub/oporahub-card-drawer/logic/use-card-data";
import { useHubRead } from "@/hub/oporahub-mirror/logic/use-hub-read";
import { cardTrailUrl, parseCardTrail } from "./card-trail";

export function useCardTrail(project: string, workspace: string, nodeId: string, refreshKey: string) {
  const session = useUiSession();
  const scoped = !!project && !!workspace && !!nodeId;
  const read = useHubRead(scoped && session ? cardTrailUrl(project, workspace, nodeId) : null, parseCardTrail);
  const seen = useRef(refreshKey);
  const { reload } = read;
  useEffect(() => {
    if (seen.current === refreshKey) return;
    seen.current = refreshKey;
    reload();
  }, [refreshKey, reload]);
  return read;
}
