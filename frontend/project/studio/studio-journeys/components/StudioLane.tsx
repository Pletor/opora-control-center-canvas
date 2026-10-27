import { Fragment } from "react";
import JourneyBadge from "./JourneyBadge";
import type { StudioLane as Lane } from "../logic/studio-lanes";
import StudioTransition from "./StudioTransition";

/** Jedna cesta zákazníka jako vodorovná dráha: v záhlaví název, sdílený odznak ověření a proměna zákazníka A → B, pod tím
 * zastávky (role, název stránky, cesta; menu jako „Menu“) a mezi nimi přechody. Klik na zastávku se stránkou hlásí
 * `onOpen(pageId)` (rodič ve Studiu vybere stránku na plátně); menu a chybějící stránka se otevřít nedají. */
export default function StudioLane({ lane, onOpen }: { lane: Lane; onOpen: (pageId: string) => void }) {
  const { journey, derived, broken, stops, transitions } = lane;
  const id = journey.id;
  return <li className="studio-journeys__lane" data-testid={"studio-journeys-lane-" + id}>
    <header className="studio-journeys__lane-head">
      <strong className="studio-journeys__lane-name">{journey.name}</strong>
      <JourneyBadge journeyId={id} derived={derived}/>
      {(journey.pointA || journey.pointB) && <span className="studio-journeys__lane-shift">
        <b className="studio-journeys__lane-point">A</b> {journey.pointA ?? "?"} <span aria-hidden="true">→</span> <b className="studio-journeys__lane-point">B</b> {journey.pointB ?? "?"}
      </span>}
    </header>
    {broken && <p className="studio-journeys__lane-broken">Cesta je přerušená: {broken}</p>}
    <ol className="studio-journeys__track">
      {stops.map((stop, index) => <Fragment key={stop.stepId}>
        {index > 0 && <StudioTransition transition={transitions[index - 1]} testId={`studio-journeys-transition-${id}-${stop.stepId}`}/>}
        <li className="studio-journeys__stop-slot">
          <button type="button" className={"studio-journeys__stop" + (stop.missing ? " studio-journeys__stop--missing" : "") + (stop.pageId ? "" : " studio-journeys__stop--static")}
            disabled={!stop.pageId} title={stop.pageId ? "Vybrat stránku na plátně" : undefined}
            data-testid={`studio-journeys-stop-${id}-${stop.stepId}`} onClick={() => stop.pageId && onOpen(stop.pageId)}>
            <span className="studio-journeys__stop-role">{stop.role}</span>
            <span className="studio-journeys__stop-title">{stop.title}</span>
            {stop.path && <code className="studio-journeys__stop-path">{stop.path}</code>}
          </button>
        </li>
      </Fragment>)}
    </ol>
  </li>;
}
