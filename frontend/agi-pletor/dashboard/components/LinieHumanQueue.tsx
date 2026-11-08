import "../styles/pletor-dashboard-linie-human-queue.css";
import { useState } from "react";
import { verified, type HumanRow } from "../logic/linie-human-queue";
import { newsCount, newsLines, primaryChoice, trialButton, trialSentence, triedSentence } from "../logic/linie-trial";
import LinieTrialButton from "./LinieTrialButton";
import LinieTrialSteps from "./LinieTrialSteps";
import LinieUntested from "./LinieUntested";

type Props = {
  rows: HumanRow[]; idle: string; said: Record<string, string>;
  onAct: (row: HumanRow, untested: boolean) => Promise<unknown>; onTrial: (row: HumanRow, kind: "start" | "tried") => Promise<unknown>;
};

/**
 * „Čeká na tebe“ nad grafem: seznam rozhodnutí v pořadí služby, jeden řádek = jedna karta s jediným tlačítkem.
 * Dokud zkouška neplatí pro hlavu, je tím tlačítkem Vyzkoušet a přijmout jde jen výslovně „bez zkoušky“ (zkouška §7).
 * Výsledek akce (nebo věta odmítnutí s opravou) přijde od rodiče v `said`; dokud akce běží, tlačítka jsou zamčená.
 */
export default function LinieHumanQueue({ rows, idle, said, onAct, onTrial }: Props) {
  const [busy, setBusy] = useState("");
  if (!rows.length) return <p className="linie-human-queue linie-human-queue__idle" role="status">{idle}</p>;
  const run = (row: HumanRow, job: Promise<unknown>) => { setBusy(row.ticketId); void job.finally(() => setBusy("")); };
  return (
    <ol className="linie-human-queue" aria-label="Čeká na tebe">
      {rows.map((row) => {
        const t = row.trial, news = newsCount(t);
        return (
          <li key={row.ticketId} className={`linie-human-queue__row${row.action ? "" : " linie-human-queue__row--waiting"}`}>
            <span className="linie-human-queue__order">{row.order}</span>
            <div className="linie-human-queue__body">
              <p className="linie-human-queue__title">
                <span className="linie-human-queue__mono">{row.mark}</span> {row.title}
                <span className="linie-human-queue__mono linie-human-queue__sha">{row.sha.slice(0, 7) || "bez revize"}</span>
              </p>
              <p className="linie-human-queue__meta">{row.state} · {verified(row)}</p>
              <p className="linie-human-queue__meta">
                náhled {trialSentence(t)}{t.url && <> · <a href={t.url} target="_blank" rel="noreferrer">{t.url}</a></>} · {triedSentence(t)}
              </p>
              <LinieTrialSteps steps={t.steps} />
              {news > 0 && (
                <details className="linie-human-queue__news">
                  <summary>{news} nových od zkoušky</summary>
                  <ul>{newsLines(t).map((line) => <li key={line}>{line}</li>)}</ul>
                </details>
              )}
              <p className="linie-human-queue__sentence">{row.action ? row.sentence : `Čeká: ${row.next}`}</p>
              {said[row.ticketId] && <p className="linie-human-queue__said" role="status">{said[row.ticketId]}</p>}
            </div>
            {row.action && (primaryChoice(t) === "try" ? (
              <span className="linie-human-queue__try">
                <LinieTrialButton button={trialButton(t)} url={t.url} busy={busy === row.ticketId}
                  onStart={() => run(row, onTrial(row, "start"))} onTried={() => run(row, onTrial(row, "tried"))} />
                <LinieUntested disabled={busy !== ""} onConfirm={() => run(row, onAct(row, true))} />
              </span>
            ) : (
              <button type="button" className="linie-human-queue__act" disabled={busy !== ""} onClick={() => run(row, onAct(row, false))}>
                {busy === row.ticketId ? "Probíhá…" : row.action.label}
              </button>
            ))}
          </li>
        );
      })}
    </ol>
  );
}
