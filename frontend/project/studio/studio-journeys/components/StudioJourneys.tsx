import type { StudioLane as Lane } from "../logic/studio-lanes";
import StudioLane from "./StudioLane";
import "../styles/studio-journeys.css";

/** Pás pod plátnem Studia na úrovni domény: cesty zákazníka jako dráhy se stavem přechodů podle posledního ověření.
 * Dráhy dostane hotové (`studioLanes`), sbalení drží rodič (`open`, `onToggle`); klik na zastávku hlásí stránku (`onPage`). */
export default function StudioJourneys({ lanes, open, onToggle, onPage }: { lanes: Lane[]; open: boolean; onToggle: () => void; onPage: (pageId: string) => void }) {
  return <section className="studio-journeys" data-testid="studio-journeys" aria-label="Cesty zákazníka domény">
    <button type="button" className={"studio-journeys__toggle" + (open ? " studio-journeys__toggle--open" : "")} aria-expanded={open} onClick={onToggle}>
      Cesty zákazníka <span className="studio-journeys__heading-count">{lanes.length}</span>
    </button>
    {open && (lanes.length
      ? <ol className="studio-journeys__lane-list">{lanes.map((lane) => <StudioLane key={lane.journey.id} lane={lane} onOpen={onPage}/>)}</ol>
      : <p className="studio-journeys__empty">Doména zatím nemá cesty zákazníka.</p>)}
  </section>;
}
