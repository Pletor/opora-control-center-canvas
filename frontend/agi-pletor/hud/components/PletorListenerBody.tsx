import type { HudState } from "../logic/hud-state";
import PletorHudCanvas from "./PletorHudCanvas";

type Props = { state: HudState; label: string; level: () => number | null; interim: string; reply: string; onInterrupt: () => void };

/**
 * Jádro popupu Poslech: malé plátno z HUD (hlasitost mikrofonu při poslechu, amplituda hlasu při mluvení),
 * štítek stavu (`label`, česky z hudLabel), živý přepis toho, co slyší, a poslední odpověď Pletora. Klik na jádro utne čtení odpovědi.
 * Jádro je i úchyt pro přetažení (`data-drag`); přetažení od kliku odliší rodič.
 */
export default function PletorListenerBody({ state, label, level, interim, reply, onInterrupt }: Props) {
  return (
    <div className="pletor-listener__body">
      <button type="button" className={`pletor-listener__core pletor-listener__core--${state}`} data-drag
        aria-label={state === "speaking" ? "Přerušit řeč" : `Pletor: ${label}`} onClick={onInterrupt}>
        <PletorHudCanvas state={state} level={level} className="pletor-listener__canvas" />
      </button>
      <div className="pletor-listener__text">
        <span className={`pletor-listener__state pletor-listener__state--${state}`} role="status">{label}</span>
        <p className="pletor-listener__interim" aria-live="off">{interim || " "}</p>
        {reply && <p className="pletor-listener__reply" title={reply}>{reply}</p>}
      </div>
    </div>
  );
}
