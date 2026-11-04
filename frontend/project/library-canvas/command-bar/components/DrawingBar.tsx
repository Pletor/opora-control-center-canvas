import type { DrawingPhase } from "../logic/use-command-bar";
import { TIMEOUT_TEXT } from "../logic/command-bar";
import "../styles/command-bar.css";

type Props = { phase: Exclude<DrawingPhase, "idle">; seconds: number; onCancel: () => void; onOpenAssistant?: () => void };

/** Lišta po odeslání zadání: „Srdce kreslí…“ s odpočtem vteřin a Zrušit (jen schová lištu, na serveru nic neruší). Po
 * ~3 minutách řekne, že srdce neodpovědělo; otázku srdce při nejasném zadání čte člověk v kanálu Asistent. */
export default function DrawingBar({ phase, seconds, onCancel, onOpenAssistant }: Props) {
  return <div className={`command-bar-status${phase === "timeout" ? " command-bar-status--timeout" : ""}`} role="status" data-testid="drawing-bar">
    <span className="command-bar-status__text">{phase === "waiting" ? <>Srdce kreslí… <b>{seconds} s</b></> : TIMEOUT_TEXT}</span>
    {onOpenAssistant && <button type="button" className="command-bar-status__button" data-testid="drawing-open-assistant" onClick={onOpenAssistant}>Otevřít Asistent</button>}
    <button type="button" className="command-bar-status__button" data-testid="drawing-cancel" onClick={onCancel}>{phase === "waiting" ? "Zrušit" : "Zavřít"}</button>
  </div>;
}
