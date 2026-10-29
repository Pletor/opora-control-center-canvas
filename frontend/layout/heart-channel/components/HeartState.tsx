import type { HeartStatus } from "../logic/heart-api";
import { batchRows } from "../logic/batch-cost";
import { statusLine } from "../logic/heart-status";

/** Srdce: stav jednou větou s tečkou a posledních 5 dávek (shrnutí a cena), nejnovější nahoře. */
export default function HeartState({ status }: { status: HeartStatus | null }) {
  const line = status ? statusLine(status) : null;
  const rows = status ? batchRows(status.batches) : [];
  return (
    <section className="heart-channel__section" aria-label="Stav srdce">
      <h3 className="heart-channel__heading">Srdce</h3>
      <p className={`heart-channel__state heart-channel__state--${line?.tone ?? "sleeping"}`}>
        <span className="heart-channel__state-dot" aria-hidden="true" />
        {line?.text ?? "Načítám stav…"}
      </p>
      {rows.length > 0 && (
        <ol className="heart-channel__batches" aria-label="Poslední dávky">
          {rows.map((row) => (
            <li key={row.key} className="heart-channel__batch">
              <span className="heart-channel__batch-summary">{row.summary}</span>
              <span className="heart-channel__batch-cost">{row.cost}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
