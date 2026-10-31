import type { ReactNode } from "react";
import type { HeartStatus } from "../logic/heart-api";
import { batchRows, type BatchRow } from "../logic/batch-cost";
import { statusLine } from "../logic/heart-status";
import type { StepRange, StepRow } from "../logic/heart-live";
import StepList from "./StepList";

/** Kroky jedné skončené dávky pro rozbalený řádek; `null` = ještě se nenačítaly. */
export type BatchStepsView = { loading: boolean; error: string; steps: StepRow[] } | null;

/** Řádek dávky: shrnutí a cena; s rozsahem se rozbalí na kroky (načtou se při prvním rozbalení). */
function BatchItem({ row, view, onOpen }: { row: BatchRow; view: BatchStepsView; onOpen: (key: string, range: StepRange) => void }) {
  const head = (
    <>
      <span className="heart-channel__batch-summary">{row.summary}</span>
      <span className="heart-channel__batch-cost">{row.cost}</span>
    </>
  );
  const range = row.range;
  if (!range) return <li className="heart-channel__batch"><div className="heart-channel__batch-head">{head}</div></li>;
  return (
    <li className="heart-channel__batch">
      <details onToggle={(event) => { if (event.currentTarget.open) onOpen(row.key, range); }}>
        <summary className="heart-channel__batch-head heart-channel__batch-head--open">{head}</summary>
        {view?.error ? <p className="heart-channel__steps-empty">Kroky se nenačetly: {view.error}</p>
          : !view || view.loading ? <p className="heart-channel__steps-empty">Načítám kroky…</p>
            : <StepList steps={view.steps} empty="Dávka nic nezapsala." label="Kroky dávky" />}
      </details>
    </li>
  );
}

/**
 * Srdce: stav jednou větou s tečkou, pod ním `live` (běžící dávka, skládá rodič) a posledních 5 dávek
 * (shrnutí a cena), nejnovější nahoře; dávka se rozbalí na své kroky a otevření hlásí `onOpenBatch`.
 */
export default function HeartState({ status, live, batchSteps, onOpenBatch }: {
  status: HeartStatus | null;
  live?: ReactNode;
  batchSteps: (key: string) => BatchStepsView;
  onOpenBatch: (key: string, range: StepRange) => void;
}) {
  const line = status ? statusLine(status) : null;
  const rows = status ? batchRows(status.batches) : [];
  return (
    <section className="heart-channel__section" aria-label="Stav srdce">
      <h3 className="heart-channel__heading">Srdce</h3>
      <p className={`heart-channel__state heart-channel__state--${line?.tone ?? "sleeping"}`}>
        <span className="heart-channel__state-dot" aria-hidden="true" />
        {line?.text ?? "Načítám stav…"}
      </p>
      {live}
      {rows.length > 0 && (
        <ol className="heart-channel__batches" aria-label="Poslední dávky">
          {rows.map((row) => <BatchItem key={row.key} row={row} view={batchSteps(row.key)} onOpen={onOpenBatch} />)}
        </ol>
      )}
    </section>
  );
}
