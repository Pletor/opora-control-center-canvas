import type { Measure } from "../logic/workshop-api";
import { asJson, measureLine } from "../logic/workshop-state";

/** Výsledek měření funkce: řádek passed/total · trvání · determinismus, pak selhání a chyba běhu. */
export default function WorkshopMeasure({ measure }: { measure: Measure }) {
  const ok = !measure.error && measure.passed === measure.total && measure.deterministic;
  return (
    <section className={"pletor-workshop__measure" + (ok ? " pletor-workshop__measure--ok" : "")} aria-label="Výsledek měření" aria-live="polite">
      <p className="pletor-workshop__measure-line">
        {measureLine(measure)}
        <span className={"pletor-workshop__badge" + (measure.deterministic ? "" : " pletor-workshop__badge--warn")}>
          {measure.deterministic ? "deterministická" : "NEdeterministická"}
        </span>
      </p>
      {measure.error && <pre className="pletor-workshop__error">{measure.error}</pre>}
      {measure.failed.length > 0 && (
        <ul className="pletor-workshop__failures">
          {measure.failed.map((f, index) => (
            <li key={`${f.name}-${index}`} className="pletor-workshop__failure">
              <strong className="pletor-workshop__failure-name">{f.name || "(bez jména)"}</strong>
              <span className="pletor-workshop__failure-row">dostal: <code>{asJson(f.got)}</code></span>
              <span className="pletor-workshop__failure-row">čekal: <code>{asJson(f.expected)}</code></span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
