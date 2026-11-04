import type { HudState } from "../logic/hud-palette";
import PletorHudCanvas from "./PletorHudCanvas";

/** Stav jádra popupu česky, jedním slovem, co Pletor právě dělá. */
export const LISTENER_LABEL: Record<HudState, string> = {
  idle: "čekám", listening: "poslouchám", thinking: "přemýšlím", speaking: "mluvím", error: "chyba",
};

type Props = { state: HudState; level: () => number | null; interim: string; reply: string; onInterrupt: () => void };

/**
 * Jádro popupu Poslech: malé plátno z HUD (hlasitost mikrofonu při poslechu, amplituda hlasu při mluvení),
 * štítek stavu, živý přepis toho, co slyší, a poslední odpověď Pletora. Klik na jádro utne čtení odpovědi.
 * Jádro je i úchyt pro přetažení (`data-drag`); přetažení od kliku odliší rodič.
 */
export default function PletorListenerBody({ state, level, interim, reply, onInterrupt }: Props) {
  return (
    <div className="pletor-listener__body">
      <button type="button" className={`pletor-listener__core pletor-listener__core--${state}`} data-drag
        aria-label={state === "speaking" ? "Přerušit řeč" : `Pletor: ${LISTENER_LABEL[state]}`} onClick={onInterrupt}>
        <PletorHudCanvas state={state} level={level} className="pletor-listener__canvas" />
      </button>
      <div className="pletor-listener__text">
        <span className={`pletor-listener__state pletor-listener__state--${state}`} role="status">{LISTENER_LABEL[state]}</span>
        <p className="pletor-listener__interim" aria-live="off">{interim || " "}</p>
        {reply && <p className="pletor-listener__reply" title={reply}>{reply}</p>}
      </div>
    </div>
  );
}
