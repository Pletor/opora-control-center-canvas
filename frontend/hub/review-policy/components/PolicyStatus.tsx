import { policyLabels } from "../logic/review-policy";
import type { PolicyStatusView } from "../logic/use-policy-status";

const checkLabels = { passed: "Prošla", missing: "Chybí", pending: "Probíhá", failed: "Selhala", unknown: "Nedoloženo" };
const reviewLabels = { approved: "Schválení doloženo", changes_requested: "Požadovány změny", missing: "Chybí schválení", unknown: "Nedoloženo" };
const time = (value: string | null) => value ? new Date(value).toLocaleString("cs-CZ") : "Nedoloženo";
export default function PolicyStatus({ model }: { model: PolicyStatusView }) {
  const value = model.value;
  return <section className="review-policy__status" aria-label="Aktuální splnění místních pravidel">
    <h3>Aktuální splnění místních pravidel · {model.prNumber ? `PR #${model.prNumber}` : "vyberte PR v GitHub důkazech"}</h3>
    <strong className={`review-policy__verdict${model.status === "satisfied" ? " review-policy__verdict--satisfied" : ""}`}>{policyLabels[model.status]}</strong>
    {model.busy && <p role="status">Znovu vyhodnocuji uložené důkazy; předchozí stav nyní neplatí.</p>}
    {model.invalidated && <p>Kontext se mění, probíhá nové pozorování nebo poslední pokus selhal. Předchozí splnění se nepřebírá.</p>}
    {model.error && <p role="alert">{model.error}</p>}
    <button type="button" disabled={!model.prNumber || model.busy || model.invalidated} onClick={model.refresh}>Obnovit stav pravidel bez načtení GitHubu</button>
    <p>Tento stav se vyhodnocuje z uložených pozorování. Nové čtení GitHubu spustíte výslovně v části GitHub důkazy.</p>
    {value && <>
      {value.status === "satisfied" && model.status !== "satisfied" && <p className="review-policy__warning">Platnost posledního vyhodnocení skončila. Dřívější splnění již není aktuální.</p>}
      <dl className="review-policy__identity">
        <dt>Pravidla</dt><dd><code>{value.policyRevision ?? "nenastavena"}</code></dd>
        <dt>Přijatá revize zadání</dt><dd><code>{value.binding.acceptedRevision ?? "nedoložena"}</code></dd>
        <dt>SHA hlavy PR</dt><dd><code>{value.binding.headSha ?? "nedoloženo"}</code></dd>
        <dt>Repozitář / PR / zdrojový repozitář</dt><dd>{value.binding.repositoryId ?? "—"} / {value.binding.prId ?? "—"} / {value.binding.headRepoId ?? "—"}</dd>
        <dt>Cílová větev a SHA</dt><dd>{value.binding.baseBranch ?? "—"} · <code>{value.binding.baseSha ?? "—"}</code></dd>
        <dt>Pozorování / pořadí pokusu</dt><dd><code>{value.evidenceId ?? "nedoloženo"}</code> / {value.attemptSequence ?? "—"}</dd>
        <dt>Interval čtení GitHubu</dt><dd>{time(value.freshness.observedFrom)} — {time(value.freshness.observedUntil)}</dd>
        <dt>Vyhodnoceno serverem</dt><dd>{time(value.freshness.evaluatedAt)}</dd>
        <dt>Platnost nejdéle do</dt><dd>{time(value.freshness.expiresAt)}</dd>
      </dl>
      <h4>Kontroly vyžadované pravidly</h4><ul>{value.checks.required.map(check => <li key={`${check.appId}:${check.name}`}><code>{check.name}</code> · aplikace {check.appId} · {checkLabels[check.status]} · běh {check.runId ?? "nedoložen"}</li>)}</ul>
      <p>{model.status !== "unknown" && value.checks.policyVerified ? "Povinné kontroly splňují tuto revizi místních pravidel v uvedeném pozorování." : "Aktuální splnění povinných kontrol není potvrzeno."}</p>
      <div className="review-policy__row">{([ ["codeReview", "Review kódu"], ["planReview", "Review přijatého zadání"] ] as const).map(([key, label]) => <article key={key}><h4>{label}</h4>
        <p>{reviewLabels[value[key].status]} · minimum {value[key].minimum ?? "—"}</p><p>ID účtů: {value[key].reviewerIds.join(", ") || "žádná"}</p><p>ID review: {value[key].reviewIds.join(", ") || "žádná"}</p></article>)}</div>
      {!!value.blockers.length && <details open><summary>Důvody vyhodnocení</summary><ul>{value.blockers.map((reason, index) => <li key={index}><code>{reason}</code></li>)}</ul></details>}
    </>}
    <p>Splnění místních pravidel neprokazuje ochranu větve, identitu workflow, nezávislé osoby, nasazení ani nynější vzdálený stav. Neopravňuje k merge a neoznačuje kartu za dokončenou.</p>
  </section>;
}
