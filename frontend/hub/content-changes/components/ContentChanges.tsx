import type { ContentChangesView } from "../logic/use-content-changes";
import ContentDetail from "./ContentDetail";
import "../styles/content-changes.css";

export default function ContentChanges({ model, requestedId, currentAcceptedHead }: {
  model?: ContentChangesView; requestedId?: string; currentAcceptedHead: string | null }) {
  if (!model) return <p role="status">Změny obsahu nejsou dostupné. Obnovte podklady.</p>;
  const { list } = model;
  const superseded = new Set(model.items.map(item => item.supersedes).filter(Boolean));
  const pending = model.items.filter(item => !item.accepted && !superseded.has(item.id));
  const selectedId = requestedId ?? model.selectedId;
  return <section className="content-changes" aria-label="Změny obsahu">
    <header className="content-changes__header"><div><h2>Změny obsahu</h2><p>Texty, kresby a konfigurace zadání · {pending.length} čeká v načtené historii</p></div>
      <button type="button" disabled={model.pending} onClick={model.refresh}>Obnovit</button></header>
    <p>Přijetí mění plán a zadání. Není ověřením implementace, obrázkových bajtů ani externích odkazů.</p>
    {model.error && <p role="alert">{model.error}</p>}
    {model.busy && <p role="status">Načítám historii obsahu…</p>}
    {!requestedId && <div className="content-changes__list">{model.items.map(item => <button type="button" key={item.id} onClick={() => model.select(item.id)}
      aria-pressed={selectedId === item.id} disabled={model.pending}>
      <strong>{item.subject}</strong><span>{item.changeCount} změn · {item.by.name} · {item.id.slice(0, 12)}</span>
      <span>{item.accepted ? "Přijato do historie" : superseded.has(item.id) ? "Nahrazeno novým návrhem" : item.parentRevision !== list?.acceptedHead ? "Zastaralý základ · nejprve rebase" : "Čeká na kontrolu"}</span>
    </button>)}</div>}
    {!requestedId && !model.busy && !model.error && !model.items.length && <p>Zatím žádné návrhy obsahu v načtené historii (limit 100).</p>}
    {selectedId && <div className="content-changes__inspection">
      {model.detailBusy && <p role="status">Načítám přesné ID návrhu…</p>}
      {model.detailError && <p role="alert">{model.detailError}</p>}
      {model.detail?.proposal.id === selectedId ? <ContentDetail model={model} currentAcceptedHead={currentAcceptedHead} />
        : !model.detailBusy && !model.detailError && <p>Vybraný návrh není dostupný. Nebyl nahrazen jiným návrhem.</p>}
    </div>}
    <details className="content-changes__recipe"><summary>Pro agenty · vytvoření návrhu přes API</summary><p>Nejprve načtěte přijatou hlavu. Agent pouze navrhuje; přijímá člověk.</p>
      <pre>{JSON.stringify({ method: "POST", path: "/api/oporahub/content-changes", body: { project: model.project, workspace: model.workspace,
        expectedAcceptedHead: list?.acceptedHead ?? "PŘIJATÁ_HLAVA", subject: "Popis změny", changes: [{ kind: "text", target: "ID_KARTY", field: "text", value: "Nové zadání" }] } }, null, 2)}</pre>
      <p>Další druhy: drawing / scene; config / actions, rules, blocks, materials, downloadsUrl. GET seznam a detail, POST /ID/rebase nebo lidské /ID/accept.</p>
    </details>
  </section>;
}
