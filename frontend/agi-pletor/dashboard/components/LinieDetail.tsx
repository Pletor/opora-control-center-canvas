import "../styles/pletor-dashboard-linie-detail.css";
import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import type { PletorAction } from "../logic/linie-actions";
import type { BoardBall } from "../logic/linie-board";
import { plural } from "../logic/linie-queues";
import { hhmm, type Judgement } from "../logic/linie-summary";
import { failureText, workDetail, type WorkDetail } from "../logic/linie-work";
import LinieDetailGit from "./LinieDetailGit";
import LinieDetailPlan from "./LinieDetailPlan";
import LinieDetailSummary from "./LinieDetailSummary";

type Props = {
  ticketId: string; query: string; ball: BoardBall | null;
  /** Počet začleněných kuliček téže větve, na které kulička navazuje (znovuotevřená větev, §10.3). */
  follows: number; cluster: { ticketId: string; title: string }[];
  /** Tiknutí boardu (čas posledního úspěšného čtení): detail se načte znovu se stejnou revizí dat jako board. */
  revision: number | null;
  actions: PletorAction[]; note: string; onNote: (note: string) => void; flash: string; onAct: (id: string) => void;
  onClose: () => void; onPickTrace: (mark: string) => void; onPick: (ticketId: string) => void;
  /** Načtený detail jde nahoru: rodič z něj bere plnou revizi HEAD a cíl pro akce. */
  onLoad: (detail: WorkDetail | null) => void;
};
type Tab = "souhrn" | "plan" | "git" | "relace";
const TABS: [Tab, string][] = [["souhrn", "Souhrn"], ["plan", "Plán"], ["git", "Git"], ["relace", "Relace"]];

/**
 * Detail kuličky z `GET /work/{ticketId}` se záložkami Souhrn (pět os, pravidlo, další krok) · Plán (vazba na kartu,
 * rozdíl revize, zadání) · Git (pokusy, commity, PR, kontroly, akce) · Relace (agenti z `work.runs`). Drobek nad ním:
 * plátno 2 › plátno 3 › značka. Souhrn čte tentýž `judgement` z boardu jako panel Pletora a obnovuje se s každým
 * tiknutím boardu, takže oba mluví o téže revizi; akce provádí rodič jednou cestou.
 */
export default function LinieDetail({ ticketId, query, ball, follows, cluster, revision, actions, note, onNote, flash, onAct, onClose, onPickTrace, onPick, onLoad }: Props) {
  const [detail, setDetail] = useState<WorkDetail | null>(null);
  const [error, setError] = useState("");
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
    return () => { live = false; };
  }, [path, query, revision]);
  useEffect(() => () => loaded.current(null), [path]);

  const judgement: Judgement | null = ball?.judgement ?? null;
  const head = (title: string) => (
    <div className="pletor-dashboard__linie-detail-head">
      <h2 className="pletor-dashboard__linie-detail-title">{title}</h2>
      <button type="button" className="pletor-dashboard__linie-icon" aria-label="Zavřít detail (Esc)" title="Zavřít (Esc)" onClick={onClose}>✕</button>
    </div>
  );
  if (!detail || detail.ticketId !== ticketId) return (
    <section className="pletor-dashboard__linie-detail" aria-label="Detail kuličky">
      {head("Detail kuličky")}
      {error ? <p className="pletor-dashboard__error" role="alert">{error}</p> : <p className="pletor-dashboard__note" role="status">Načítám detail…</p>}
    </section>
  );

  const d = detail, plan = judgement?.plan ?? null;
  return (
    <section className="pletor-dashboard__linie-detail" aria-label="Detail kuličky">
      {head(d.title || d.ticketId)}
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
      <p className="pletor-dashboard__linie-detail-crumb">
        <span title="plátno 2 · směr">{plan?.directionCardId ? `směr ${plan.directionCardId}` : "směr —"}</span> › <span title="plátno 3 · plán">{plan?.planCardId ? `plán ${plan.planCardId}` : plan?.text || "plán —"}</span> › <span className="pletor-dashboard__mono">{d.mark || d.ticketId}</span>
      </p>
      <div className="pletor-dashboard__linie-detail-meta">
        <span className="pletor-dashboard__tag">{judgement?.summary.text || d.stateLabel || d.state}</span>
        {d.mark && <button type="button" className="pletor-dashboard__button" onClick={() => onPickTrace(d.mark)}>Celá cesta</button>}
      </div>
      {follows > 0 && <p className="pletor-dashboard__note">navazuje na {plural(follows, "začleněnou kuličku", "začleněné kuličky", "začleněných kuliček")} této větve</p>}
      <div className="pletor-dashboard__tools" role="tablist" aria-label="Záložky detailu">
        {TABS.map(([id, text]) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} className="pletor-dashboard__linie-tab" onClick={() => setTab(id)}>{text}</button>
        ))}
      </div>
      {tab === "souhrn" && <LinieDetailSummary judgement={judgement} detail={d} cluster={cluster} onPick={onPick} />}
      {tab === "plan" && <LinieDetailPlan plan={plan} detail={d} query={query} />}
      {tab === "git" && <LinieDetailGit detail={d} ball={ball} actions={actions} note={note} onNote={onNote} flash={flash} onAct={onAct} />}
      {tab === "relace" && (
        <div className="pletor-dashboard__linie-detail-card">
          <h3 className="pletor-dashboard__linie-detail-h">Relace agentů · {d.runs.length} · zdroj run</h3>
          {d.runs.map((run) => (
            <div key={run.runId} className="pletor-dashboard__linie-kv"><span className="pletor-dashboard__linie-k pletor-dashboard__mono">{run.runId.slice(0, 12)}</span>
              <span>{run.agent || "agent"} · od {hhmm(run.startedAt)} · naposledy {hhmm(run.heartbeat)}{run.worktree ? ` · ⌂ ${run.worktree}` : " · bez worktree (neověřená)"}</span></div>
          ))}
          {judgement?.axes?.work.state === "in_progress" && judgement.summary.text.includes("neověřeno") && (
            <p className="pletor-dashboard__linie-plan-diff">Žádná živá relace. Stav práce je neověřený, dokud se agent nepřihlásí nebo nepřijde commit.</p>
          )}
          {!d.runs.length && <p className="pletor-dashboard__note">zatím žádná relace</p>}
        </div>
      )}
    </section>
  );
}
