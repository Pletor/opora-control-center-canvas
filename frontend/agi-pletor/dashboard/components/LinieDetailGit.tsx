import type { ReactNode } from "react";
import type { PletorAction } from "../logic/linie-actions";
import type { BoardBall } from "../logic/linie-board";
import { hhmm } from "../logic/linie-summary";
import { acceptanceSentence, short, type WorkDetail } from "../logic/linie-work";
import LinieActions from "./LinieActions";
import LinieTrial from "./LinieTrial";

type Props = { detail: WorkDetail; ball: BoardBall | null; actions: PletorAction[]; note: string; onNote: (note: string) => void; flash: string; onAct: (id: string) => void };

const Row = ({ k, children, dead }: { k: string; children: ReactNode; dead?: boolean }) => (
  <div className={`pletor-dashboard__linie-kv${dead ? " pletor-dashboard__linie-kv--dead" : ""}`}><span className="pletor-dashboard__linie-k">{k}</span><span>{children}</span></div>
);
const PR_STATE: Record<string, string> = { OPEN: "otevřen", MERGED: "sloučen", CLOSED: "zavřen" };

/**
 * Záložka Git: větev a revize, pokusy (větev z rodiče, agent), commity z boardu (opuštěné přeškrtnuté), PR s posledním
 * známým stavem, kontroly, přijetí a náhled se zkouškou a obnovou dat. Akce člověka jsou tentýž seznam jako v panelu Pletora (jen `allowed` /
 * `blocked`, jedna cesta přes rodiče); vlastní odhad tlačítek tu není.
 */
export default function LinieDetailGit({ detail: d, ball, actions, note, onNote, flash, onAct }: Props) {
  const commits = ball?.commits.length ? ball.commits.map((c) => ({ sha7: c.sha7, title: c.title, at: c.at, dead: !!c.abandoned, why: c.abandoned?.why ?? "" })) : d.commits.map((c) => ({ ...c, dead: false, why: "" }));
  const pr = ball?.pr ?? (d.pr && { ...d.pr, unconfirmed: false });
  const rest = actions.filter((a) => a.id !== "preview"); // Vyzkoušet kreslí karta náhledu
  return (
    <div className="pletor-dashboard__linie-detail-cols">
      <div className="pletor-dashboard__linie-detail-col">
        <div className="pletor-dashboard__linie-detail-card">
          <h3 className="pletor-dashboard__linie-detail-h">Větev a revize</h3>
          <Row k="větev">{d.branch || "bez větve"}</Row>
          <Row k="rodič"><span className="pletor-dashboard__mono">{d.baseBranch || "—"} @ {short(d.baseSha) || "—"}</span></Row>
          <Row k="hlava"><span className="pletor-dashboard__mono">{short(d.headSha) || "zatím bez commitu"}</span></Row>
          <Row k="cíl">{d.target || "zatím neurčeno"}</Row>
          <Row k="začlenění">{d.merged ? `${short(d.merged.sha)} do ${d.merged.target} · ${d.merged.at}` : "—"}</Row>
          {d.blocked && <Row k="blokováno">{d.blocked}</Row>}
        </div>
        <div className="pletor-dashboard__linie-detail-card">
          <h3 className="pletor-dashboard__linie-detail-h">Pokusy · {d.attempts.length}</h3>
          {d.attempts.length ? d.attempts.map((a) => <Row key={a.attemptId} k={a.branch}>{a.agent || "—"} · z {a.baseRef || "—"} · {hhmm(a.at)}{a.published ? " · v originu" : " · zatím jen lokálně"}</Row>)
            : <p className="pletor-dashboard__note">zatím bez pokusu (kancelář založí větev z rodiče podle jména)</p>}
          <h3 className="pletor-dashboard__linie-detail-h">Commity · {commits.length} · zdroj git log</h3>
          {commits.length ? [...commits].reverse().map((c) => <Row key={c.sha7} k={c.sha7} dead={c.dead}>{c.title}{c.dead && ` · opuštěno${c.why ? ` – ${c.why}` : ""}`} <span className="pletor-dashboard__note">{c.at}</span></Row>)
            : <p className="pletor-dashboard__note">zatím žádné commity</p>}
          <h3 className="pletor-dashboard__linie-detail-h">PR</h3>
          {pr ? <p><a href={pr.url} target="_blank" rel="noreferrer">PR #{pr.number} · {pr.unconfirmed ? "neověřeno (poslední známý stav" : PR_STATE[pr.state.toUpperCase()] ?? pr.state}{pr.unconfirmed ? `: ${PR_STATE[pr.state.toUpperCase()] ?? pr.state})` : ""} ↗</a></p> : <p className="pletor-dashboard__note">bez PR</p>}
        </div>
      </div>
      <div className="pletor-dashboard__linie-detail-col">
        <div className="pletor-dashboard__linie-detail-card">
          <h3 className="pletor-dashboard__linie-detail-h">Kontroly</h3>
          {d.checks.length ? d.checks.map((c) => <Row key={`${c.name}-${c.sha}`} k={c.name}>{c.status} @ {short(c.sha)}{c.sha !== d.headSha ? " (stará revize)" : ""}</Row>)
            : <p className="pletor-dashboard__note">kontroly neproběhly</p>}
          <Row k="přijetí">{acceptanceSentence(d)}</Row>
          <Row k="povolení">{d.mergeAllowed ? `do ${d.mergeAllowed.target} při ${short(d.mergeAllowed.targetSha)}` : "—"}</Row>
        </div>
        <LinieTrial trial={d.trial} actions={actions} onAct={onAct} fresh />
        <div className="pletor-dashboard__linie-detail-card">
          <h3 className="pletor-dashboard__linie-detail-h">Akce člověka</h3>
          {rest.length ? <LinieActions actions={rest} note={note} onNote={onNote} onAct={onAct} />
            : <p className="pletor-dashboard__note">Další akce nejsou; hlavní krok je v panelu Pletora.</p>}
          <p className="pletor-dashboard__note">Agent tato tlačítka nikdy nestiskne za tebe.</p>
          {flash && <p className="pletor-dashboard__linie-flash" role="status">{flash}</p>}
        </div>
      </div>
    </div>
  );
}
