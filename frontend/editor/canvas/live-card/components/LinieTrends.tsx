import type { LiveCard, LiveLinie } from "../logic/live-card-types";
import { costSeries, sourcePath, sparkPoints, testSeries, usd } from "../logic/live-card-view";

const AXIS_TONE: Record<string, string> = { ok: "ok", done: "ok", green: "ok", wait: "wait", pending: "wait", bad: "bad", failed: "bad", red: "bad" };

/** Linie: kde je úkol (osy), větev, PR, commity a mezery mezi plánem a kódem. */
function LinieBox({ linie }: { linie: LiveLinie }) {
  return <section className="live-card__box">
    <h3 className="live-card__h">Linie<small className="live-card__h-meta">{[linie.mark || linie.ticketId, linie.branch, linie.pr != null ? `PR #${linie.pr}` : ""].filter(Boolean).join(" · ")}</small></h3>
    {linie.axes.length > 0 && <div className="live-card__chips">
      {linie.axes.map(axis => <span key={axis.name} className={`live-card__chip live-card__chip--${AXIS_TONE[axis.state] ?? "plain"}`} title={axis.text}>{axis.name}{axis.text ? ` · ${axis.text}` : ""}</span>)}
    </div>}
    {linie.commits.length > 0 && <ul className="live-card__commits">
      {linie.commits.map(commit => <li key={commit.sha7} className="live-card__commit"><code className="live-card__sha">{commit.sha7}</code>{commit.title}</li>)}
    </ul>}
    {linie.gaps.length > 0 && <div className="live-card__alert">Mezery: {linie.gaps.join(", ")}</div>}
    <div className="live-card__src">zdroj: <b className="live-card__src-url" title={linie.source}>{sourcePath(linie.source)}</b></div>
  </section>;
}

/** Testy a cena napříč běhy: dvě tenké křivky, ať je vidět trend, ne jednotlivé číslo. */
function TrendsBox({ runs, cost }: { runs: LiveCard["runs"]; cost: LiveCard["cost"] }) {
  const tests = sparkPoints(testSeries(runs)), spend = sparkPoints(costSeries(runs));
  if (!tests && !spend) return null;
  return <section className="live-card__box">
    <h3 className="live-card__h">Testy a cena napříč běhy<small className="live-card__h-meta">{runs.length} běhů</small></h3>
    {tests && <svg className="live-card__spark live-card__tone--real" viewBox="0 0 300 44" preserveAspectRatio="none" role="img" aria-label="Podíl prošlých testů po bězích"><polyline className="live-card__spark-line" points={tests} /></svg>}
    {spend && <svg className="live-card__spark live-card__tone--vision" viewBox="0 0 300 44" preserveAspectRatio="none" role="img" aria-label="USD na běh"><polyline className="live-card__spark-line" points={spend} /></svg>}
    <div className="live-card__src">zelená testy · oranžová USD na běh{cost?.totalUsd != null ? ` · celkem ${usd(cost.totalUsd)}` : ""}{cost?.budgetUsd != null ? ` / rozpočet ${usd(cost.budgetUsd)}` : ""}</div>
  </section>;
}

export default function LinieTrends({ card }: { card: LiveCard }) {
  const trends = sparkPoints(testSeries(card.runs)) || sparkPoints(costSeries(card.runs));
  if (!card.linie && !trends) return null;
  return <div className="live-card__row">
    {card.linie && <LinieBox linie={card.linie} />}
    {trends && <TrendsBox runs={card.runs} cost={card.cost} />}
  </div>;
}
