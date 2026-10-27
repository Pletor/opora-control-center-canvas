import { useState } from "react";
import type { PageSlice, SectionChip } from "../logic/page-slice";
import SliceRow from "./SliceRow";
import SectionStrip from "./SectionStrip";
import SliceVerification from "./SliceVerification";
import "../styles/journey-slice.css";

type Props = {
  slices: PageSlice[]; sections: SectionChip[];
  /** Soused na cestě: přepne rozsah editoru na jeho stránku. */
  onOpenPage: (pageId: string) => void;
  /** „Upravit cestu“ (id cesty) nebo výzva u stránky mimo cesty (`null`): rodič otevře Mapu domény. */
  onOpenJourneys: (journeyId: string | null) => void;
  /** Štítek sekce: rodič vybere stránku v Detailu prvku (záložka Stránka). */
  onSelectPage: () => void;
};

/** Úsek cesty zákazníka aktivní stránky nad plátnem a pod ním pruh sekcí. Více cest = přepínač, vidět je vždy jeden úsek.
 * Nic neukládá: cesty se mění v trychtýři na Mapě domény, sekce v Detailu prvku. */
export default function JourneySlice({ slices, sections, onOpenPage, onOpenJourneys, onSelectPage }: Props) {
  const [chosen, setChosen] = useState(0);
  const index = Math.min(chosen, slices.length - 1);
  const slice = slices[index];
  return <section className="journey-slice" aria-label="Cesta zákazníka této stránky" data-testid="architecture-journey-slice">
    {slice ? <>
      <header className="journey-slice__head">
        <span className="journey-slice__kicker">CESTA ZÁKAZNÍKA</span>
        {slices.length > 1 ? <div className="journey-slice__switch" role="group" aria-label="Cesty, na kterých stránka leží">
          {slices.map((item, at) => <button key={item.journeyId + ":" + item.stepId} type="button" className="journey-slice__switch-item"
            aria-pressed={at === index} onClick={() => setChosen(at)}>{item.journeyName} · {item.step}.</button>)}
        </div> : <strong className="journey-slice__name">{slice.journeyName}</strong>}
        <SliceVerification badge={slice.verification}/>
        {slice.broken && <span className="journey-slice__broken">Cesta je přerušená: {slice.broken}</span>}
        <button type="button" className="journey-slice__edit" data-testid="architecture-slice-edit" onClick={() => onOpenJourneys(slice.journeyId)}>Upravit cestu</button>
      </header>
      <SliceRow slice={slice} onOpenPage={onOpenPage}/>
    </> : <p className="journey-slice__empty" data-testid="architecture-slice-empty">
      Stránka zatím neleží na žádné cestě zákazníka – přidej ji v{" "}
      <button type="button" className="journey-slice__link" onClick={() => onOpenJourneys(null)}>Mapě domény</button>.
    </p>}
    <SectionStrip sections={sections} onSelect={onSelectPage}/>
  </section>;
}
