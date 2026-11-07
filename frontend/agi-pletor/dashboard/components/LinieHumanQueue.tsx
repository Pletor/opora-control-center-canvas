import "../styles/pletor-dashboard-linie-human-queue.css";
import { useState } from "react";
import { verified, type HumanRow } from "../logic/linie-human-queue";

type Props = { rows: HumanRow[]; idle: string; said: Record<string, string>; onAct: (row: HumanRow) => Promise<unknown> };

/**
 * „Čeká na tebe“ nad grafem: seznam rozhodnutí v pořadí služby, jeden řádek = jedna karta s jediným tlačítkem.
 * Výsledek akce (nebo věta odmítnutí s opravou) přijde od rodiče v `said`; dokud akce běží, tlačítko je zamčené.
 */
export default function LinieHumanQueue({ rows, idle, said, onAct }: Props) {
  const [busy, setBusy] = useState("");
  if (!rows.length) return <p className="linie-human-queue linie-human-queue__idle" role="status">{idle}</p>;
  const act = (row: HumanRow) => { setBusy(row.ticketId); void onAct(row).finally(() => setBusy("")); };
  return (
    <ol className="linie-human-queue" aria-label="Čeká na tebe">
      {rows.map((row) => (
        <li key={row.ticketId} className={`linie-human-queue__row${row.action ? "" : " linie-human-queue__row--waiting"}`}>
          <span className="linie-human-queue__order">{row.order}</span>
          <div className="linie-human-queue__body">
            <p className="linie-human-queue__title">
              <span className="linie-human-queue__mono">{row.mark}</span> {row.title}
              <span className="linie-human-queue__mono linie-human-queue__sha">{row.sha.slice(0, 7) || "bez revize"}</span>
            </p>
            <p className="linie-human-queue__meta">{row.state} · {verified(row)}</p>
            <p className="linie-human-queue__sentence">{row.action ? row.sentence : `Čeká: ${row.next}`}</p>
            {said[row.ticketId] && <p className="linie-human-queue__said" role="status">{said[row.ticketId]}</p>}
          </div>
          {row.action && (
            <button type="button" className="linie-human-queue__act" disabled={busy !== ""} onClick={() => act(row)}>
              {busy === row.ticketId ? "Probíhá…" : row.action.label}
            </button>
          )}
        </li>
      ))}
    </ol>
  );
}
