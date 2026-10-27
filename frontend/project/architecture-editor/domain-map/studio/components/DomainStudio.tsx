import type { ApplicationSite, CanvasNode } from "@/shared/types/logic/types";
import { derivedForDomain, type DerivedJourney } from "../../logic/derived-journeys";
import type { MapCheckTarget } from "../../map-check/logic/map-check";
import type { FlowSummary } from "../logic/studio-flows";
import { studioLanes } from "../logic/studio-lanes";
import StudioFlows from "./StudioFlows";
import StudioLane from "./StudioLane";
import "../styles/studio.css";

/** Pohled Studio na mapu domény (docs/architektura-pro-agenty.md §7): nahoře cesty zákazníka jako dráhy se stavem přechodů
 * podle posledního ověření, pod nimi tok domény podle `carries`. Stejná data jako pohled Stránky, jen ke čtení. Dráhy
 * sestaví čistá funkce `studioLanes`, toky dostane hotové od rodiče; klik na zastávku jde do `onOpen`, na vazbu toku
 * do `onOpenFinding` (stejný mechanismus jako Díry mapy). */
export default function DomainStudio({ domainId, site, pages, derived, flows, onOpen, onOpenFinding }: {
  domainId: string; site: ApplicationSite | undefined; pages: CanvasNode[]; derived: DerivedJourney[] | null; flows: FlowSummary[] | null;
  onOpen: (pageId: string) => void; onOpenFinding: (target: MapCheckTarget) => void;
}) {
  const lanes = studioLanes(site, pages, derivedForDomain(derived ?? [], domainId));
  return <div className="studio" data-testid="architecture-studio">
    <section className="studio__lanes">
      <h3 className="studio__heading">Cesty zákazníka <span className="studio__heading-count">{lanes.length}</span></h3>
      {lanes.length
        ? <ol className="studio__lane-list">{lanes.map((lane) => <StudioLane key={lane.journey.id} lane={lane} onOpen={onOpen}/>)}</ol>
        : <p className="studio__empty">Doména zatím nemá cesty zákazníka. Zadávají se v pohledu Stránky.</p>}
    </section>
    {flows && <StudioFlows flows={flows} onSelect={(target) => target.kind === "page" ? onOpen(target.id) : onOpenFinding(target)}/>}
  </div>;
}
