import type { ReactNode } from "react";
import type { PletorAction } from "../logic/linie-actions";
import { acceptanceSentence, previewSentence, short, type WorkDetail } from "../logic/linie-work";

type Props = { detail: WorkDetail; actions: PletorAction[]; flash: string; onAct: (id: string) => void };

const Row = ({ k, children }: { k: string; children: ReactNode }) => (
  <div className="pletor-dashboard__linie-kv"><span className="pletor-dashboard__linie-k">{k}</span><span>{children}</span></div>
);

/**
 * Záložka Git: větev a revize, commity, PR, kontroly, přijetí a náhled. Akce člověka jsou tentýž seznam jako v panelu
 * Pletora (jen `allowed` / `blocked`, jedna cesta přes rodiče); vlastní odhad tlačítek tu není.
 */
export default function LinieDetailGit({ detail: d, actions, flash, onAct }: Props) {
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
          <h3 className="pletor-dashboard__linie-detail-h">Commity · {d.commits.length}</h3>
          {d.commits.length ? d.commits.map((c) => <Row key={c.sha7} k={c.sha7}>{c.title} <span className="pletor-dashboard__note">{c.at}</span></Row>)
            : <p className="pletor-dashboard__note">zatím žádné commity</p>}
          <h3 className="pletor-dashboard__linie-detail-h">PR</h3>
          {d.pr ? <a href={d.pr.url} target="_blank" rel="noreferrer">PR #{d.pr.number} ({d.pr.state}) ↗</a> : <p className="pletor-dashboard__note">bez PR</p>}
        </div>
      </div>
      <div className="pletor-dashboard__linie-detail-col">
        <div className="pletor-dashboard__linie-detail-card">
          <h3 className="pletor-dashboard__linie-detail-h">Kontroly</h3>
          {d.checks.length ? d.checks.map((c) => <Row key={`${c.name}-${c.sha}`} k={c.name}>{c.status} @ {short(c.sha)}{c.sha !== d.headSha ? " (stará revize)" : ""}</Row>)
            : <p className="pletor-dashboard__note">kontroly neproběhly</p>}
          <Row k="přijetí">{acceptanceSentence(d)}</Row>
          <Row k="povolení">{d.mergeAllowed ? `do ${d.mergeAllowed.target} při ${short(d.mergeAllowed.targetSha)}` : "—"}</Row>
          <Row k="náhled">{previewSentence(d)}{d.preview?.url && <> · <a href={d.preview.url} target="_blank" rel="noreferrer">otevřít ↗</a></>}</Row>
        </div>
        <div className="pletor-dashboard__linie-detail-card">
          <h3 className="pletor-dashboard__linie-detail-h">Akce člověka</h3>
          {actions.length ? (
            <span className="pletor-dashboard__tools pletor-dashboard__linie-acts">
              {actions.map((action) => (
                <button key={action.id} type="button" className="pletor-dashboard__button" disabled={!action.enabled} title={action.why || undefined}
                  onClick={() => onAct(action.id)}>{action.label}</button>
              ))}
            </span>
          ) : <p className="pletor-dashboard__note">Backend zatím nepovolil žádnou akci (bez `allowed`).</p>}
          <p className="pletor-dashboard__note">Agent tato tlačítka nikdy nestiskne za tebe.</p>
          {flash && <p className="pletor-dashboard__linie-flash" role="status">{flash}</p>}
        </div>
      </div>
    </div>
  );
}
