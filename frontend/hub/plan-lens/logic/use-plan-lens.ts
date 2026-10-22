import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { IDLE, planLensReducer, planLensUrl, readPlanLens, type PlanLensState } from "./plan-lens-read";

export type PlanLensView = PlanLensState & { reload: () => void };

/** Lens plánu: jedno čtení při otevření okna a po „Obnovit“ (s ETagem, takže beze změny přijde 304); žádné pollování. */
export function usePlanLens(project: string, workspace: string, area: string | null): PlanLensView {
  const url = project && workspace ? planLensUrl(project, workspace, area) : null;
  const [state, dispatch] = useReducer(planLensReducer, IDLE);
  const [nonce, setNonce] = useState(0);
  const latest = useRef(state);
  latest.current = state;
  const lastUrl = useRef(url);
  useEffect(() => {
    if (!url) return;
    // Jiná oblast nebo projekt nesmí potvrdit ETagem data předchozí URL.
    const etag = lastUrl.current === url && latest.current.data ? latest.current.etag : "";
    if (lastUrl.current !== url) dispatch({ type: "reset" });
    lastUrl.current = url;
    const controller = new AbortController();
    dispatch({ type: "start" });
    readPlanLens(url, etag, controller.signal).then(event => { if (!controller.signal.aborted) dispatch(event); }, () => {});
    return () => controller.abort();
  }, [url, nonce]);
  const reload = useCallback(() => setNonce(value => value + 1), []);
  return { ...state, reload };
}
