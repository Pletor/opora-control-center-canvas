import { verificationTime, verificationTitle, type VerificationBadge } from "../../../domain-map/logic/journey-verification";

/** Odznak ověření cesty v hlavičce úseku: stejný text jako v trychtýři na Mapě domény, s časem běhu. */
export default function SliceVerification({ badge }: { badge: VerificationBadge | undefined }) {
  if (!badge) return null;
  const when = verificationTime(badge.at);
  return <span className={"journey-slice__verified journey-slice__verified--" + badge.tone} title={verificationTitle(badge)}
    data-testid="architecture-slice-verified">
    {badge.text}{when && <time className="journey-slice__verified-time" dateTime={badge.at ?? undefined}>{when}</time>}
  </span>;
}
