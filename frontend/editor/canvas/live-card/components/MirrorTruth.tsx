// Zrcadlo kódu (F1) na líci živé karty: co z karty kód opravdu má. Shoda je ručně „fixou“ se soubor:řádek pod ní,
// chybějící je šedý kroužek, navíc červeně. Náhled souboru aplikace zatím nemá, plná cesta je v `title`.
import { useState } from "react";
import type { MirrorTruth as Mirror } from "../logic/live-card-types";
import { mirrorBar, mirrorPlace, mirrorShown, sourcePath } from "../logic/live-card-view";

export default function MirrorTruth({ mirror }: { mirror: Mirror }) {
  const fill = mirrorBar(mirror);
  const [all, setAll] = useState(false);
  const { shown, rest } = mirrorShown(mirror.items, 12, all);
  return <section className="live-card__truth live-card__tone--mirror" data-oh-mirror={`${mirror.counts.matched}/${mirror.counts.missing}/${mirror.counts.extra}`}>
    <h3 className="live-card__h">Zrcadlo kódu<small className="live-card__h-meta" title={mirror.evidence?.at}>{mirror.evidence?.commit.slice(0, 7) ?? ""}</small></h3>
    <ul className="live-card__list">
      {shown.map((item, index) => <li key={index} className={`live-card__item live-card__item--${item.status}`} title={[mirrorPlace(item), item.text].filter(Boolean).join(" · ")}>
        {item.status === "ok" ? <><b className="live-card__mark">✓</b><span className="live-card__item-text">
          <span className="live-card__ink">{item.name}</span><br /><span className="live-card__code">{mirrorPlace(item)}</span></span></>
          : item.status === "bad" ? <><b className="live-card__mark">+</b><span className="live-card__code live-card__item-text">{item.path || item.name} · navíc</span></>
          : <><b className="live-card__mark">○</b><span className="live-card__code live-card__item-text">{item.name}</span></>}
      </li>)}
    </ul>
    {(rest > 0 || all) && <button type="button" className="live-card__more" onClick={() => setAll(!all)}>{all ? "méně" : `+ ${rest} dalších`}</button>}
    {fill && <div className="live-card__bar">shoda<i className="live-card__bar-track"><i className="live-card__bar-fill" style={{ width: `${fill.pct}%` }} /></i><em className="live-card__bar-value">{fill.done}/{fill.total}</em></div>}
    <div className="live-card__src">zdroj: <b className="live-card__src-url" title={mirror.source}>{sourcePath(mirror.source)}</b></div>
  </section>;
}
