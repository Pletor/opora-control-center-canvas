import type { Lane } from "../../logic/lanes";
import { SOURCE_NAME, clock } from "../../logic/process-event";
import { CardHash, Chip, PhaseChip, StateDot } from "../../components/Marks";
import { checksOf, refsOf, turnOf } from "../logic/inspector-model";
import "../styles/card-inspector.css";

type Props = { lane: Lane | null; onOpenCard: (nodeId: string) => void };
const STATE_WORD: Record<string, [string, string]> = {
  fail: ["selhalo", "bad"], blocked: ["čeká na člověka", "bad"], wait: ["čeká", "warn"], ok: ["potvrzeno", "ok"],
  progress: ["běží", "acc"], start: ["začalo", "acc"], info: ["info", "gap"],
};

/** Inspektor vybrané karty; bez výběru řekne, co se po kliknutí na řádek ukáže. */
export default function CardInspector({ lane, onOpenCard }: Props) {
  if (!lane) return <section className="card-inspector" aria-label="Inspektor karty">
    <div className="card-inspector__panel-head"><h2 className="card-inspector__heading">Inspektor</h2><span className="card-inspector__muted">žádná karta</span></div>
    <div className="card-inspector__empty"><b className="card-inspector__empty-title">Vyberte řádek v mapě</b>
      <span>Zobrazí se časová osa karty, běh, větev, PR, kontroly a kdo je na tahu.</span></div>
  </section>;
  const turn = turnOf(lane), refs = refsOf(lane), checks = checksOf(lane);
  const [stateText, stateTone] = lane.last ? STATE_WORD[lane.last.state] : ["bez události", "gap"];
  return <section className="card-inspector" aria-label="Inspektor karty" data-oh-inspector={lane.nodeId}>
    <div className="card-inspector__head">
      <div className="card-inspector__row"><CardHash id={lane.nodeId} ghost={false} />
        <span className="card-inspector__muted">zdroj: {lane.source ? SOURCE_NAME[lane.source] : "—"}</span>
        <span className="card-inspector__grow" /><Chip tone={stateTone}>{stateText}</Chip></div>
      <h3 className="card-inspector__title">{lane.title}</h3>
      <div className="card-inspector__row"><PhaseChip phase={lane.phase} /><span className="card-inspector__muted">{lane.workerName || "bez pracovníka"}</span>
        <span className="card-inspector__grow" />
        <button type="button" className="card-inspector__open" onClick={() => onOpenCard(lane.nodeId)}>Otevřít detail karty</button></div>
    </div>
    <div className="card-inspector__grid">
      <div className="card-inspector__col">
        <div className={`card-inspector__turn${turn.human ? " card-inspector__turn--human" : ""}`} data-oh-field="turn">
          <span className="card-inspector__label">{turn.label}</span><b className="card-inspector__who">{turn.who}</b>
          <span className="card-inspector__muted">{turn.what}</span>
        </div>
        <div className="card-inspector__section"><span className="card-inspector__label">Odkazy</span>
          <dl className="card-inspector__refs">
            <dt className="card-inspector__key">Běh</dt><dd className="card-inspector__value"><code>{refs.run}</code></dd>
            <dt className="card-inspector__key">Větev</dt><dd className="card-inspector__value"><code>{refs.branch}</code></dd>
            <dt className="card-inspector__key">PR</dt><dd className="card-inspector__value">{refs.prUrl
              ? <a className="card-inspector__link" href={refs.prUrl} target="_blank" rel="noreferrer noopener">{refs.pr}</a>
              : refs.pr || <span className="card-inspector__muted">zatím bez PR</span>}</dd>
            <dt className="card-inspector__key">Commit</dt><dd className="card-inspector__value"><code>{refs.sha}</code></dd>
            <dt className="card-inspector__key">Patro</dt><dd className="card-inspector__value">{refs.floor}</dd>
          </dl></div>
        <div className="card-inspector__section"><span className="card-inspector__label">Kontroly</span>
          {checks.length ? checks.map((check) => <div key={check.key} className="card-inspector__check"><StateDot state={check.state} />
            <code className="card-inspector__check-name">{check.name}</code><span className="card-inspector__muted">{check.result}</span></div>)
            : <span className="card-inspector__muted">zatím žádná kontrola</span>}</div>
      </div>
      <div className="card-inspector__col">
        <div className="card-inspector__section"><span className="card-inspector__label">Časová osa · {lane.events.length} událostí</span></div>
        <ol className="card-inspector__timeline">
          {lane.events.map((event) => <li key={event.key} className={`card-inspector__item card-inspector__item--${event.state}`}>
            <StateDot state={event.state} />
            <div className="card-inspector__item-body">
              <div className="card-inspector__item-head"><span className="card-inspector__mono">{clock(event.at)}</span><span>{SOURCE_NAME[event.source]}</span>
                <PhaseChip phase={event.phase} /><span className="card-inspector__mono">{event.kind}</span></div>
              <span className="card-inspector__item-title">{event.title}</span>
              {event.detail && <span className="card-inspector__item-detail">{event.detail}</span>}
            </div>
          </li>)}
          {!lane.events.length && <li className="card-inspector__muted">V okně posledních událostí nic pro tuto kartu.</li>}
        </ol>
      </div>
    </div>
  </section>;
}
