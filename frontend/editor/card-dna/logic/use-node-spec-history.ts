import { useEffect, useRef, useState } from "react";

type Item = { revision?: number; saved_at?: string; fields?: { goal?: string; non_goals?: string; acceptance?: string } };
type History = { items?: Item[]; has_more?: boolean; error?: string };
export type NodeSpecHistoryState = { items: Item[]; hasMore: boolean; error: string; loading: boolean; cancel: () => void; retry: () => void };
const errorMessage = (error: unknown) => error instanceof Error ? error.message : String(error);

/** Lazy historie patří do hooku: dílek jen zobrazí hotový stav a pošle retry/cancel nahoru. */
export function useNodeSpecHistory(project: string, workspace: string, nodeId: string): NodeSpecHistoryState {
  const [items, setItems] = useState<Item[]>([]); const [hasMore, setHasMore] = useState(false); const [error, setError] = useState("");
  const [loading, setLoading] = useState(true); const [revision, setRevision] = useState(0); const request = useRef<AbortController | null>(null);
  useEffect(() => {
    request.current?.abort(); const abort = new AbortController(); request.current = abort;
    const url = "/api/node-spec/history?" + new URLSearchParams({ project, workspace, node: nodeId });
    setLoading(true); setError(""); setItems([]); setHasMore(false);
    void fetch(url, { signal: abort.signal }).then(async response => {
      const value = await response.json() as History;
      if (!response.ok) throw new Error(value.error ?? `Historii nelze načíst (HTTP ${response.status}).`);
      return value;
    }).then(value => {
      if (abort.signal.aborted) return;
      setItems(Array.isArray(value.items) ? value.items : []); setHasMore(value.has_more === true);
    }).catch(reason => { if (!abort.signal.aborted) setError(errorMessage(reason)); })
      .finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => abort.abort();
  }, [nodeId, project, revision, workspace]);
  return { items, hasMore, error, loading, cancel: () => { request.current?.abort(); setLoading(false); }, retry: () => setRevision(value => value + 1) };
}
