import type { LiveCard, MirrorTruth as Mirror, PendingTruth, Truth } from "../logic/live-card-types";
import { isPending, markOfStatus, sourcePath, truthBar, type Tone } from "../logic/live-card-view";
import FutureTruth from "./FutureTruth";
import MirrorTruth from "./MirrorTruth";

const TRUTHS: { id: keyof LiveCard["truths"]; name: string; tone: Tone; bar: string }[] = [
  { id: "vision", name: "Záměr", tone: "vision", bar: "kritéria" },
  { id: "mirror", name: "Zrcadlo kódu", tone: "mirror", bar: "shoda" },
  { id: "reality", name: "Skutečnost", tone: "real", bar: "v main" },
  { id: "future", name: "Budoucnost", tone: "future", bar: "" },
];

function TruthBox({ name, tone, bar, truth }: { name: string; tone: Tone; bar: string; truth: Truth | PendingTruth }) {
  if (isPending(truth)) return <section className="live-card__truth live-card__truth--pending">
    <h3 className="live-card__h">{name}</h3>
    <p className="live-card__pending">staví se {truth.milestone}</p>
  </section>;
  const fill = truthBar(truth);
  return <section className={`live-card__truth live-card__tone--${tone}`}>
    <h3 className="live-card__h">{name}<small className="live-card__h-meta">{truth.sha ?? ""}</small></h3>
    <ul className="live-card__list">
      {truth.items.map((item, index) => <li key={index} className={`live-card__item live-card__item--${item.status}`}>
        <b className="live-card__mark">{markOfStatus(item.status)}</b>
        <span className="live-card__item-text">{item.text}</span>
      </li>)}
    </ul>
    {fill && <div className="live-card__bar">{bar}<i className="live-card__bar-track"><i className="live-card__bar-fill" style={{ width: `${fill.pct}%` }} /></i><em className="live-card__bar-value">{fill.done}/{fill.total}</em></div>}
    <div className="live-card__src">zdroj: <b className="live-card__src-url" title={truth.source}>{sourcePath(truth.source)}</b></div>
  </section>;
}

/** Čtyři pravdy vedle sebe; chybějící pravda se nekreslí, nedostavěné zrcadlo (F1) je šedá karta. */
export default function TruthsGrid({ truths }: { truths: LiveCard["truths"] }) {
  const shown = TRUTHS.filter(item => truths[item.id]);
  if (!shown.length) return null;
  return <div className="live-card__truths">
    {shown.map(({ id, ...item }) => {
      const truth = truths[id]!;
      if (id === "future") return <FutureTruth key={id} future={truths.future!} />;
      return "available" in truth && truth.available ? <MirrorTruth key={id} mirror={truth as Mirror} /> : <TruthBox key={id} {...item} truth={truth as Truth | PendingTruth} />;
    })}
  </div>;
}
