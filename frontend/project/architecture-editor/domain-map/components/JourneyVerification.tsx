import type { DerivedJourney } from "../logic/derived-journeys";
import { verificationBadge, verificationTime, verificationTitle } from "../logic/journey-verification";

/** Odznak ověření cesty v hlavičce trychtýře: poslední doklad přehrání (`derived.lastRun`) s časem běhu; rozbitá cesta
 * nebo chybějící odvození = nic. Jen zobrazení, data od rodiče. */
export default function JourneyVerification({ journeyId, derived }: { journeyId: string; derived: DerivedJourney | undefined }) {
  const badge = verificationBadge(derived);
  if (!badge) return null;
  const when = verificationTime(badge.at);
  return <span className={"domain-map__journey-verified domain-map__journey-verified--" + badge.tone} title={verificationTitle(badge)}
    data-testid={"architecture-journey-verified-" + journeyId}>
    {badge.text}{when && <time className="domain-map__journey-verified-time" dateTime={badge.at ?? undefined}>{when}</time>}
  </span>;
}
