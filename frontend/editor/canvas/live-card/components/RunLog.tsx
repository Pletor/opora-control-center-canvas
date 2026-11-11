import type { RecentItem } from "../logic/live-card-types";
import { actorView, clock, runLanes } from "../logic/live-card-view";

/** Živý běh: dráhy aktérů (kdo kdy zasáhl) a deník karty, nejnovější nahoře, nový řádek zvýrazněný. */
export default function RunLog({ recent }: { recent: RecentItem[] }) {
  if (!recent.length) return null;
  const lanes = runLanes(recent);
  return <div className="live-card__row">
    <section className="live-card__box">
      <h3 className="live-card__h">Živý běh<small className="live-card__h-meta">dráhy aktérů</small></h3>
      <div className="live-card__lanes">
        {lanes.map(lane => <div key={lane.lane} className="live-card__lane">
          <span className="live-card__lane-name">{lane.lane}</span>
          <div className="live-card__track">{lane.ticks.map((x, i) => <span key={i} className={`live-card__tick live-card__tone--${lane.tone}`} style={{ left: `${x}%` }} />)}</div>
        </div>)}
      </div>
    </section>
    <section className="live-card__box">
      <h3 className="live-card__h">Deník karty<small className="live-card__h-meta">živě · nejnovější nahoře</small></h3>
      <ul className="live-card__log" aria-live="polite">
        {recent.map((item, index) => {
          const actor = actorView(item.actor, item.kind);
          return <li key={`${item.at}-${index}`} className={`live-card__log-row${index === 0 ? " live-card__log-row--new" : ""}`} title={item.source}>
            <span className="live-card__log-time">{clock(item.at)}</span>
            <span className={`live-card__log-actor live-card__tone--${actor.tone}`}>{item.actor.replace(/^agent:/, "")}</span>
            <span className="live-card__log-text">{item.text}</span>
          </li>;
        })}
      </ul>
    </section>
  </div>;
}
