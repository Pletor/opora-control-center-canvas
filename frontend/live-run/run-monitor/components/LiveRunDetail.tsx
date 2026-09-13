import type { AgentRunDetail } from "@/live-run/run-monitor/logic/agent-types";

export type LivePane = "sessions" | "cost" | "memory" | "sources";
const text = (value: unknown) => typeof value === "string" || typeof value === "number" ? String(value) : "Nedostupné";
const number = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("cs-CZ") : "Nedostupné";
const money = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? `${value.toLocaleString("cs-CZ", { minimumFractionDigits: 2, maximumFractionDigits: 4 })} USD` : "Nedostupné";

export default function LiveRunDetail({ run, pane }: { run: AgentRunDetail; pane: LivePane }) {
  const telemetry = run.telemetry ?? [];
  return <section className="live-run-evidence" aria-label="Doložené údaje běhu">
    {pane === "sessions" && <>
      <dl className="live-identities"><dt>Relace</dt><dd>{run.sessionId ?? "Zdroj ji neposkytl"}</dd><dt>Rodičovská relace</dt><dd>{run.parentSessionId ?? "Zdroj ji neposkytl"}</dd>
        <dt>Worktrees</dt><dd>{run.worktrees?.length ? run.worktrees.map((path) => <code key={path}>{path}</code>) : "Nedostupné"}</dd>
        <dt>Větve</dt><dd>{run.branches?.join(", ") || "Nedostupné"}</dd><dt>Zdrojové cesty</dt><dd>{run.sourcePaths?.join(", ") || "Nedostupné"}</dd>
        <dt>Původ</dt><dd>{run.stateOrigin}</dd></dl>
      <div className="live-controls" aria-label="Možnosti relace">
        <button disabled title={run.capabilities?.btw?.reason ?? "Zdroj neposkytuje /btw transport."}>/btw</button>
        <button disabled title={run.capabilities?.fork?.reason ?? "Zdroj neposkytuje ověřený fork transport."}>Fork</button>
        <span className="muted">Nedostupné transporty nejsou simulované.</span>
      </div>
      {!!run.axis?.length && <><h4>Procesní osa · OporaCC</h4><ol className="live-axis">{run.axis.map((stage, index) => <li key={index}>
        <strong>{text(stage.label ?? stage.name ?? stage.kind)}</strong> · {text(stage.status)}
        <p>{text(stage.summary)}</p><code>{text(stage.source)}</code>
      </li>)}</ol></>}
      {telemetry.map((item) => <section key={item.runId}><h4>Bridge · {item.runId}</h4>
        <p>{item.available ? `${text(item.model?.name)} · ${text(item.state?.value)}` : item.error ?? "Telemetrie není dostupná"}</p>
        <ol>{item.tools?.map((tool, index) => <li key={index}><code>{tool.name}</code> · {tool.args_preview}<small>{tool.source} · {tool.at ?? "čas neznámý"}</small></li>)}</ol>
      </section>)}
    </>}
    {pane === "cost" && <><h4>Náklady vybraného běhu</h4>
      {!telemetry.length && <p>Zdroj neposkytl per-run náklady. Nedostupné neznamená nulové.</p>}
      {telemetry.map((item) => <section className="live-metric-card" key={item.runId}><h4>{item.runId}</h4>
        <dl><dt>Skutečná cena</dt><dd data-testid="run-actual-cost">{money(item.costs?.actual_usd)}</dd>
          <dt>Odhad zdroje</dt><dd>{money(item.costs?.estimated_usd)}</dd></dl>
        <p>{text(item.costs?.source)}</p><small>Zdrojový čas: {text(item.costs?.at)}</small>
      </section>)}
      {run.cost && <section className="live-metric-card"><h4>Celé OporaCC · denní účet (nikoli tento běh)</h4>
        <p>{run.cost.reliable ? money(run.cost.todayUsd) : "Nedostupné — Bridge nepotvrdil údaj"} / limit {money(run.cost.limitUsd)}</p><small>{run.cost.note}</small></section>}
    </>}
    {pane === "memory" && <><h4>Kontext a paměť vybrané relace</h4>
      <p>Kontextové tokeny nejsou dlouhodobá paměť. Zdroj persistentní paměť zatím neposkytuje.</p>
      {!telemetry.length && <p>Telemetrie kontextu není dostupná.</p>}
      {telemetry.map((item) => <section className="live-metric-card" key={item.runId}><h4>{item.runId}</h4>
        <dl><dt>Vstupní tokeny</dt><dd>{number(item.context?.input_tokens)}</dd><dt>Kontextové okno</dt><dd>{number(item.context?.context_window)}</dd>
          <dt>Podíl dle zdroje</dt><dd>{typeof item.context?.context_percent === "number" ? number(item.context.context_percent) + " %" : "Nedostupné"}</dd>
          <dt>Výstupní tokeny</dt><dd>{number(item.context?.output_tokens)}</dd></dl>
        <p>{text(item.context?.source)}</p><small>Zdrojový čas: {text(item.context?.at)}</small>
      </section>)}
      {run.brain && <p>Kontextový snímek harnessu: {run.brain.contextSnapshot}</p>}
    </>}
    {!!run.telemetryRemaining && <p className="warn-text">Zobrazeny nejvýše čtyři Bridge relace; dalších {run.telemetryRemaining} není načteno.</p>}
  </section>;
}
