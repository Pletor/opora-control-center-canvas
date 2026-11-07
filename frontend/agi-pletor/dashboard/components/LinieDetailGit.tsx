import { useState, type ReactNode } from "react";
import type { WriteMethod } from "@/shared/types/logic/types";
import type { Judgement } from "../logic/linie-summary";
import { acceptanceSentence, previewSentence, short, workActions, type WorkDetail } from "../logic/linie-work";

type Props = {
  detail: WorkDetail; judgement: Judgement | null; main: string; flash: string;
  run: (sub: string, body: object, done: string, method?: WriteMethod) => void; onDeploy: (sha: string) => void;
};

const Row = ({ k, children }: { k: string; children: ReactNode }) => (
  <div className="pletor-dashboard__linie-kv"><span className="pletor-dashboard__linie-k">{k}</span><span>{children}</span></div>
);

/**
 * Záložka Git: větev a revize, commity, PR, kontroly, přijetí a náhled, akce člověka. Přijetí a začlenění se řídí
 * týmž pravidlem jako panel Pletora (`allowed` / `blocked`); jen když backend `allowed` ještě neposílá, platí odhad
 * `workActions` a o platnosti rozhodne backend (409).
 */
export default function LinieDetailGit({ detail: d, judgement, main, flash, run, onDeploy }: Props) {
  const [note, setNote] = useState("");
  const guess = workActions(d, main);
  const ruled = !!judgement && (judgement.allowed.length > 0 || Object.keys(judgement.blocked).length > 0);
  const can = (id: "accept" | "merge") => (ruled ? judgement!.allowed.includes(id) : guess[id]);
  const why = (id: string) => (ruled ? judgement!.blocked[id] : undefined);
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
          <input className="pletor-dashboard__input" aria-label="Poznámka k přijetí" placeholder="poznámka k přijetí" value={note} onChange={(event) => setNote(event.target.value)} />
          <span className="pletor-dashboard__tools pletor-dashboard__linie-acts">
            <button type="button" className="pletor-dashboard__button" disabled={!guess.preview} onClick={() => run("/preview", {}, "Náhled se spouští.")}>Spustit náhled</button>
            <button type="button" className="pletor-dashboard__button" disabled={!can("accept") || !d.headSha} title={why("accept")}
              onClick={() => run("/accept", { sha: d.headSha, note }, `Přijato ${short(d.headSha)}.`)}>Přijmout tuto revizi</button>
            {guess.revoke && <button type="button" className="pletor-dashboard__button" onClick={() => run("/accept", {}, "Přijetí zrušeno.", "DELETE")}>Zrušit přijetí</button>}
            <button type="button" className="pletor-dashboard__button" disabled={!guess.allow}
              onClick={() => run("/allow-merge", { target: d.target }, `Začlenění do ${d.target} povoleno.`)}>Povolit začlenění do {d.target || "—"}</button>
            <button type="button" className="pletor-dashboard__button" disabled={!can("merge")} title={why("merge")} onClick={() => run("/merge", {}, "Začleněno službou.")}>Začlenit (služba)</button>
            {guess.deploy && d.merged && <button type="button" className="pletor-dashboard__button" onClick={() => onDeploy(d.merged!.sha)}>Zapsat nasazení</button>}
          </span>
          <p className="pletor-dashboard__note">Agent tato tlačítka nikdy nestiskne za tebe.</p>
          {flash && <p className="pletor-dashboard__linie-flash" role="status">{flash}</p>}
        </div>
      </div>
    </div>
  );
}
