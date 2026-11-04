import { pretty, routeText, verdict, type SimulateResponse, type TraceStep } from "../logic/play-trace";

type Props = { response: SimulateResponse; step: TraceStep | null; index: number; name: (nodeId: string) => string };

const Block = ({ title, children, tone }: { title: string; children: string; tone?: "error" | "branch" }) =>
  <section className={`flow-play-panel__block${tone ? ` flow-play-panel__block--${tone}` : ""}`}><h4 className="flow-play-panel__key">{title}</h4><pre className="flow-play-panel__value">{children}</pre></section>;

/** Panel „Co se stalo“ u právě přehrávaného kroku: vstup → pravidlo → výstup, větev, chyba a poznámka (notifikace).
 * Na posledním kroku pod tím stojí souhrn případu: výsledek, trasa a shoda s `expect` s rozdíly česky. */
export default function FlowPlayPanel({ response, step, index, name }: Props) {
  const last = index >= response.trace.length - 1, end = verdict(response);
  return <aside className="flow-play-panel" aria-label="Co se stalo" data-testid="flow-play-panel">
    <h3 className="flow-play-panel__title">Co se stalo</h3>
    {step ? <>
      <p className="flow-play-panel__step" data-testid="flow-play-step"><b>{index + 1}. {name(step.nodeId)}</b><small className="flow-play-panel__muted">{step.layer} · {step.type}</small></p>
      <Block title="Vstup">{pretty(step.in)}</Block>
      {step.rule && <Block title="Pravidlo">{step.rule}</Block>}
      <Block title="Výstup">{pretty(step.out)}</Block>
      {step.branch && <Block title="Větev" tone="branch">{step.branch}</Block>}
      {step.error && <Block title="Chyba" tone="error">{step.error}</Block>}
      {step.note && <Block title="Poznámka">{step.note}</Block>}
    </> : <p className="flow-play-panel__muted">Trasa je prázdná.</p>}
    {last && <section className="flow-play-panel__summary" data-testid="flow-play-summary">
      <h4 className="flow-play-panel__key">Souhrn případu</h4>
      <p className={`flow-play-panel__verdict flow-play-panel__verdict--${end.tone}`} data-testid="flow-play-verdict">{end.text}</p>
      {response.expect && !response.expect.ok && <ul className="flow-play-panel__diffs">{response.expect.diffs.map((diff) => <li key={diff}>{diff}</li>)}</ul>}
      <Block title="Výsledek">{pretty(response.result) || "—"}</Block>
      <Block title="Trasa">{routeText(response.trace) || "—"}</Block>
    </section>}
  </aside>;
}
