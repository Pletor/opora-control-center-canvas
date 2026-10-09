import { useNodeSpecHistory } from "../logic/use-node-spec-history";

/** Historie se načte až s otevřeným Zadáním; dílek jen zobrazí stav dodaný hookem. */
export default function NodeSpecHistory({ project, workspace, nodeId }: { project: string; workspace: string; nodeId: string }) {
  const history = useNodeSpecHistory(project, workspace, nodeId);
  return <section><h3>Historie revizí</h3>{history.loading && <p role="status">Načítám historii revizí… <button type="button" onClick={history.cancel}>Zrušit</button></p>}
    {history.error && <p role="alert">Historii nelze načíst: {history.error} <button type="button" onClick={history.retry}>Zkusit znovu</button></p>}
    {!history.loading && !history.error && !history.items.length && <p>Zatím není uložená starší revize.</p>}
    {history.hasMore && <p role="status">⚠ Zobrazeno je prvních 20 revizí; další historie není v tomto API dostupná.</p>}
    {history.items.map((item, index) => <details key={`${item.revision}:${index}`}><summary>Verze {item.revision ?? "?"} · {item.saved_at ?? "čas nezaznamenán"}</summary><pre>{JSON.stringify(item.fields ?? item, null, 2)}</pre></details>)}</section>;
}
