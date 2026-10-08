import { useEffect, useRef, useState } from "react";

type Item = { revision?: number; saved_at?: string; fields?: { goal?: string; non_goals?: string; acceptance?: string } };
type History = { items?: Item[]; has_more?: boolean; error?: string };
const errorMessage = (error: unknown) => error instanceof Error ? error.message : String(error);

/** Historie se načte až s otevřeným Zadáním; požadavek lze zrušit a server dnes vrací nejvýše 20 revizí. */
export default function NodeSpecHistory({ project, workspace, nodeId }: { project: string; workspace: string; nodeId: string }) {
  const [items, setItems] = useState<Item[]>([]); const [hasMore, setHasMore] = useState(false); const [error, setError] = useState("");
  const [loading, setLoading] = useState(true); const [retry, setRetry] = useState(0); const request = useRef<AbortController | null>(null);
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
    }).catch(reason => {
      if (!abort.signal.aborted) setError(errorMessage(reason));
    }).finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => abort.abort();
  }, [nodeId, project, retry, workspace]);
  const cancel = () => { request.current?.abort(); setLoading(false); };
  return <section><h3>Historie revizí</h3>{loading && <p role="status">Načítám historii revizí… <button type="button" onClick={cancel}>Zrušit</button></p>}
    {error && <p role="alert">Historii nelze načíst: {error} <button type="button" onClick={() => setRetry(value => value + 1)}>Zkusit znovu</button></p>}
    {!loading && !error && !items.length && <p>Zatím není uložená starší revize.</p>}
    {hasMore && <p role="status">⚠ Zobrazeno je prvních 20 revizí; další historie není v tomto API dostupná.</p>}
    {items.map((item, index) => <details key={`${item.revision}:${index}`}><summary>Verze {item.revision ?? "?"} · {item.saved_at ?? "čas nezaznamenán"}</summary><pre>{JSON.stringify(item.fields ?? item, null, 2)}</pre></details>)}</section>;
}
