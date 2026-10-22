// Rozbalená časová osa: vlevo karty (značka zdraví + jméno), uprostřed dráhy se značkami, pásy pronájmu
// a čárkami heartbeatu, svislá čára „teď“ vpravo; zcela vpravo seznam posledních událostí. Klik na značku
// nebo řádek otevře detail karty na záložce, kam událost patří.
import type { CSSProperties } from "react";
import { openCardDrawer } from "@/hub/oporahub-card-drawer/logic/open";
import type { OporaEvent } from "../logic/events-client";
import { axis, type Lane, type markOf } from "../logic/live-model";

type Recent = { event: OporaEvent; name: string; text: string; mark: ReturnType<typeof markOf> };
const at = (x: number) => ({ left: `${x}%` }) as CSSProperties;

export default function LiveLanes({ lanes, windowMs, now, recent }: { lanes: Lane[]; windowMs: number; now: number; recent: Recent[] }) {
  return (
    <div className="live-strip__body">
      <div className="live-strip__grid">
        <div className="live-strip__axis-row"><span className="live-strip__names-head" />
          <div className="live-strip__axis">{axis(windowMs, now).map((tick) => <span key={tick.label} style={at(tick.x)}>{tick.label}</span>)}<span className="live-strip__now-label">teď</span></div>
        </div>
        {!lanes.length && <p className="live-strip__muted live-strip__empty">Vrstva nemá karty.</p>}
        {lanes.map((lane) => (
          <div key={lane.nodeId} className="live-strip__lane" data-oh-lane={lane.nodeId}>
            <button type="button" className="live-strip__name" onClick={() => openCardDrawer(lane.nodeId)}>
              <span aria-hidden="true">{lane.glyph}</span> {lane.name}
            </button>
            <div className="live-strip__track">
              {lane.spans.map((span, index) => <i key={index} className="live-strip__span" style={{ left: `${span.from}%`, width: `${span.to - span.from}%` }} />)}
              {lane.ticks.map((x, index) => <i key={"t" + index} className="live-strip__heartbeat" style={at(x)} />)}
              {lane.marks.map((mark) => (
                <button key={mark.id} type="button" className={"live-strip__mark live-strip__mark--" + mark.tone} style={at(mark.x)}
                  title={mark.title} aria-label={mark.title} data-oh-event={mark.id} onClick={() => openCardDrawer(lane.nodeId, mark.tab)}>{mark.glyph}</button>
              ))}
              <i className="live-strip__now" />
            </div>
          </div>
        ))}
      </div>
      <aside className="live-strip__recent" aria-label="Poslední události">
        <div className="live-strip__recent-head">Poslední události</div>
        {!recent.length && <p className="live-strip__muted live-strip__empty">Zatím nic.</p>}
        {recent.map(({ event, name, text, mark }) => (
          <button key={event.id} type="button" className="live-strip__recent-row" data-oh-event={event.id} data-oh-kind={event.kind}
            onClick={() => event.nodeId && openCardDrawer(event.nodeId, mark.tab)}>
            <time>{new Date(event.at).toLocaleTimeString("cs-CZ")}</time>
            <span className={"live-strip__glyph live-strip__glyph--" + mark.tone} aria-hidden="true">{mark.glyph}</span>
            <span className="live-strip__recent-text"><span>{name} · {text}</span><code>{event.kind}</code></span>
          </button>
        ))}
      </aside>
    </div>
  );
}
