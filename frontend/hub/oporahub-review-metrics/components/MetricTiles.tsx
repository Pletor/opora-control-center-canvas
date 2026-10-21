import type { Tile } from "../logic/review-metrics";

const GLYPH: Record<Tile["tone"], string> = { ok: "✓", warn: "◷", bad: "✕", gap: "◌", acc: "●" };
const WORD: Record<Tile["tone"], string> = { ok: "v pořádku", warn: "pozor", bad: "blokuje", gap: "bez dat", acc: "měření" };

/** Dlaždice: velké číslo, co znamená a značka se slovem; pojistka nad nulou je zlatá „pozor“. */
export default function MetricTiles({ title, tiles }: { title: string; tiles: Tile[] }) {
  return <section className="oporahub-review-metrics__panel" aria-label={title}>
    <h4 className="oporahub-review-metrics__subtitle">{title}</h4>
    <div className="oporahub-review-metrics__tiles">
      {tiles.map(tile => <div key={tile.metric} className={`oporahub-review-metrics__tile oporahub-review-metrics__tile--${tile.tone}`}
        data-oh-metric={tile.metric} data-oh-value={tile.raw ?? ""}>
        <span className="oporahub-review-metrics__tile-label">{tile.label}</span>
        <b className="oporahub-review-metrics__tile-value">{tile.value}</b>
        <span className="oporahub-review-metrics__tile-state"><span aria-hidden="true">{GLYPH[tile.tone]}</span> {WORD[tile.tone]}</span>
        <span className="oporahub-review-metrics__note">{tile.hint}</span>
      </div>)}
    </div>
  </section>;
}
