// Panel Trend ve Velínu: osm malých křivek souhrnných čísel za 14 dní (vzorky strážce `trend`). Řádek nese jméno,
// křivku, poslední hodnotu a rozdíl od prvního vzorku obarvený podle toho, zda jde k lepšímu. Jen se čte.
import { trendLines, type TrendSeries } from "../logic/velin-trend";

const WIDTH = 96;
const HEIGHT = 20;

export default function VelinTrend({ series }: { series: TrendSeries | null }) {
  if (!series) return null;
  const lines = trendLines(series, WIDTH, HEIGHT);
  const empty = lines.every(line => line.last === null);
  return (
    <section className="velin__trend" aria-label="Trend" data-oh-trend={empty ? "empty" : "ok"}>
      <header className="velin__trend-head"><b>Trend</b><small className="velin__muted">14 dní · vzorek po 15 min</small></header>
      {empty && <p className="velin__muted velin__trend-empty">Strážce trend zatím nevzal žádný vzorek.</p>}
      {!empty && <ul className="velin__trend-list">
        {lines.map(line => (
          <li key={line.id} className="velin__trend-row" data-oh-metric={line.id} data-oh-value={line.last ?? ""}>
            <span className="velin__trend-label">{line.label}</span>
            <svg className="velin__trend-spark" viewBox={`-1 -1 ${WIDTH + 2} ${HEIGHT + 2}`} width={WIDTH} height={HEIGHT} aria-hidden="true">
              {line.path && <path d={line.path} />}
            </svg>
            <b className="velin__trend-value">{line.last ?? "—"}</b>
            <small className={"velin__trend-delta velin__trend-delta--" + line.tone}>
              {line.delta ? (line.delta > 0 ? "+" : "") + line.delta : ""}
            </small>
          </li>
        ))}
      </ul>}
    </section>
  );
}
