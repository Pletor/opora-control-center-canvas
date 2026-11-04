import { barText, seconds, type Work, type WorkPhase } from "../logic/heart-work";
import WorkSteps from "./WorkSteps";
import "../styles/heart-work.css";

type Props = { phase: WorkPhase; work: Work | null; elapsedMs: number; typicalMs: number | null; onClose: () => void; onOpenAssistant?: () => void; onRetry: () => void };

/** Okno „Co srdce dělá“: nahoře průběh (čas, obvyklá délka, počet kroků, stav slovy), uprostřed živé kroky, dole závěrečná
 * odpověď srdce nebo chyba. Samo nic neposílá; Zkusit znovu vrací zadání do pole, Otevřít Asistent vede do kanálu. */
export default function HeartWork({ phase, work, elapsedMs, typicalMs, onClose, onOpenAssistant, onRetry }: Props) {
  const steps = work?.steps ?? null, running = phase === "running" || phase === "queued" || phase === "finishing";
  return <section className="heart-work" role="dialog" aria-label="Co srdce dělá" data-testid="heart-work" data-phase={phase}>
    <header className="heart-work__head">
      <h3 className="heart-work__title">Co srdce dělá</h3>
      <button type="button" className="heart-work__close" aria-label="Zavřít okno" data-testid="heart-work-close" onClick={onClose}>×</button>
    </header>
    <p className="heart-work__progress" data-testid="heart-work-progress">
      {barText(phase, work, elapsedMs, typicalMs)}{typicalMs && !running ? ` · obvykle ~${seconds(typicalMs)}` : ""}
    </p>
    {steps?.length
      ? <WorkSteps steps={steps} follow={running}/>
      : <p className="heart-work__none" data-testid="heart-work-none">{work && !work.running ? "Detail kroků u této dávky není k dispozici." : "Srdce zatím nezapsalo žádný krok."}</p>}
    {work && !work.running && (work.error || work.reply) && <div className={`heart-work__reply${work.error ? " heart-work__reply--error" : ""}`} data-testid="heart-work-reply">
      <b>{work.error ? "Chyba" : "Odpověď srdce"}</b>
      <p>{work.error || work.reply}</p>
    </div>}
    {phase === "stalled" && <p className="heart-work__none">Srdce se zadáním nezačalo. Je možné, že spí (limit předplatného) nebo je vypnuté; stav a případné otázky najdete v kanálu Asistent.</p>}
    <footer className="heart-work__actions">
      {!running && <button type="button" className="heart-work__button" data-testid="heart-work-retry" onClick={onRetry}>Zkusit znovu</button>}
      {onOpenAssistant && <button type="button" className="heart-work__button" data-testid="heart-work-assistant" onClick={onOpenAssistant}>Otevřít Asistent</button>}
      <button type="button" className="heart-work__button" onClick={onClose}>Zavřít</button>
    </footer>
  </section>;
}
