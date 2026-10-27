import type { DerivedJourney } from "@/project/architecture-editor/domain-map/logic/derived-journeys";
import { verificationBadge, verificationTime, verificationTitle } from "@/project/architecture-editor/domain-map/logic/journey-verification";

/** Odznak posledního ověření cesty (`derived.lastRun`) s časem běhu, logika sdílená s trychtýřem mapy domény; rozbitá
 * cesta nebo chybějící odvození = nic. Jen zobrazení. */
export default function JourneyBadge({ journeyId, derived }: { journeyId: string; derived: DerivedJourney | undefined }) {
  const badge = verificationBadge(derived);
  if (!badge) return null;
  const when = verificationTime(badge.at);
  return <span className={"studio-journeys__badge studio-journeys__badge--" + badge.tone} title={verificationTitle(badge)} data-testid={"studio-journey-verified-" + journeyId}>
    {badge.text}{when && <time className="studio-journeys__badge-time" dateTime={badge.at ?? undefined}>{when}</time>}
  </span>;
}
