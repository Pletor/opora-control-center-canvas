import type { LiveCard } from "../logic/live-card-types";
import { latestRun, stateView, usd } from "../logic/live-card-view";

export type Side = "human" | "agent";
type Props = { card: LiveCard | null; nodeId: string; side: Side; onSide: (side: Side) => void; onClose: () => void };

const CIRCLE = 151;

/** Hlavička obou stran: kruh postupu, drobečky, název se štítky, počitadla testů a USD, přepínač stran a ✕. */
export default function CardHead({ card, nodeId, side, onSide, onClose }: Props) {
  const state = stateView(card?.state ?? "");
  const progress = card?.progress ?? null;
  const run = card ? latestRun(card.runs) : null;
  return <header className="live-card__head">
    {progress !== null && <div className={`live-card__ring live-card__tone--${state.tone}`} aria-label={`Postup ${progress} %`}>
      <svg viewBox="0 0 58 58" className="live-card__ring-svg" aria-hidden="true">
        <circle cx="29" cy="29" r="24" className="live-card__ring-track" />
        <circle cx="29" cy="29" r="24" className="live-card__ring-fill" strokeDasharray={CIRCLE} strokeDashoffset={CIRCLE - CIRCLE * progress / 100} />
      </svg>
      <b className="live-card__ring-text">{progress} %</b>
    </div>}
    <div className="live-card__id">
      <div className="live-card__crumbs">{[...(card?.crumbs ?? []), card?.kind].filter(Boolean).join(" › ") || nodeId}</div>
      <div className="live-card__title-row">
        <h1 className="live-card__title" id="live-card-title">{card?.title ?? nodeId}</h1>
        {card && <span className={`live-card__pill live-card__tone--${state.tone}`}>{state.label}</span>}
        {card?.pills.map(pill => <span key={pill.text} className={`live-card__pill live-card__tone--${pill.tone}`}>{pill.text}</span>)}
      </div>
    </div>
    <div className="live-card__right">
      {card && <div className="live-card__counters">
        {run?.tests && <div className="live-card__counter"><b className="live-card__counter-value">{run.tests.passed}/{run.tests.total}</b><span className="live-card__counter-label">testy</span></div>}
        {card.cost?.totalUsd != null && <div className="live-card__counter"><b className="live-card__counter-value">{usd(card.cost.totalUsd)}</b><span className="live-card__counter-label">USD</span></div>}
      </div>}
      <div className="live-card__flip" role="group" aria-label="Strana karty">
        <button type="button" className="live-card__flip-button" aria-pressed={side === "human"} onClick={() => onSide("human")}>Pro člověka</button>
        <button type="button" className="live-card__flip-button" aria-pressed={side === "agent"} onClick={() => onSide("agent")}>Pro agenty</button>
      </div>
      <button type="button" className="live-card__close" aria-label="Zavřít" onClick={onClose}>✕</button>
    </div>
  </header>;
}
