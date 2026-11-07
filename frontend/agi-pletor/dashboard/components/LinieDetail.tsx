import "../styles/pletor-dashboard-linie-detail.css";
import { useEffect, useRef, useState } from "react";
import { api, type WriteMethod } from "@/shared/types/logic/types";
import type { Judgement } from "../logic/linie-summary";
import { failureText, short, workDetail, type WorkDetail } from "../logic/linie-work";
import LinieDetailGit from "./LinieDetailGit";
import LinieDetailSummary from "./LinieDetailSummary";

/** Zápis přes rodiče: vrátí větu k zobrazení (hotovo, nebo `message` odmítnutí 409). */
export type LinieAct = (path: string, body: object, done: string, method?: WriteMethod) => Promise<string>;
type Props = {
  ticketId: string; query: string; main: string; judgement: Judgement | null; cluster: { ticketId: string; title: string }[];
  onAct: LinieAct; onClose: () => void; onPickTrace: (mark: string) => void; onPick: (ticketId: string) => void;
  /** Načtený detail jde nahoru: panel Pletora z něj bere plnou revizi HEAD pro přijetí. */
  onLoad: (detail: WorkDetail | null) => void;
};
type Tab = "souhrn" | "git";

/**
 * Detail kuličky z `GET /work/{ticketId}` se záložkami Souhrn (pět os, důvod, další krok) a Git (revize, commity,
 * PR, kontroly, akce). Souhrn čte tentýž `judgement` z boardu jako panel Pletora, takže oba říkají stejný další krok.
 */
export default function LinieDetail({ ticketId, query, main, judgement, cluster, onAct, onClose, onPickTrace, onPick, onLoad }: Props) {
  const [detail, setDetail] = useState<WorkDetail | null>(null);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [round, setRound] = useState(0);
  const [tab, setTab] = useState<Tab>("souhrn");
  const loaded = useRef(onLoad);
  loaded.current = onLoad;
  const path = `/work/${encodeURIComponent(ticketId)}`;
  useEffect(() => {
    let live = true;
    api<unknown>(`/api/pletor/linie${path}?${query}`).then(
      (raw) => { if (live) { const next = workDetail(raw); setDetail(next); setError(""); loaded.current(next); } },
      (failure: unknown) => { if (live) setError(failureText(failure, "Detail se nenačetl.")); },
    );
    return () => { live = false; loaded.current(null); };
  }, [path, query, round]);

  const head = (title: string) => (
    <div className="pletor-dashboard__linie-detail-head">
      <h2 className="pletor-dashboard__linie-detail-title">{title}</h2>
      <button type="button" className="pletor-dashboard__linie-icon" aria-label="Zavřít detail (Esc)" title="Zavřít (Esc)" onClick={onClose}>✕</button>
    </div>
  );
  if (!detail) return (
    <section className="pletor-dashboard__linie-detail" aria-label="Detail kuličky">
      {head("Detail kuličky")}
      {error ? <p className="pletor-dashboard__error" role="alert">{error}</p> : <p className="pletor-dashboard__note" role="status">Načítám detail…</p>}
    </section>
  );

  const d = detail;
  const run = (sub: string, body: object, done: string, method?: WriteMethod) => {
    setFlash("");
    void onAct(`${path}${sub}`, body, done, method).then((text) => { setFlash(text); setRound((n) => n + 1); });
  };
  const deploy = (sha: string) => { setFlash(""); void onAct("/deployed", { sha }, `Nasazení zapsáno: ${short(sha)}.`).then(setFlash); };

  return (
    <section className="pletor-dashboard__linie-detail" aria-label="Detail kuličky">
      {head(d.title || d.ticketId)}
      <div className="pletor-dashboard__linie-detail-meta">
        <span className="pletor-dashboard__tag">{judgement?.summary.text || d.stateLabel || d.state}</span>
        {d.mark && <><span className="pletor-dashboard__mono">{d.mark}</span><button type="button" className="pletor-dashboard__button" onClick={() => onPickTrace(d.mark)}>Celá cesta</button></>}
      </div>
      <div className="pletor-dashboard__tools" role="tablist" aria-label="Záložky detailu">
        {(["souhrn", "git"] as Tab[]).map((id) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} className="pletor-dashboard__linie-tab" onClick={() => setTab(id)}>{id === "souhrn" ? "Souhrn" : "Git"}</button>
        ))}
      </div>
      {tab === "souhrn"
        ? <LinieDetailSummary judgement={judgement} detail={d} cluster={cluster} onPick={onPick} />
        : <LinieDetailGit detail={d} judgement={judgement} main={main} flash={flash} run={run} onDeploy={deploy} />}
    </section>
  );
}
