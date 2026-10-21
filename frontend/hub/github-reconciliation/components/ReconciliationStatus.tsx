import type { GithubReconciliationView } from "../logic/use-github-reconciliation";
import { displayTime, jobLabels, prLabels } from "../logic/reconciliation";
import BindingIdentity from "./BindingIdentity";

export default function ReconciliationStatus({ model }: { model: GithubReconciliationView }) {
  const item = model.selected;
  if (!item) return null;
  const { binding, control, job, latestAttempt: latest, lastSuccessfulObservation: observation } = item;
  const historical = !!model.error || !!latest && latest.state !== "complete" || job.state === "checking" || job.state === "retrying" || job.state === "paused";
  return <section className="github-reconciliation__details" aria-label="Stav trvalého sledování">
    <h3>Vazba PR #{binding.pr.number} · <code>{binding.id}</code></h3><BindingIdentity binding={binding} />
    {!item.revisionRelation.matchesCurrentAcceptedRevision && <p className="github-reconciliation__warning">Sledování je vázáno k dřívější nebo jiné revizi plánu. Nadále sleduje původní PR; není vazbou k aktuálnímu plánu <code>{item.revisionRelation.currentAcceptedRevision ?? "bez přijaté revize"}</code>.</p>}
    <div className="github-reconciliation__planes"><article><h4>1. Stav serverového sledování</h4>
      <strong>{jobLabels[job.state]}</strong><p>Generace řízení {control.generation} · {control.enabled ? "Zapnuto" : "Pozastaveno"}.</p>
      <p>Další pokus: {displayTime(job.nextAttemptAt)} · po sobě jdoucí neúspěchy: {job.consecutiveFailures}.</p>
      {job.leaseUntil && <p>Rezervace probíhajícího pokusu do {displayTime(job.leaseUntil)}. Po přerušení může server po jejím vypršení bezpečně převzít práci.</p>}
      {job.providerRetryUntil && <p>Čekací doba poskytovatele do {displayTime(job.providerRetryUntil)}.</p>}
      {job.lastErrorCode && <p className="github-reconciliation__warning">Důvod: <code>{job.lastErrorCode}</code></p>}
      {latest && <p>Poslední pokus <code>{latest.id}</code> · {latest.state} · {displayTime(latest.startedAt)} — {displayTime(latest.finishedAt)}{latest.errorCode && <> · <code>{latest.errorCode}</code></>}</p>}
      <p>Načteno ze serveru: {displayTime(model.context?.serverNow)}. Čtení tohoto panelu samo nespouští GitHub práci.</p>
    </article><article><h4>2. Pozorovaný stav pull requestu</h4>
      {!observation ? <p>Stav PR zatím není doložen.</p> : <><p><strong>{historical ? "Poslední úspěšné historické pozorování" : "Poslední uložené pozorování"}</strong></p>
        {historical && <p>Poslední pokus nepotvrzuje nově načtený stav. Tento starší fakt zůstává v historii.</p>}
        <strong>{prLabels[observation.data.pr.state]}</strong>
        <p>Interval čtení: {displayTime(observation.data.observedFrom)} — {displayTime(observation.data.observedUntil)}.</p>
        <dl className="github-reconciliation__identity"><dt>Zdrojová hlava PR</dt><dd><code>{observation.data.pr.headSha}</code></dd>
          <dt>Merge commit SHA</dt><dd><code>{observation.data.pr.mergeCommitSha ?? "Není doložen merge commit"}</code></dd>
          <dt>Čas sloučení</dt><dd>{displayTime(observation.data.pr.mergedAt)}</dd>
          <dt>Zdrojový repozitář v pozorování</dt><dd>{observation.data.pr.headRepoId ?? "Fork již není dostupný; původní vazba se nemění"}</dd></dl>
        {observation.data.pr.draft && <p>PR je návrh (draft).</p>}</>}
    </article><article><h4>3. Review a kontroly jsou samostatné</h4>
      <p>Zaznamenání stavu PR nepotvrzuje místní pravidla review. Jejich aktuální vyhodnocení je v samostatném panelu.</p>
      <p>Kontroly zdrojové hlavy neověřují automaticky merge commit. Záznam sloučení neprokazuje, že cílová větev obsahuje změnu i po pozdějším revertu nebo přepsání historie.</p>
    </article></div>
    <div className="github-reconciliation__actions">
      <button type="button" disabled={!model.pauseAllowed || !control.enabled} onClick={() => model.prepare("pause")}>Pozastavit vybrané sledování</button>
      <button type="button" disabled={model.disabled || control.enabled} onClick={() => model.prepare("resume")}>Obnovit vybrané sledování</button>
      <button type="button" disabled={model.disabled || !control.enabled || job.state === "checking"} onClick={() => model.prepare("retry")}>Připravit nový pokus</button>
    </div>
  </section>;
}
