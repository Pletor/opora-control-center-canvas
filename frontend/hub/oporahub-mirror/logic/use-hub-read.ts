import { useCallback, useEffect, useState } from "react";
import { hubRead, type Parse } from "./hub-read";

export type HubRead<T> = { data: T | null; busy: boolean; error: string; reload: () => void };

/** Čte jednou při otevření detailu a po `reload`; jiná URL okamžitě skryje data předchozí URL. */
export function useHubRead<T>(url: string | null, parse: Parse<T>): HubRead<T> {
  const [nonce, setNonce] = useState(0);
  const [state, setState] = useState<{ url: string | null; data: T | null; busy: boolean; error: string }>({ url, data: null, busy: false, error: "" });
  useEffect(() => {
    if (!url) { setState({ url, data: null, busy: false, error: "" }); return; }
    const controller = new AbortController();
    setState(current => ({ url, data: current.url === url ? current.data : null, busy: true, error: "" }));
    hubRead(url, parse, controller.signal)
      .then(data => { if (!controller.signal.aborted) setState({ url, data, busy: false, error: "" }); })
      .catch(error => { if (!controller.signal.aborted) setState(current => ({ url, data: current.url === url ? current.data : null, busy: false,
        error: error instanceof Error ? error.message : "Čtení se nezdařilo." })); });
    return () => controller.abort();
    // `parse` je čistá funkce modulu; čtení řídí jen URL a ruční obnova.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, nonce]);
  const reload = useCallback(() => setNonce(value => value + 1), []);
  const shown = state.url === url ? state : { url, data: null, busy: !!url, error: "" };
  return { data: shown.data, busy: shown.busy, error: shown.error, reload };
}
