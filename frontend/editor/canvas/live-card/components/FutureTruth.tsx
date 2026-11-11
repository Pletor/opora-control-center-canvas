// Budoucnost po sloučení (F4) na líci živé karty: co udělá sloučení otevřené práce. Nahoře verdikt slovem,
// pod ním každá větev: kam míří, kolik souborů mění a co tím zasáhne. Konflikt je červeně, dopad a překryv
// čekají modře; seznam změněných souborů je v `title` (je ho moc na líc).
import type { FutureTruth as Future } from "../logic/live-card-types";
import { czechCount } from "@/project/architecture-editor/page-editor/layout-canvas/logic/czech-count";
import { futureLines, futureVerdict, markOfStatus } from "../logic/live-card-view";

export default function FutureTruth({ future }: { future: Future }) {
  const verdict = futureVerdict(future.verdict);
  return <section className="live-card__truth live-card__tone--future" data-oh-future={future.verdict}>
    <h3 className="live-card__h">Budoucnost<small className={`live-card__h-meta live-card__item--${verdict.status}`}>{verdict.label}</small></h3>
    {future.works.map(work => <div key={work.branch} className="live-card__future-work">
      <div className="live-card__code" title={work.changed.join("\n")}>{work.mark ?? work.branch} → {work.target} · {czechCount(work.changed.length, ["soubor", "soubory", "souborů"])}</div>
      <ul className="live-card__list">
        {futureLines(work).map((line, index) => <li key={index} className={`live-card__item live-card__item--${line.status}`} title={line.title}>
          <b className="live-card__mark">{markOfStatus(line.status)}</b><span className="live-card__item-text">{line.text}</span>
        </li>)}
      </ul>
    </div>)}
  </section>;
}
