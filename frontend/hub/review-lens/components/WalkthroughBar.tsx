import type { Step, WalkAction } from "../logic/walkthrough";

/** Pruh průvodce nad plátnem: číslo kroku, nadpis změny, řádek o chování a ovládání (W/→, ←, Esc). */
export default function WalkthroughBar({ step, index, total, onAction }: { step: Step; index: number; total: number; onAction: (action: WalkAction) => void }) {
  return <section className="review-lens__walk" aria-live="polite" aria-label="Průvodce změnou" data-oh-walk-index={index} data-oh-walk-total={total}>
    <div className="review-lens__walk-dots" aria-hidden="true">
      {Array.from({ length: total }, (_, item) => <span key={item} className={`review-lens__walk-dot${item === index ? " review-lens__walk-dot--on" : item < index ? " review-lens__walk-dot--done" : ""}`} />)}
    </div>
    <div className="review-lens__walk-text">
      <span className="review-lens__muted">Krok {index + 1}/{total}</span>
      <b className="review-lens__walk-heading">{step.heading}</b>
      <span>{step.body}</span>
      {step.detail && <span className="review-lens__muted">{step.detail.text}</span>}
    </div>
    <div className="review-lens__walk-controls">
      <button type="button" className="review-lens__walk-button" aria-label="Předchozí krok" disabled={index === 0} onClick={() => onAction("prev")}>←</button>
      <button type="button" className="review-lens__walk-button" aria-label="Další krok" disabled={index === total - 1} onClick={() => onAction("next")}>→</button>
      <button type="button" className="review-lens__walk-button" aria-label="Ukončit průvodce (Esc)" onClick={() => onAction("stop")}>✕</button>
    </div>
  </section>;
}
