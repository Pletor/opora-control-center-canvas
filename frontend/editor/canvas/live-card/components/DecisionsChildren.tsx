import type { LiveCard } from "../logic/live-card-types";
import { stateView } from "../logic/live-card-view";

/** Rozhodnutí (proč touto cestou) a potomci karty; klik na potomka otevře jeho živou kartu. */
export default function DecisionsChildren({ card, onOpenCard }: { card: LiveCard; onOpenCard: (nodeId: string) => void }) {
  return <>
    {card.decisions.length > 0 && <section className="live-card__box">
      <h3 className="live-card__h">Rozhodnutí a výzkum<small className="live-card__h-meta">proč touto cestou</small></h3>
      <ul className="live-card__list">
        {card.decisions.map((item, index) => <li key={index} className="live-card__item live-card__item--ok" title={item.source}>
          <b className="live-card__mark">●</b><span className="live-card__item-text">{item.text}</span>
        </li>)}
      </ul>
    </section>}
    {card.children.length > 0 && <section className="live-card__box">
      <h3 className="live-card__h">Uvnitř<small className="live-card__h-meta">potomci · klik otevře</small></h3>
      <div className="live-card__kids">
        {card.children.map(child => {
          const state = stateView(child.state);
          return <button key={child.nodeId} type="button" className={`live-card__kid live-card__tone--${state.tone}`} onClick={() => onOpenCard(child.nodeId)}>
            <b className="live-card__kid-title">{child.title}</b>
            <span className="live-card__kid-state">{state.label}{child.progress != null ? ` · ${child.progress} %` : ""}</span>
            {child.progress != null && <i className="live-card__kid-bar"><i className="live-card__kid-fill" style={{ width: `${child.progress}%` }} /></i>}
          </button>;
        })}
      </div>
    </section>}
  </>;
}
