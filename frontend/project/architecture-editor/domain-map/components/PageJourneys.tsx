import { pageJourneyText, type PageJourneyRole } from "../logic/page-journeys";

/** Na kterých cestách zákazníka stránka leží a v jaké roli („Prodej kurzu · Upsell (krok 4)“). Jen ke čtení:
 * cesty se mění v trychtýři cesty pod kartami stránek. Bez cest nic. */
export default function PageJourneys({ roles, pageId }: { roles: PageJourneyRole[]; pageId: string }) {
  if (!roles.length) return null;
  return <ul className="domain-map__page-journeys" aria-label="Cesty zákazníka přes tuto stránku" data-testid={"architecture-page-journeys-" + pageId}>
    {roles.map((role) => <li key={role.journeyId + ":" + role.stepId} className="domain-map__page-journey">{pageJourneyText(role)}</li>)}
  </ul>;
}
