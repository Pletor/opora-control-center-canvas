import type { WorkPhase } from "../logic/heart-work";
import "../styles/command-bar.css";

type Props = { phase: WorkPhase; text: string; onDetails: () => void; onCancel: () => void; onOpenAssistant?: () => void };

/** Lišta po odeslání zadání: co srdce dělá a jak dlouho („Srdce čte skill… 12 s · krok 3 · obvykle ~60 s“), Podrobnosti
 * otevřou okno s kroky a Zrušit/Zavřít lištu jen schová (na serveru nic neruší). U odpovědi bez kreslení, chyby a zaseknutí
 * lišta zežloutne a odkáže na kanál Asistent. */
export default function DrawingBar({ phase, text, onDetails, onCancel, onOpenAssistant }: Props) {
  const working = phase === "queued" || phase === "running" || phase === "finishing";
  return <div className={`command-bar-status${working ? "" : " command-bar-status--stopped"}`} role="status" data-testid="drawing-bar" data-phase={phase}>
    <span className="command-bar-status__text">{text}</span>
    {phase !== "stalled" && <button type="button" className="command-bar-status__button" data-testid="drawing-details" onClick={onDetails}>Podrobnosti</button>}
    {!working && onOpenAssistant && <button type="button" className="command-bar-status__button" data-testid="drawing-open-assistant" onClick={onOpenAssistant}>Otevřít Asistent</button>}
    <button type="button" className="command-bar-status__button" data-testid="drawing-cancel" onClick={onCancel}>{working ? "Zrušit" : "Zavřít"}</button>
  </div>;
}
