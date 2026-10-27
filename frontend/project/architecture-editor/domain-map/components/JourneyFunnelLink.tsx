/** Šipka mezi dvěma kroky trychtýře: signál přechodu (`via` jako věta, např. „odešle formulář v sekci Výzva“; sekci,
 * kterou předchozí stránka nemá, ukáže varovně), odkud krok odbočuje (když nenavazuje na předchozí) a tichý štítek
 * „chybí vazba“, když mapa přechod zatím nerealizuje (práce pro agenty, cestu to nerozbíjí). Hotová data od rodiče. */
export default function JourneyFunnelLink({ signal, missingSection, branchFrom, unrealized }: {
  signal?: string | null; missingSection?: string | null; branchFrom?: string; unrealized?: string | null;
}) {
  return <div className="domain-map__funnel-link">
    <span aria-hidden="true" className="domain-map__funnel-arrow">↓</span>
    {signal && <span className={"domain-map__funnel-signal" + (missingSection ? " domain-map__funnel-signal--missing" : "")}
      title={missingSection ? `Předchozí stránka sekci ${missingSection} nemá` : "Co zákazník udělá na předchozí stránce, aby se dostal sem"}>{signal}</span>}
    {branchFrom && <span className="domain-map__funnel-branch">odbočka z {branchFrom}</span>}
    {unrealized && <span className="domain-map__funnel-gap" title={"Na mapě zatím nevede vazba: " + unrealized}>chybí vazba</span>}
  </div>;
}
