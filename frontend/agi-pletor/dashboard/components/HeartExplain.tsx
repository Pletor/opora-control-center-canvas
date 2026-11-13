import type { ExplainView } from "../logic/heart-explain";
import HeartStops from "./HeartStops";
import HeartPhases from "./HeartPhases";

const Err = ({ text }: { text: string }) => <p className="pletor-dashboard__error">{text}</p>;

/** Průhled srdce: věta „Teď“, zarážky, tok, čas dávek a fronta; data dostává hotová od rodiče. */
export default function HeartExplain({ view }: { view: ExplainView }) {
  return (
    <section className="heart-explain" aria-label="Průhled srdce">
      <h2 className="pletor-dashboard__group-title">Průhled srdce</h2>
      {view.now.error ? <Err text={view.now.error} /> : <p className="heart-explain__now"><b>Teď:</b> {view.now.sentence || "—"}</p>}
      <h3 className="pletor-dashboard__group-title">Kde se může zastavit</h3>
      {view.stops.error ? <Err text={view.stops.error} /> : <HeartStops stops={view.stops.rows} />}
      <h3 className="pletor-dashboard__group-title">Tok srdce</h3>
      {view.pipeline.error ? <Err text={view.pipeline.error} /> : (
        <ul className="heart-explain__pipeline">
          {view.pipeline.runs.map((r) => <li key={r.run}><b>{r.run}</b> ({r.status}): {r.line}</li>)}
          {view.pipeline.runs.length === 0 && <li className="pletor-dashboard__empty">Žádné běhy.</li>}
        </ul>
      )}
      <h3 className="pletor-dashboard__group-title">Kam šel čas dávek</h3>
      {view.batches.error ? <Err text={view.batches.error} /> : <HeartPhases batches={view.batches.rows} />}
      <h3 className="pletor-dashboard__group-title">Fronta</h3>
      {view.queue.error ? <Err text={view.queue.error} /> : (
        <table className="pletor-dashboard__table">
          <thead><tr><th>Typ</th><th>Odkaz</th><th>Prostor</th><th>Splatné za (s)</th></tr></thead>
          <tbody>
            {view.queue.rows.map((q, i) => <tr key={i}><td>{q.type}</td><td>{q.ref}</td><td>{q.workspace}</td><td>{q.dueIn}</td></tr>)}
            {view.queue.rows.length === 0 && <tr><td colSpan={4} className="pletor-dashboard__empty">Fronta je prázdná.</td></tr>}
          </tbody>
        </table>
      )}
    </section>
  );
}
