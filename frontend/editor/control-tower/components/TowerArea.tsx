// Pásmo oblasti: barevný pruh stejné barvy jako rámeček oblasti na plátně, název, účel a vlastní součty;
// uvnitř členové oblasti (sektory, karty, kontejnerové karty). Na kořeni je to hlavní pásmo pyramidy,
// uvnitř rozbalené dlaždice (`nested`) menší pásmo oblasti té vrstvy.
import type { TowerArea as Area } from "../logic/tower-model";
import TowerBar from "./TowerBar";
import { TowerGroup, type TowerNav } from "./TowerLayer";

type Props = { area: Area; depth: number; nested?: boolean; nav: TowerNav };

export default function TowerArea({ area, depth, nested, nav }: Props) {
  const c = area.counts;
  const extra = (c.running ? " · " + c.running + " pracuje" : "") + (c.failed ? " · " + c.failed + " selhalo" : "");
  const empty = !area.sectors.length && !area.cards.length && !area.containers.length;
  return (
    <section className={"tower-area" + (nested ? " tower-area--nested" : "")} data-color={area.color} aria-label={"Oblast " + area.name}>
      <header className="tower-area__head">
        <h3 className="tower-area__name">{area.name}</h3>
        <span className="tower-area__counts">{c.closed}/{c.cards} hotovo{extra}</span>
      </header>
      {area.purpose && <p className="tower-area__purpose">{area.purpose}</p>}
      <TowerBar counts={c} />
      <TowerGroup group={area} depth={depth} nav={nav} />
      {empty && <p className="tower-area__empty">V oblasti zatím nic neleží.</p>}
    </section>
  );
}
