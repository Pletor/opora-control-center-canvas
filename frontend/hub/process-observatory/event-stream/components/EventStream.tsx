import { SOURCE_NAME, clock, type FlowEvent } from "../../logic/process-event";
import { CardHash, PhaseChip, StateDot } from "../../components/Marks";
import "../styles/event-stream.css";

type Option = { id: string; name: string };
type Props = {
  rows: FlowEvent[]; total: number; paused: boolean; buffered: number; anyEvent: boolean;
  cards: Option[]; workers: Option[]; card: string; worker: string;
  onCard: (id: string) => void; onWorker: (id: string) => void; onTogglePause: () => void;
};

/** Proud událostí: filtr karty a pracovníka, „Pozastavit čtení“ s počítadlem a řádky nejnovější nahoře. */
export default function EventStream({ rows, total, paused, buffered, anyEvent, cards, workers, card, worker, onCard, onWorker, onTogglePause }: Props) {
  return <section className="event-stream" aria-label="Proud událostí">
    <div className="event-stream__panel-head"><h2 className="event-stream__heading">Proud událostí</h2>
      <span className="event-stream__meta">{anyEvent ? `${total} událostí · posledních 300` : "posledních 300 · nic nepřišlo"}</span></div>
    <div className="event-stream__tools">
      <select className="event-stream__select" aria-label="Filtr karty" value={card} onChange={(event) => onCard(event.target.value)}>
        <option value="">Všechny karty</option>
        {cards.map((option) => <option key={option.id} value={option.id}>{option.id} {option.name !== option.id ? option.name : ""}</option>)}
      </select>
      <select className="event-stream__select" aria-label="Filtr pracovníka" value={worker} onChange={(event) => onWorker(event.target.value)}>
        <option value="">Všichni pracovníci</option>
        {workers.map((option) => <option key={option.id} value={option.id}>{option.name}</option>)}
      </select>
      <span className="event-stream__grow" />
      <button type="button" className={`event-stream__pause${paused ? " event-stream__pause--on" : ""}`} aria-pressed={paused} onClick={onTogglePause}>
        {paused ? "Pokračovat ve čtení" : "Pozastavit čtení"}
        {paused && <span className="event-stream__counter" data-oh-field="buffered">+{buffered}</span>}
      </button>
    </div>
    {paused && <div className="event-stream__buffer" role="status">
      <span>Čtení pozastaveno — data dál přicházejí. <b>{buffered} nových událostí</b> čeká nad seznamem.</span>
      <span className="event-stream__grow" />
      <button type="button" className="event-stream__resume" onClick={onTogglePause}>Zobrazit a pokračovat</button>
    </div>}
    {!rows.length && <div className="event-stream__empty" role="status">
      <b className="event-stream__empty-title">{anyEvent ? "Filtru neodpovídá žádná událost" : "Zatím žádná událost — kancelář ani Opora nic nehlásí"}</b>
    </div>}
    <div className="event-stream__list" aria-live={paused ? "off" : "polite"}>
      {rows.map((event) => <div key={event.key} className="event-stream__row" data-oh-event={event.key}>
        <span className="event-stream__time">{clock(event.at)}</span>
        <span className="event-stream__source">{SOURCE_NAME[event.source]}</span>
        <PhaseChip phase={event.phase} />
        <span className="event-stream__title"><StateDot state={event.state} />
          <span className="event-stream__text" title={event.detail ? `${event.title}\n${event.detail}` : event.title}>{event.title}</span>
          <span className="event-stream__kind">{event.kind}</span></span>
        <span className="event-stream__card">{event.cardId ? <CardHash id={event.cardId} /> : null}</span>
      </div>)}
    </div>
  </section>;
}
