import { formatRate } from "../logic/journeys";

/** Šipka mezi dvěma kroky trychtýře: konverze (když jsou oba počty), odkud krok odbočuje (když nenavazuje na předchozí)
 * a tichý štítek „chybí vazba“, když mapa přechod zatím nerealizuje (práce pro agenty, cestu to nerozbíjí). */
export default function JourneyFunnelLink({ rate, branchFrom, unrealized }: { rate: number | null; branchFrom?: string; unrealized?: string | null }) {
  return <div className="domain-map__funnel-link">
    <span aria-hidden="true" className="domain-map__funnel-arrow">↓</span>
    {rate !== null && <span className="domain-map__funnel-rate" title="Kolik lidí z předchozího kroku došlo sem">{formatRate(rate)}</span>}
    {branchFrom && <span className="domain-map__funnel-branch">odbočka z {branchFrom}</span>}
    {unrealized && <span className="domain-map__funnel-gap" title={"Na mapě zatím nevede vazba: " + unrealized}>chybí vazba</span>}
  </div>;
}
