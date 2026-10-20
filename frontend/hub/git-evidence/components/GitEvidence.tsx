import type { GitEvidenceView } from "../logic/use-git-evidence";
import { planReviewMarker } from "../logic/git-evidence";
import GitEvidenceDetails from "./GitEvidenceDetails";
import "../styles/git-evidence.css";

export default function GitEvidence({ model }: { model: GitEvidenceView }) {
  const context = model.context;
  const latestFailed = context?.items[0]?.snapshot.complete === false;
  return <section className="git-evidence" aria-label="GitHub důkazy" aria-busy={model.busy}>
    <header className="git-evidence__head"><div><h2>GitHub důkazy</h2>
      <p>GitHub review a kontroly pro konkrétní zadání a commit.</p></div>
      <button type="button" disabled={model.busy} onClick={model.refresh}>Obnovit uloženou historii</button>
    </header>
    {model.busy && <p role="status">Načítám pozorování…</p>}
    {model.error && <p role="alert" className="git-evidence__warning">{model.error}</p>}
    {model.notice && <p role="status">{model.notice}</p>}
    {(latestFailed || model.failedAttempt) && <p className="git-evidence__warning">Poslední pokus nebyl úplně ověřen. Starší záznamy níže jsou pouze historické podklady, nikoli potvrzení aktuálního stavu.</p>}
    {context && <>
      <p>Repozitář: <strong>{context.repository ?? "GitHub není připojen"}</strong></p>
      <p>Přijatá revize zadání: <code className="git-evidence__hash">{context.acceptedHead ?? "zatím nezaložena"}</code></p>
      {!context.available && <p>{context.unavailableReason || "Tento projekt zatím nemá dostupné propojení s GitHubem."}</p>}
      {context.available && <div className="git-evidence__import">
        {!context.acceptedHead && <p>Nejprve přijměte výchozí zadání v části Změny zadání.</p>}
        <label className="git-evidence__field">Číslo pull requestu
          <input inputMode="numeric" value={model.prNumber} maxLength={16} disabled={model.busy || !context.acceptedHead}
            onChange={event => model.setPrNumber(event.target.value)} placeholder="Například 10" />
        </label>
        <button type="button" disabled={model.busy || !context.acceptedHead || !model.prNumber.trim()} onClick={model.observe}>Načíst nové pozorování z GitHubu</button>
        <p>Načtení pouze čte GitHub. Review se neodesílá a pull request se neslučuje.</p>
      </div>}
      {context.acceptedHead && <div className="git-evidence__marker">
        <label className="git-evidence__field">Značka aktuálního zadání pro samostatný řádek v review
          <input readOnly value={planReviewMarker(model.project, model.workspace, context.acceptedHead)} onFocus={event => event.currentTarget.select()} />
        </label><p>Označte a zkopírujte celý řádek. Reviewer jej přidá do svého schválení na GitHubu; značka pouze v popisu PR nestačí.</p>
      </div>}
    </>}
    <h3>Uložená pozorování</h3><p>Nejvýše 100 posledních záznamů. Obnova historie nečte GitHub; nové pozorování načtěte tlačítkem výše.</p>
    {!model.items.length && <p>Zatím nejsou uloženy žádné GitHub důkazy.</p>}
    <ul className="git-evidence__list">{model.items.map((item, index) => <li key={item.snapshot.id}>
      <button type="button" onClick={() => model.select(item.snapshot.id)} disabled={model.busy} aria-pressed={model.selected?.snapshot.id === item.snapshot.id}>
        PR #{item.snapshot.pr?.number ?? item.snapshot.prNumber} · {item.snapshot.complete ? "Pozorování" : "Neúspěšný pokus"}
      </button><span>{new Date(item.snapshot.observedAt).toLocaleString("cs-CZ")}{index === 0 ? " · nejnovější uložený záznam" : " · historie"}</span>
    </li>)}</ul>
    {model.detailBusy && <p role="status">Načítám podrobnosti vybraného pozorování…</p>}
    {model.detailError && <p role="alert" className="git-evidence__warning">Podrobnosti se nepodařilo načíst: {model.detailError}. Obnovte historii pro další pokus.</p>}
    {model.selected && <GitEvidenceDetails item={model.selected} historical={model.selected.snapshot.id !== model.items[0]?.snapshot.id || model.failedAttempt} />}
  </section>;
}
