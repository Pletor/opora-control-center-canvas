import { TRANSITION_TEXT, type LaneTransition } from "../logic/studio-lanes";

/** Přechod mezi dvěma zastávkami dráhy: šipka obarvená stavem posledního ověření (prošel, neprošel, zastaralé, neověřeno),
 * nad ní signál `via` (co zákazník udělá na předchozí stránce), pod ní realizace na mapě (`line`, nebo „nerealizováno“)
 * a odbočka, když krok nenavazuje na předchozí. Jen zobrazení, hotová data od rodiče. */
export default function StudioTransition({ transition, testId }: { transition: LaneTransition; testId: string }) {
  const { signal, missingSection, branchFrom, realized, line, state, reason } = transition;
  const stateTitle = TRANSITION_TEXT[state] + (reason ? ` (${reason})` : "");
  return <li className={"studio__transition studio__transition--" + state} data-testid={testId} data-state={state}>
    {branchFrom && <span className="studio__transition-branch">odbočka z {branchFrom}</span>}
    <span className={"studio__transition-signal" + (missingSection ? " studio__transition-signal--missing" : "")}
      title={missingSection ? `Předchozí stránka sekci ${missingSection} nemá` : "Co zákazník udělá na předchozí stránce, aby se dostal sem"}>
      {signal ?? "signál neurčen"}
    </span>
    <span className="studio__transition-arrow" aria-hidden="true"/>
    <span className="studio__transition-state">{stateTitle}</span>
    {realized !== null && <span className={"studio__transition-line" + (realized ? "" : " studio__transition-line--gap")}
      title={realized ? "Mapa přechod nese: " + line : "Na mapě zatím nevede vazba: " + line}>
      {realized ? line : "nerealizováno"}
    </span>}
  </li>;
}
