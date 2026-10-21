import type { GithubReconciliationView } from "../logic/use-github-reconciliation";
import ReconciliationEnrollment from "./ReconciliationEnrollment";
import ReconciliationStatus from "./ReconciliationStatus";
import ReconciliationHistory from "./ReconciliationHistory";
import "../styles/github-reconciliation.css";

export default function GithubReconciliation({ model }: { model: GithubReconciliationView }) {
  return <section className="github-reconciliation" aria-label="Trvalé sledování GitHub PR" aria-busy={model.busy}>
    <header className="github-reconciliation__head"><div><h2>Trvalé sledování GitHub PR</h2><p>Server ukládá pozorovaný stav konkrétního PR i po zavření prohlížeče a restartu.</p></div>
      <button type="button" disabled={model.busy} onClick={model.refresh}>Obnovit uložený stav sledování</button></header>
    {model.busy && <p role="status">Načítám nebo ukládám stav sledování…</p>}
    {model.error && <p role="alert" className="github-reconciliation__warning">{model.error} Zobrazené dřívější údaje nejsou novým potvrzením stavu.</p>}
    {model.context && !model.context.canConfigure && <p>{model.context.unavailableReason || "Nastavení vyžaduje lidskou relaci a dostupný zapisovatelný prostor."}</p>}
    {model.context?.automaticWorkerEnabled === false && <p className="github-reconciliation__warning">Automatický serverový proces je v této instanci vypnutý. Naplánované pokusy se samy nespustí, dokud jej správce nepovolí. {model.context.automaticWorkerUnavailableReason}</p>}
    <ReconciliationEnrollment model={model} />
    <h3>Vazby v tomto pracovním prostoru</h3>
    {!model.items.length && !model.busy && <p>Žádné trvalé sledování není nastaveno. Samotné otevření panelu nespouští čtení GitHubu.</p>}
    <ul className="github-reconciliation__list">{model.items.map(item => <li key={item.binding.id}><button type="button" disabled={model.busy} aria-pressed={model.selected?.binding.id === item.binding.id} onClick={() => model.select(item.binding.id)}>
      {item.binding.repository.fullName} · PR #{item.binding.pr.number} · {item.control.enabled ? "Zapnuto" : "Pozastaveno"}</button><span>{item.revisionRelation.matchesCurrentAcceptedRevision ? "Vazba k aktuální revizi" : "Historická revize plánu"}</span></li>)}</ul>
    <ReconciliationStatus model={model} /><ReconciliationHistory model={model} />
  </section>;
}
