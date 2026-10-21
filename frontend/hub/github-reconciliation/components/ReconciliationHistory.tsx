import type { GithubReconciliationView } from "../logic/use-github-reconciliation";
import { displayTime } from "../logic/reconciliation";

const labels: Record<string, string> = { binding: "Založení vazby", control: "Změna řízení", observation: "Pozorování", event: "Změna pozorovaného stavu",
  id: "ID", acceptedRevision: "Přijatá revize", createdAt: "Založeno", action: "Akce", generation: "Generace", enabled: "Zapnuto", by: "Autor",
  repository: "Repozitář", pr: "PR", enrolledHeadSha: "Zdrojová hlava při založení", identityEvidenceId: "Důkaz identity", intervalSeconds: "Interval v sekundách",
  state: "Stav", errorCode: "Důvod", observationId: "ID pozorování", data: "Obsah pozorování", fromState: "Před změnou", toState: "Po změně",
  headSha: "Zdrojová hlava SHA", mergeCommitSha: "Merge commit SHA", mergedAt: "Čas sloučení", observedFrom: "Čtení od", observedUntil: "Čtení do" };
const fields = ["id", "acceptedRevision", "createdAt", "action", "generation", "enabled", "by", "repository", "pr", "enrolledHeadSha", "identityEvidenceId", "intervalSeconds", "state", "errorCode", "observationId", "data", "fromState", "toState"];
function Value({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span>Není doloženo</span>;
  if (Array.isArray(value)) return <ul>{value.map((item, index) => <li key={index}><Value value={item} /></li>)}</ul>;
  if (typeof value === "object") return <dl className="github-reconciliation__record">{Object.entries(value).map(([key, item]) => <div key={key}><dt>{labels[key] ?? key}</dt><dd><Value value={item} /></dd></div>)}</dl>;
  return <span>{typeof value === "boolean" ? value ? "Ano" : "Ne" : String(value)}</span>;
}
export default function ReconciliationHistory({ model }: { model: GithubReconciliationView }) {
  if (!model.selected) return null;
  const { history } = model;
  return <section className="github-reconciliation__history" aria-label="Historie trvalého sledování"><h3>Historie vazby a pokusů</h3>
    <p>Neměnné záznamy jsou od nejstaršího. Další stránky se načítají výslovně; opakované pozorování stejného sloučení nevytváří další merge událost.</p>
    {history.error && <p role="alert">{history.error}</p>}
    {history.busy && <p role="status">Načítám historii…</p>}
    {history.items.map(item => <details key={`${item.kind}:${String(item.record.id)}`} className="github-reconciliation__history-entry"><summary>{labels[item.kind] ?? item.kind} · <code>{String(item.record.id ?? "")}</code></summary>
      <dl className="github-reconciliation__record">{fields.filter(field => field in item.record).map(field => <div key={field}><dt>{labels[field] ?? field}</dt><dd><Value value={item.record[field]} /></dd></div>)}</dl>
    </details>)}
    <h4>Pokusy serverového procesu</h4>
    {!history.attempts.length && !history.busy && <p>Zatím nejsou načtené žádné pokusy.</p>}
    <ul>{history.attempts.map(item => <li key={item.id}><code>{item.id}</code> · {item.state} · {displayTime(item.startedAt)} — {displayTime(item.finishedAt)}
      {item.errorCode && <> · <code>{item.errorCode}</code></>}{item.observationId && <> · pozorování <code>{item.observationId}</code></>}</li>)}</ul>
    <button type="button" disabled={history.busy || !history.nextCursor && !history.nextAttemptCursor} onClick={history.more}>Načíst další stránku historie</button>
  </section>;
}
