import { pageJourneyText, type PageJourneyRole } from "../logic/page-journeys";

/** Na kterých cestách zákazníka stránka leží, v jaké roli a k jakému posunu slouží („Prodej kurzu · Upsell (krok 4) –
 * z … na …“), každá cesta na jednom řádku. Jen ke čtení: cesty se mění v trychtýři cesty pod kartami stránek. Bez cest nic. */
export default function PageJourneys({ roles, pageId }: { roles: PageJourneyRole[]; pageId: string }) {
  if (!roles.length) return null;
  return <ul className="domain-map__page-journeys" aria-label="Cesty zákazníka přes tuto stránku" data-testid={"architecture-page-journeys-" + pageId}>
    {roles.map((role) => { const text = pageJourneyText(role);
      return <li key={role.journeyId + ":" + role.stepId} className="domain-map__page-journey" title={text}>{text}</li>; })}
  </ul>;
}
