import { readSteps } from "../../spec-tab/logic/spec-diff";
import type { CardData } from "../../logic/use-card-data";
import { stepFill } from "../logic/step-fill";
import { afterMergeNotice, parseAfterMerge } from "../../logic/card-dod";
import { STEP_GLYPH as GLYPH, STEP_WORD as WORD, stepClass, stepColumns, stepProgress, stepRows, type StepRow } from "../logic/step-status";
import "../styles/steps-tab.css";


function StepItem({ row }: { row: StepRow }) {
  const evidence = row.result?.evidence;
  return <li className={`steps-tab__step steps-tab__step--${stepClass(row.status)}`} data-oh-plan-step={row.id} data-oh-step-status={row.status}
    data-oh-step-current={String(row.isCurrent)} data-oh-depends-on={row.dependsOn.join(",")} data-oh-order={row.order}>
    <details open={row.isCurrent}>
      <summary className="steps-tab__summary">
        <span className="steps-tab__glyph" aria-label={WORD[row.status]}>{GLYPH[row.status]}</span>
        <code className="steps-tab__id">{row.id}</code>
        <b className="steps-tab__title">{row.title}{row.status === "after_merge" && <span className="steps-tab__badge" title="Krok přibyl do zadání po sloučení PR; uznalo ho sloučení, žádný běh ho nedoložil.">po sloučení</span>}</b>
        {row.kind && <span className="steps-tab__kind">{row.kind}</span>}
        <span className="steps-tab__count">{row.acceptanceMet}/{row.acceptance.length}</span>
        <span className="steps-tab__deps">{row.dependsOn.length ? `závisí na ${row.dependsOn.join(", ")}` : "bez závislostí"}
          {row.isCurrent && row.result === null ? " · aktuální krok" : ""}{row.blockedBy.length && row.status === "waiting" ? ` · čeká na ${row.blockedBy.join(" + ")}` : ""}</span>
      </summary>
      <ul className="steps-tab__checks" aria-label={`Akceptace kroku ${row.id}`}>
        {row.acceptance.map((text, index) => <li key={index} data-oh-step-acceptance={index} data-oh-met={String(row.status === "done")}
          className={row.status === "done" ? "steps-tab__check steps-tab__check--met" : "steps-tab__check"}>
          <span aria-hidden="true">{row.status === "done" ? "✓" : "○"}</span>{text}</li>)}
      </ul>
      {evidence && <p className="steps-tab__evidence" data-oh-step-evidence={row.id}>
        {evidence.notes || "bez poznámky"}{evidence.checks.length ? ` · kontroly ${evidence.checks.join(", ")}` : ""}
        {evidence.commits.length ? ` · ${evidence.commits.map(sha => sha.slice(0, 7)).join(", ")}` : ""}</p>}
      {row.files.length > 0 && <p className="steps-tab__files">{row.files.join(" · ")}</p>}
    </details>
  </li>;
}

/** Záložka Kroky: postup, náhled DAG závislostí a seznam kroků s akceptací; změna kroků jde přes Zadání. */
export default function StepsTab({ data, onEditSteps }: { data: CardData; onEditSteps: () => void }) {
  const accepted = readSteps(data.accepted?.fields ?? null);
  const working = readSteps(data.working?.fields ?? null);
  const steps = accepted ?? working;
  const rows = steps ? stepRows(steps, data.stepResults, data.card?.steps?.current ?? null) : [];
  const progress = stepProgress(rows);
  const columns = stepColumns(rows);
  const fill = stepFill(rows);
  const next = rows.find(row => row.status === "waiting");
  const notice = afterMergeNotice(parseAfterMerge(data.card?.dod));
  return <div className="steps-tab" data-oh-view="card-steps" data-oh-steps-total={progress.total} data-oh-steps-done={progress.done}
    data-oh-steps-current={progress.current?.id ?? ""} data-oh-steps-source={accepted ? "accepted" : working ? "working" : "none"}>
    {!steps ? <p className="steps-tab__empty" data-oh-steps="missing">◌ Karta nemá kroky plánu. {data.accepted || data.working
      ? "Server kroky zatím nevydává, nebo je zadání ještě nemá; přidají se návrhem změny zadání (pole steps)." : "Kontext zadání není dostupný."}</p> : <>
      <div className="steps-tab__head">
        <b>Postup <span className="steps-tab__muted">{progress.done}/{progress.total}</span></b>
        <span className="steps-tab__muted">{accepted ? "přijatý plán" : "jen pracovní návrh"} · DAG kroků</span>
      </div>
      <div className={`steps-tab__fill steps-tab__fill--${fill.severity}`} role="progressbar" aria-label="Hotové kroky" aria-valuemin={0} aria-valuemax={100}
        aria-valuenow={fill.percent} aria-valuetext={`${progress.done} z ${progress.total} kroků${fill.severity === "error" ? ", krok selhal" : fill.severity === "warn" ? (notice ? ", část uznalo sloučení" : ", krok přeskočen") : ""}`}>
        <i style={{ width: `${fill.percent}%` }} />
      </div>
      {notice && <p className="steps-tab__notice" role="note" data-oh-steps-after-merge="true">{notice}</p>}
      <div className="steps-tab__bar" aria-hidden="true">{rows.map(row => <i key={row.id} className={`steps-tab__seg steps-tab__seg--${stepClass(row.status)}`} />)}</div>
      <div className="steps-tab__dag" aria-label="Závislosti kroků (sloupec = hloubka v DAG)">
        {columns.map((column, index) => <div key={index} className="steps-tab__col">
          {column.map(row => <span key={row.id} className={`steps-tab__node steps-tab__node--${stepClass(row.status)}`} title={row.title}>{row.id}</span>)}
        </div>)}
        <span className="steps-tab__muted steps-tab__legend">dependsOn →</span>
      </div>
      <ol className="steps-tab__list">{rows.map(row => <StepItem key={row.id} row={row} />)}</ol>
      {!data.card?.steps?.items.length && !data.receipts.length && <p className="steps-tab__muted">Stav kroků se skládá z výsledků všech běhů karty; karta zatím žádný výsledek nemá.</p>}
    </>}
    <div className="steps-tab__foot">
      <span><b>{progress.current ? `Další: ${progress.current.id} ${progress.current.title}` : progress.total && progress.done === progress.total ? (rows.some(row => row.status === "after_merge") ? "Kroky uzavřelo sloučení, část mimo standardní proces" : "Všechny kroky hotové") : "Žádný aktivní krok"}</b>
        {next && <span className="steps-tab__muted"> · {next.id} čeká{next.blockedBy.length ? ` na ${next.blockedBy.join(" + ")}` : ""}</span>}</span>
      <button type="button" className="steps-tab__button" onClick={onEditSteps} data-oh-action="steps.propose">Navrhnout změnu kroků</button>
    </div>
  </div>;
}
