import { checkLabels, evidenceReason, planReviewMarker, pullRequestLink, reviewLabels, type GitEvidenceItem } from "../logic/git-evidence";

export default function GitEvidenceDetails({ item, historical }: { item: GitEvidenceItem; historical: boolean }) {
  const { snapshot, evaluation } = item;
  const link = pullRequestLink(snapshot.configuredRepository, snapshot.pr?.number ?? snapshot.prNumber);
  return <section className="git-evidence__details" aria-label="Podrobnosti GitHub pozorování">
    <h3>{historical ? "Historický záznam" : "Vybrané pozorování"}</h3>
    <p>{link && <a href={link} target="_blank" rel="noopener noreferrer">Otevřít PR #{snapshot.pr?.number ?? snapshot.prNumber} na GitHubu</a>}</p>
    <dl className="git-evidence__identity">
      <dt>Čas pozorování</dt><dd>{new Date(snapshot.observedAt).toLocaleString("cs-CZ")}</dd>
      <dt>Revize zadání</dt><dd><code>{snapshot.acceptedRevision}</code></dd>
      <dt>Git SHA</dt><dd><code>{snapshot.pr?.headSha ?? "Při tomto pokusu nebylo ověřeno"}</code></dd>
    </dl>
    <p>Jde o historické pozorování, nikoli průběžně ověřovaný stav GitHubu ani oprávnění k merge.</p>
    {!snapshot.complete ? <p role="status" className="git-evidence__warning">GitHub pozorování není úplné. Review ani kontroly tímto pokusem nejsou doloženy. Pro další pokus znovu načtěte PR.</p> : <>
      {evaluation.freshness.status === "stale" && <p className="git-evidence__warning">Zastaralý podklad: přijatá revize zadání nebo poslední známé SHA tohoto PR se změnily.</p>}
      {evaluation.freshness.status === "unknown" && <p className="git-evidence__warning">Platnost kontextu pozorování není doložena.</p>}
      <div className="git-evidence__verdicts">
        <article><h4>Nezávislé review kódu</h4><strong>{reviewLabels[evaluation.codeReview.status]}</strong>
          <p>Jiný ověřený reviewer než autor PR, oprávnění k repozitáři a přesné SHA.</p></article>
        <article><h4>Review přijatého zadání</h4><strong>{reviewLabels[evaluation.planReview.status]}</strong>
          <p>Schválení musí v samotném review obsahovat přesnou značku této revize.</p>
          <p>Identita autora zadání zatím není propojena s GitHub účtem.</p></article>
        <article><h4>Pozorované kontroly</h4><strong>{checkLabels[evaluation.checks.status]}</strong>
          <p>Počet vyhodnocených kontrol: {evaluation.checks.observedCount ?? 0}. Politika povinných kontrol není ověřena.</p></article>
      </div>
      <p className="git-evidence__warning">Celkové ověření implementace není potvrzeno. Politika povinných kontrol a důvěryhodných poskytovatelů zatím není nastavena.</p>
      <details><summary>Jednotlivé výsledky z GitHubu</summary>
        {snapshot.checks === undefined || snapshot.statuses === undefined ? <p>Podrobné výsledky nejsou načteny. Přehled uvádí {snapshot.counts?.checks ?? "—"} kontrol a {snapshot.counts?.statuses ?? "—"} commit statusů.</p>
          : !(snapshot.checks.length || snapshot.statuses.length) && <p>Žádné kontroly ani commit statusy nebyly nalezeny.</p>}
        <ul>{snapshot.checks?.map(check => <li key={`check-${check.id}`}>{check.name} · aplikace {check.appId} · {check.status} / {check.conclusion ?? "bez výsledku"}</li>)}
          {snapshot.statuses?.map(status => <li key={`status-${status.id}`}>{status.context} · {status.state}</li>)}</ul>
      </details>
    </>}
    <label className="git-evidence__field">Značka zadání tohoto pozorování
      <input readOnly value={planReviewMarker(snapshot.project, snapshot.workspace, snapshot.acceptedRevision)} onFocus={event => event.currentTarget.select()} />
    </label>
    {!!evaluation.blockers.length && <ul className="git-evidence__reasons">{evaluation.blockers.map(reason => <li key={reason}>{evidenceReason(reason)}</li>)}</ul>}
  </section>;
}
