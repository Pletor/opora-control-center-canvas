import type { DetailTarget } from "@/hub/oporahub-overview/logic/overview";
import { useCopyText } from "@/shared/hooks/logic/use-copy-text";
import { processEndpoint, processPresentation, type ProcessSnapshot } from "../logic/process-sync";
import { useProcessSync } from "../logic/use-process-sync";
import "../styles/process-sync.css";

type Props = { project: string; workspace: string; open: (target: DetailTarget) => void; onImprove: (nodeId: string, name: string) => void };
export default function ProcessSync({ project, workspace, open, onImprove }: Props) {
  const model = useProcessSync(project, workspace);
  return <ProcessSyncView {...model} project={project} workspace={workspace} open={open} onImprove={onImprove} />;
}
export function ProcessSyncView({ snapshot, busy, error, refresh, project, workspace, open, onImprove }: Props & {
  snapshot: ProcessSnapshot | null; busy: boolean; error: string; refresh: () => void;
}) {
  const copy = useCopyText(), endpoint = processEndpoint(project, workspace);
  return <section className="process-sync" aria-label="Proces Control Center" aria-busy={busy}>
    <header className="process-sync__header"><div><h2>Proces Control Center</h2><p>Od přijatého plánu přes práci k nezávislé kontrole.</p></div>
      <button type="button" onClick={refresh} disabled={busy || !project || !workspace}>Obnovit proces</button></header>
    <p className="process-sync__observation">{snapshot ? <>Poslední pozorování: <time dateTime={snapshot.observedAt}>{new Date(snapshot.observedAt).toLocaleString("cs-CZ")}</time> · přijatá revize <code>{snapshot.acceptedRevision?.slice(0, 12) ?? "nezaložena"}</code></>
      : busy ? "Načítám aktuální podklady…" : "Aktuální pozorování není doloženo."} · Obnova po 15 s jen při viditelném přehledu.</p>
    {error && <p className="process-sync__error" role="alert">{error} Předchozí výsledek není vydáván za aktuální.</p>}
    {snapshot && <><p className="process-sync__limits">{snapshot.items.length} z {snapshot.totalCards} karet{snapshot.truncated ? " · omezený výřez, nejvýše 100" : ""}. Nahlášení není ověření, merge ani nasazení.</p>
      <div className="process-sync__cards">{snapshot.items.map(card => {
        const shown = processPresentation(card);
        return <article className="process-sync__card" key={card.nodeId}>
          <div className="process-sync__identity"><strong>{card.name}</strong><code>{card.nodeId}</code>
            <span className={`process-sync__state process-sync__state--${shown.tone}`}>{shown.label}</span></div>
          <div className="process-sync__progress"><span>Pipeline: {card.pipeline.passedCount}/{card.pipeline.stageCount} · chyby {card.pipeline.failedCount}</span>
            {card.pipeline.currentStage && <span>Aktuální krok: {card.pipeline.currentStage}</span>}
            <span>{card.workingMatchesAccepted ? "Pracovní zadání odpovídá přijatému" : "Pracovní zadání se liší / přijetí není doloženo"}</span>
            {card.currentExecution && <span>Běh {card.currentExecution.id.slice(0, 8)} · {card.currentExecution.results} výsledků · {card.currentExecution.matchesCurrentRevision ? "aktuální revize" : "historická revize"}</span>}
            {card.openIdeas > 0 && <span>Otevřené podněty: {card.openIdeas}</span>}</div>
          <div className="process-sync__action"><strong>{card.nextAction.label}</strong><p>{card.nextAction.reason}</p>
            <button type="button" onClick={() => open(shown.target)}>Otevřít další krok</button>
            <button type="button" onClick={() => onImprove(card.nodeId, card.name)}>Navrhnout zlepšení</button></div>
        </article>;
      })}</div>
      {!snapshot.items.length && <p>V tomto pracovním prostoru nejsou karty v aktuálním výřezu.</p>}
      <p className="process-sync__tracking">GitHub sledování prostoru: {snapshot.githubTracking.items.length} na načtené stránce{snapshot.githubTracking.truncated ? " · výřez omezen" : ""}. Vazby nejsou automaticky přiřazené kartám.
        <button type="button" onClick={() => open({ kind: "tracking", title: "Sledování pracovního prostoru" })}>Sledování</button>
        <button type="button" onClick={() => open({ kind: "evidence", title: "Nezávislé důkazy" })}>Důkazy</button></p>
      {(snapshot.githubTracking.items.length > 0 || snapshot.githubTracking.reviews.length > 0) && <details className="process-sync__tracking"><summary>Poslední podklady GitHubu · prostor, nikoli přiřazení kartám</summary>
        {snapshot.githubTracking.items.slice(0, 3).map(item => <p key={item.bindingId}>Sledování {item.bindingId.slice(0, 8)} · PR {item.observedPrState ?? "nedoloženo"} · kontrola {item.reviewStatus ?? "nedoložena"} · {item.matchesCurrentRevision ? "aktuální revize" : "historická revize"}</p>)}
        {snapshot.githubTracking.reviews.slice(0, 3).map(item => <p key={item.evidenceId}>Důkaz {item.evidenceId.slice(0, 8)} · kód: {item.codeReview} · plán: {item.planReview} · aktuálnost: {item.freshness} · {item.matchesCurrentRevision ? "aktuální revize" : "historická revize"}</p>)}
        <p>Nejvýše 3 sledování a 3 review z načteného výřezu; úplné podklady otevřete tlačítky výše.</p></details>}</>}
    <div className="process-sync__api"><label>Čtecí API pro agenty<textarea ref={copy.fieldRef} readOnly value={`GET ${endpoint}`} rows={2} /></label>
      <button type="button" onClick={() => void copy.copy(`GET ${endpoint}`)}>Kopírovat API procesu</button>
      {copy.status !== "idle" && <span role={copy.status === "failed" ? "alert" : "status"}>{copy.status === "copied" ? "API zkopírováno" : "Označte a zkopírujte API ručně."}</span>}</div>
  </section>;
}
