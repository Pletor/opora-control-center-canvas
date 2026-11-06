import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { logTail, previewLabel, type LinieLane } from "../logic/linie-view";

export type LinieAct = (write: Promise<unknown>, done: string) => void;
type Props = { lane: LinieLane; project: string; onAct: LinieAct };

const BASE = "/api/pletor/linie/previews";

/** Náhled větve: stav, Spustit / Otevřít ↗ / Zastavit, u selhání log (posledních 40 řádků). Zápis hlásí rodič přes `onAct`. */
export default function LiniePreview({ lane, project, onAct }: Props) {
  const [log, setLog] = useState("");
  const p = lane.preview;
  const start = () => onAct(api(BASE, { branch: lane.name, project }), `Náhled ${lane.name} se spouští.`);
  const stop = () => p && onAct(api(`${BASE}/${encodeURIComponent(p.slug)}`, {}, "DELETE"), `Náhled ${lane.name} zastaven.`);
  const showLog = () => p && api<unknown>(`${BASE}/${encodeURIComponent(p.slug)}/log`).then(
    (raw) => setLog(logTail(raw) || "Log je prázdný."),
    (failure: unknown) => setLog(failure instanceof Error ? failure.message : "Log se nenačetl."),
  );

  return (
    <div className="pletor-dashboard__linie-preview">
      <span className="pletor-dashboard__tools">
        <span className="pletor-dashboard__tag">náhled: {previewLabel(p)}</span>
        {p?.state === "running" && p.url && <a href={p.url} target="_blank" rel="noreferrer">Otevřít náhled ↗</a>}
        {(p?.state === "running" || p?.state === "building") && <button type="button" className="pletor-dashboard__button" onClick={stop}>Zastavit</button>}
        {p?.state !== "running" && p?.state !== "building" && (
          <button type="button" className="pletor-dashboard__button" disabled={!project} onClick={start}>Spustit náhled</button>
        )}
        {p?.state === "failed" && <button type="button" className="pletor-dashboard__link" onClick={() => void showLog()}>Zobrazit log</button>}
      </span>
      {log && <pre className="pletor-dashboard__pre">{log}</pre>}
    </div>
  );
}
