import { contentValue } from "../logic/content-changes";
import type { ContentChangesView } from "../logic/use-content-changes";
import ProposalReview from "@/hub/proposal-review/components/ProposalReview";
import { reviewReady } from "@/hub/proposal-review/logic/proposal-review";
import type { ProposalReviewView } from "@/hub/proposal-review/logic/use-proposal-review";

function Value({ title, value }: { title: string; value: unknown }) {
  return <div className="content-changes__value"><h4>{title}</h4><pre>{contentValue(value).preview}</pre></div>;
}
export default function ContentDetail({ model, currentAcceptedHead, review }: { model: ContentChangesView; currentAcceptedHead: string | null; review?: ProposalReviewView }) {
  const detail = model.detail!;
  const item = detail.proposal;
  const headKnown = !!currentAcceptedHead && currentAcceptedHead === model.list?.acceptedHead && currentAcceptedHead === detail.acceptedHead;
  const stale = !headKnown || item.parentRevision !== currentAcceptedHead;
  const canAccept = !model.disabled && !stale && !detail.accepted && detail.canAccept && !!model.list?.canAccept
    && (!item.requiresBaseContentAdoption || model.acknowledged) && reviewReady(review, { proposalKind: "content", proposalId: item.id }, currentAcceptedHead);
  const json = JSON.stringify(item, null, 2);
  function download() {
    const url = URL.createObjectURL(new Blob([json], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = `oporahub-content-${item.id}.json`; link.click(); URL.revokeObjectURL(url);
  }
  return <article className="content-changes__detail">
    <h3>{item.subject}</h3><code className="content-changes__id">{item.id}</code>
    <p>{item.by.name} · {new Date(item.createdAt).toLocaleString("cs-CZ")} · {item.changes.length} změn</p>
    <p>Rodič: <code>{item.parentRevision}</code></p>
    <p role="status">{detail.accepted ? `Přijato v revizi ${detail.accepted}` : !headKnown ? "Aktuální společný základ není doložen. Přijetí je vypnuté." : stale ? "Návrh má starší základ. Před přijetím jej převeďte na aktuální hlavu." : "Základ návrhu odpovídá načtené přijaté revizi."}</p>
    <button type="button" onClick={download}>Stáhnout úplný JSON návrhu</button>
    {item.changes.map(change => <section className="content-changes__change" key={JSON.stringify([change.kind, change.target, change.field])}>
      <header><h4>{change.kind === "text" ? "Text" : change.kind === "drawing" ? "Kresba" : change.kind === "storyboard" ? "Storyboard" : "Konfigurace"} · {change.field === "downloadsUrl" ? "Úloha stahuje URL" : change.field}</h4>
        <p>{change.target || "Kořenová kresba"} · vlastník {change.observedOwner} · {change.observedRevision !== undefined ? `zdrojová revize ${change.observedRevision} · ` : ""}kolo {change.observedRound ?? "neuvedeno"}</p></header>
      <div className="content-changes__diff"><Value title="Přijatý obsah" value={change.acceptedBefore?.value ?? (change.acceptedBefore ? null : undefined)} />
        <Value title="Pozorovaný pracovní stav" value={change.before} /><Value title="Navržená hodnota" value={change.value} /></div>
    </section>)}
    {item.requiresBaseContentAdoption && <section className="content-changes__adoption"><h4>První přijetí převezme celý výchozí obsah</h4>
      <p>Kromě změn výše se schvaluje {item.baseContent.length} výchozích položek. Zkontrolujte celý základ; nejde pouze o viditelný patch.</p>
      <p>Zavedení schváleného obsahového základu může zneplatnit běžící úlohy založené na revizi bez tohoto manifestu.</p>
      <code>{item.baseContentDigest}</code><details><summary>Prohlédnout výchozí obsah ({item.baseContent.length} položek)</summary>
        {item.baseContent.map(entry => <details key={JSON.stringify([entry.kind, entry.target, entry.field])}><summary>{entry.kind} · {entry.target || "kořen"} · {entry.field} · {entry.ownerWorkspace}</summary><pre>{contentValue(entry.value).preview}</pre></details>)}</details>
      <label><input type="checkbox" checked={model.acknowledged} disabled={model.disabled || !!detail.accepted || stale} onChange={event => model.acknowledge(event.target.checked)} />Potvrzuji kontrolu celého výchozího obsahu s tímto přesným otiskem.</label>
    </section>}
    {model.conflicts.length > 0 && <section className="content-changes__conflicts" role="alert"><h4>Konflikty · původní návrh zůstává</h4><ul>{model.conflicts.map((conflict, index) => <li key={index}>{conflict.kind} · {conflict.target || "kořen"} · {conflict.field}: {conflict.reason}</li>)}</ul></section>}
    {model.notice && <p role="status">{model.notice}</p>}{model.actionError && <p role="alert">{model.actionError}</p>}
    <ProposalReview model={review} proposalKind="content" proposalId={item.id} acceptedHead={currentAcceptedHead} />
    <div className="content-changes__actions"><button type="button" disabled={model.disabled || !headKnown || !!detail.accepted} onClick={model.rebase}>Převést na aktuální základ</button>
      <button type="button" className="content-changes__accept" disabled={!canAccept} onClick={model.accept}>{model.pending ? "Ukládám…" : "Přijmout přesný návrh"}</button></div>
    {!detail.canAccept && !detail.accepted && <p>Přijetí je dostupné pouze identifikovanému člověku v zapisovatelném prostoru.</p>}
  </article>;
}
