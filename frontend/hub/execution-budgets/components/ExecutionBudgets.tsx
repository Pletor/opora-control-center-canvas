import type { ExecutionBudgetsView } from "../logic/use-execution-budgets";
import type { BudgetLimits } from "../logic/execution-budgets";
import "../styles/execution-budgets.css";

const fields: { key: keyof BudgetLimits; label: string; min: number; max: number }[] = [
  { key: "maxRunSeconds", label: "Nejvyšší doba oprávnění běhu v sekundách", min: 30, max: 86400 },
  { key: "maxAttempts", label: "Nejvyšší počet pokusů", min: 1, max: 100 },
  { key: "maxRepairRounds", label: "Nejvyšší počet opravných kol", min: 0, max: 99 },
];
export default function ExecutionBudgets({ model }: { model: ExecutionBudgetsView }) {
  const { context, review } = model;
  return <section className="execution-budgets" aria-label="Omezení běhů agentů" aria-busy={model.busy}>
    <header className="execution-budgets__head"><div><h2>Omezení běhů agentů</h2><p>Čas oprávnění a počet spuštění pro konkrétní přijaté zadání. Nejde o peněžní ani tokenový rozpočet.</p></div>
      <button type="button" disabled={model.busy} onClick={model.refresh}>Obnovit pravidla a spotřebu</button></header>
    <label className="execution-budgets__field">Karta pro omezení běhů<select aria-label="Karta pro omezení běhů" value={model.nodeId} disabled={model.busy} onChange={event => model.select(event.target.value)}>
      {!model.choices.length && <option value="">Žádné dostupné karty</option>}{model.choices.map(node => <option value={node.id} key={node.id}>{node.name}</option>)}
    </select></label>
    {!model.nodeId && <p>Nejprve přijměte plán s kartou. Historické běhy odstraněných karet zůstávají v panelu výsledků.</p>}
    {model.busy && <p role="status">Načítám nebo ukládám omezení…</p>}
    {model.error && <p role="alert">{model.error}</p>}
    {context && <><p>Přijatá revize <code>{context.acceptedHead ?? "Zatím není přijata"}</code> · hlava pravidel <code>{context.policyHead ?? "Bez nastavení"}</code>.</p>
      {!context.canConfigure && <p>{context.unavailableReason}</p>}
      <p>{context.enrolled ? "Karta je trvale zařazena. Po nové revizi plánu musí člověk potvrdit její nová pravidla." : "Karta dosud není zařazena; starší protokol nemá pevný strop oprávnění běhu. První nastavení nelze vrátit k neomezenému protokolu."}</p>
      {context.blockedReason && <p className="execution-budgets__warning">Nový běh je blokován: {context.blockedReason}</p>}
      <dl className="execution-budgets__identity"><dt>Pokusy spotřebovány / zbývají</dt><dd>{context.attemptsUsed} / {context.remainingAttempts ?? "Limit není nastaven"}</dd>
        <dt>Opravy spotřebovány / zbývají</dt><dd>{context.repairRoundsUsed} / {context.remainingRepairRounds ?? "Limit není nastaven"}</dd>
        <dt>Rodina přijatého zadání</dt><dd><code>{context.family?.id ?? "Zatím nezaložena"}</code></dd>
        <dt>Poslední běh rodiny</dt><dd><code>{context.latestExecutionId ?? "Žádný"}</code></dd></dl>
      {context.policy && <p>Platné limity: {context.policy.limits.maxRunSeconds} sekund na běh · {context.policy.limits.maxAttempts} pokusů · {context.policy.limits.maxRepairRounds} oprav.</p>}
    </>}
    <fieldset className="execution-budgets__form" disabled={model.disabled}><legend>Nová neměnná revize pravidel</legend>
      {fields.map(field => <label className="execution-budgets__field" key={field.key}>{field.label}<input type="number" step="1" min={field.min} max={field.max} value={Number.isNaN(model.limits[field.key]) ? "" : model.limits[field.key]} onChange={event => model.edit(field.key, event.target.value === "" ? NaN : Number(event.target.value))} /></label>)}
      <button type="button" onClick={model.prepare}>Zkontrolovat omezení běhů</button>
    </fieldset>
    {review && <section className="execution-budgets__confirmation" aria-label="Potvrzení omezení běhů"><h3>Potvrzení přesné revize</h3>
      <p>Karta <code>{review.payload.nodeId}</code> · plán <code>{review.payload.expectedAcceptedHead}</code> · předchozí pravidla <code>{review.payload.expectedPolicyHead ?? "První zařazení"}</code>.</p>
      <p>{review.payload.limits.maxRunSeconds} sekund na běh, celkem {review.payload.limits.maxAttempts} pokusů a {review.payload.limits.maxRepairRounds} opravných kol.</p>
      <p>Spotřebované pokusy se nevracejí po selhání, uvolnění ani zrušení. Změna pravidel neprodlouží existující běh. Snížení pod spotřebu nepovolí další spuštění.</p>
      <label><input type="checkbox" checked={model.confirmed} disabled={model.disabled} onChange={event => model.confirm(event.target.checked)} /> Potvrzuji trvalé zařazení karty, přesnou revizi a tyto limity.</label>
      <button type="button" disabled={model.disabled || !model.confirmed} onClick={model.save}>Potvrdit omezení běhů</button><button type="button" disabled={model.busy} onClick={model.cancel}>Zrušit potvrzení</button>
    </section>}
    <p>Odebrané oprávnění není důkaz ukončení všech procesů. Agent Office žádá zastavení pracovníka; karta, review ani nasazení se tím nepotvrzují.</p>
    <details><summary>Historie lidských pravidel · {model.history.length} záznamů</summary>{model.history.map(policy => <article className="execution-budgets__history" key={policy.id}>
      <h3>Pravidla <code>{policy.id}</code></h3><p>Plán <code>{policy.acceptedRevision}</code> · rodič <code>{policy.parentPolicyHead ?? "První zařazení"}</code>.</p>
      <p>{policy.limits.maxRunSeconds} sekund · {policy.limits.maxAttempts} pokusů · {policy.limits.maxRepairRounds} oprav.</p><p>{policy.by.name} · {policy.createdAt}</p>
    </article>)}</details>
    {model.ledger && <details><summary>Spotřeba a zrušení · načteno {model.ledger.allocations.length} alokací / {model.ledger.cancellations.length} zrušení</summary>
      <p>Každá historie obsahuje nejvýše 100 záznamů; nejde o celkovou spotřebu rodiny. Autoritativní počty jsou v aktuálním kontextu výše.</p>
      <h3>Alokace pokusů</h3>{model.ledger.allocations.map((entry, index) => <pre key={typeof entry.id === "string" ? entry.id : index}>{JSON.stringify(entry, null, 2)}</pre>)}
      <h3>Lidská zrušení</h3>{model.ledger.cancellations.map((entry, index) => <pre key={typeof entry.id === "string" ? entry.id : index}>{JSON.stringify(entry, null, 2)}</pre>)}
    </details>}
  </section>;
}
