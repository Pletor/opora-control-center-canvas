import type { GithubReconciliationView } from "../logic/use-github-reconciliation";
import BindingIdentity from "./BindingIdentity";

const actionNames = { enroll: "Zapnout trvalé sledování", pause: "Pozastavit sledování", resume: "Obnovit původní sledování", retry: "Naplánovat nový pokus" };
export default function ReconciliationEnrollment({ model }: { model: GithubReconciliationView }) {
  const { candidate, review, selected } = model;
  const sources = model.evidence.items.filter(item => item.snapshot.complete && item.snapshot.acceptedRevision === model.context?.currentAcceptedHead);
  const identity = review?.action === "enroll" ? candidate.candidate?.binding : selected?.binding;
  const confirmationDisabled = review?.action === "pause" ? !model.pauseAllowed : model.disabled;
  return <>
    <fieldset className="github-reconciliation__enrollment" disabled={model.disabled}><legend>Nové trvalé sledování PR</legend>
      <p>Vyberte úplné serverové pozorování aktuální přijaté revize. Číselnou identitu repozitáře a PR ověří server; odkaz se nepřebírá z volného textu.</p>
      <label className="github-reconciliation__field">Pozorování pro trvalé sledování<select aria-label="Pozorování pro trvalé sledování" value={model.evidenceId} onChange={event => model.selectEvidence(event.target.value)}>
        <option value="">Vyberte pozorování GitHub důkazů</option>
        {sources.map(item => <option key={item.snapshot.id} value={item.snapshot.id}>PR #{item.snapshot.pr?.number ?? item.snapshot.prNumber} · {item.snapshot.configuredRepository} · {item.snapshot.id}</option>)}
      </select></label>
      {!sources.length && <p>Nejprve přijměte plán a načtěte úplné GitHub pozorování pro jeho aktuální revizi.</p>}
      {candidate.busy && <p role="status">Ověřuji podklady pro vazbu bez nového čtení GitHubu…</p>}
      {candidate.error && <p role="alert">{candidate.error}</p>}
      {candidate.candidate && <><BindingIdentity binding={candidate.candidate.binding} />
        {!candidate.candidate.canConfigure && <p>{candidate.candidate.unavailableReason}</p>}
        {candidate.candidate.existingEnabledBinding && <p className="github-reconciliation__warning">Toto PR již má aktivní vazbu <code>{candidate.candidate.existingEnabledBinding.id}</code>. Nejprve ji výslovně pozastavte; původní historie se nepřepisuje.</p>}</>}
      <button type="button" disabled={candidate.busy || !candidate.candidate?.canConfigure || !!candidate.candidate?.existingEnabledBinding} onClick={() => model.prepare("enroll")}>Zkontrolovat zapnutí sledování</button>
    </fieldset>
    {review && identity && <section className="github-reconciliation__confirmation" aria-label="Potvrzení trvalého sledování">
      <h3>{actionNames[review.action]}</h3><BindingIdentity binding={identity} />
      {review.action !== "enroll" && <p>Očekávaná generace řízení: <code>{selected?.control.generation}</code></p>}
      {review.action === "enroll" ? <p>Server bude trvale číst stav tohoto PR i po zavření prohlížeče a po restartu. Otevřené PR čte přibližně každých {identity.intervalSeconds} sekund, uzavřené bez merge pomaleji. Sloučené PR se uloží a pravidelné sledování skončí.</p>
        : review.action === "pause" ? <p>Nové pokusy se pozastaví. Probíhající vzdálené čtení může doběhnout, ale nesmí přepsat pozastavenou vazbu. Historie zůstává.</p>
          : review.action === "resume" ? <p>Obnoví se původní číselná identita i původní revize plánu. Novější plán se automaticky nepřevezme.</p>
            : <p>Požádáte trvalý serverový proces o další pokus. Omezení poskytovatele a jeho čekací doba zůstávají v platnosti.</p>}
      <p>Jde pouze o čtení GitHubu. Vazba je lidské přiřazení, nikoli důkaz implementace, review, dokončení karty nebo nasazení.</p>
      <label className="github-reconciliation__ack"><input type="checkbox" checked={model.confirmed} disabled={confirmationDisabled} onChange={event => model.confirm(event.target.checked)} />
        Výslovně potvrzuji tuto akci, přesné identity a revizi; při zapnutí souhlasím s trvalým čtením GitHubu na serveru.</label>
      <button type="button" disabled={confirmationDisabled || !model.confirmed} onClick={model.save}>Potvrdit: {actionNames[review.action]}</button>
      <button type="button" disabled={model.busy} onClick={model.cancel}>Zrušit potvrzení</button>
    </section>}
  </>;
}
