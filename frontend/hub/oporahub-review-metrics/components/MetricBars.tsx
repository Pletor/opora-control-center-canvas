import type { CSSProperties } from "react";
import type { Bar } from "../logic/review-metrics";

/** Vodorovné pruhy: délka vůči největší hodnotě skupiny, číslo a slovo vždy vedle pruhu (barva není jediný nosič). */
export default function MetricBars({ title, bars }: { title: string; bars: Bar[] }) {
  return <section className="oporahub-review-metrics__panel" aria-label={title}>
    <h4 className="oporahub-review-metrics__subtitle">{title}</h4>
    <ul className="oporahub-review-metrics__bars">
      {bars.map(bar => <li key={bar.metric} className="oporahub-review-metrics__bar-row" data-oh-metric={bar.metric} data-oh-value={bar.value}>
        <span className="oporahub-review-metrics__bar-label">{bar.label}</span>
        <span className="oporahub-review-metrics__bar-track" aria-hidden="true">
          <i className={`oporahub-review-metrics__bar oporahub-review-metrics__bar--${bar.tone}`} style={{ "--oh-pct": `${bar.pct}%` } as CSSProperties} />
        </span>
        <b className="oporahub-review-metrics__bar-value">{bar.value}</b>
      </li>)}
    </ul>
  </section>;
}
