import { Fragment } from "react";
import JourneyVerification from "../../components/JourneyVerification";
import type { StudioLane as Lane } from "../logic/studio-lanes";
import StudioTransition from "./StudioTransition";

/** Jedna cesta zákazníka jako vodorovná dráha: v záhlaví název, sdílený odznak ověření a proměna zákazníka A → B, pod tím
 * zastávky (role, název stránky, cesta; menu jako „Menu“) a mezi nimi přechody. Klik na zastávku se stránkou hlásí
 * `onOpen(pageId)` (rodič otevře Editor stránky); menu a chybějící stránka se otevřít nedají. */
export default function StudioLane({ lane, onOpen }: { lane: Lane; onOpen: (pageId: string) => void }) {
  const { journey, derived, broken, stops, transitions } = lane;
  const id = journey.id;
  return <li className="studio__lane" data-testid={"architecture-studio-lane-" + id}>
    <header className="studio__lane-head">
      <strong className="studio__lane-name">{journey.name}</strong>
      <JourneyVerification journeyId={id} derived={derived}/>
      {(journey.pointA || journey.pointB) && <span className="studio__lane-shift">
        <b className="studio__lane-point">A</b> {journey.pointA ?? "?"} <span aria-hidden="true">→</span> <b className="studio__lane-point">B</b> {journey.pointB ?? "?"}
      </span>}
    </header>
    {broken && <p className="studio__lane-broken">Cesta je přerušená: {broken}</p>}
    <ol className="studio__track">
      {stops.map((stop, index) => <Fragment key={stop.stepId}>
        {index > 0 && <StudioTransition transition={transitions[index - 1]} testId={`architecture-studio-transition-${id}-${stop.stepId}`}/>}
        <li className="studio__stop-slot">
          <button type="button" className={"studio__stop" + (stop.missing ? " studio__stop--missing" : "") + (stop.pageId ? "" : " studio__stop--static")}
            disabled={!stop.pageId} title={stop.pageId ? "Otevřít Editor stránky" : undefined}
            data-testid={`architecture-studio-stop-${id}-${stop.stepId}`} onClick={() => stop.pageId && onOpen(stop.pageId)}>
            <span className="studio__stop-role">{stop.role}</span>
            <span className="studio__stop-title">{stop.title}</span>
            {stop.path && <code className="studio__stop-path">{stop.path}</code>}
          </button>
        </li>
      </Fragment>)}
    </ol>
  </li>;
}
