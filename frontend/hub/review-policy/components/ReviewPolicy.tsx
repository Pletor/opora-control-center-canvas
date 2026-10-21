import type { ReviewPolicyView } from "../logic/use-review-policy";
import PolicyEditor from "./PolicyEditor";
import PolicyRules from "./PolicyRules";
import PolicyStatus from "./PolicyStatus";
import "../styles/review-policy.css";

export default function ReviewPolicy({ model }: { model: ReviewPolicyView }) {
  const policy = model.context?.policy;
  return <section className="review-policy" aria-label="Pravidla GitHub review a kontrol" aria-busy={model.busy}>
    <header className="review-policy__head"><div><h2>Pravidla GitHub review a kontrol</h2><p>Výslovná místní pravidla nad serverovým pozorováním konkrétního zadání a SHA.</p></div>
      <button type="button" onClick={model.refresh} disabled={model.busy}>Obnovit nastavení pravidel</button></header>
    {model.error && <p className="review-policy__warning" role="alert">{model.error}</p>}
    {model.notice && <p role="status">{model.notice}</p>}
    {model.busy && <p role="status">Načítám nebo ukládám pravidla…</p>}
    {policy ? <section><h3>{policy.enabled ? "Aktivní" : "Vypnutá"} revize <code>{policy.id}</code></h3>
      <p>Repozitář {policy.repository.fullName} · ID {policy.repository.id} · větev <code>{policy.repository.baseBranch}</code>.</p><PolicyRules rules={policy.rules} /></section>
      : <p>Žádná výchozí pravidla se nepředpokládají. Bez nastavení jde pouze o pozorované kontroly a review.</p>}
    <PolicyStatus model={model.status} />
    {model.context && !model.context.canConfigure && <p>{model.context.unavailableReason || "Nastavení je dostupné pouze člověku v zapisovatelném projektu s přijatou revizí a GitHub repozitářem."}</p>}
    {model.context && <PolicyEditor model={model} />}
    <details><summary>Historie pravidel · nejvýše 100 revizí</summary>
      {!model.history.length && <p>Zatím bez historie pravidel.</p>}
      {model.history.map(item => <article className="review-policy__history" key={item.id}><h3>{item.enabled ? "Zapnuto" : "Vypnuto"} · <code>{item.id}</code></h3>
        <p>{item.by.name} · {new Date(item.createdAt).toLocaleString("cs-CZ")} · předchozí revize <code>{item.parentPolicyRevision ?? "není"}</code></p>
        <p>{item.repository.fullName} · ID {item.repository.id} · větev <code>{item.repository.baseBranch}</code> · zdroj identity <code>{item.identityEvidenceId}</code></p>
        <PolicyRules rules={item.rules} /></article>)}
    </details>
  </section>;
}
