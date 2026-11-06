import "../styles/pletor-dashboard-linie-detail.css";
import { useEffect, useState, type ReactNode } from "react";
import { api, type WriteMethod } from "@/shared/types/logic/types";
import { acceptanceSentence, failureText, previewSentence, short, workActions, workDetail, type WorkDetail } from "../logic/linie-work";

/** Zápis přes rodiče: vrátí větu k zobrazení (hotovo, nebo `message` odmítnutí 409). */
export type LinieAct = (path: string, body: object, done: string, method?: WriteMethod) => Promise<string>;
type Props = { ticketId: string; query: string; main: string; onAct: LinieAct; onClose: () => void; onPickTrace: (mark: string) => void };

const Row = ({ k, children }: { k: string; children: ReactNode }) => (
  <div className="pletor-dashboard__linie-kv"><span className="pletor-dashboard__linie-k">{k}</span><span>{children}</span></div>
);

/**
 * Detail kuličky z `GET /work/{ticketId}`: zadání, větev a revize, commity, PR, kontroly, přijetí, cíl a náhled s revizí.
 * Tlačítka mačká jen člověk; po každé akci se detail načte znovu a odmítnutí backendu se ukáže textem.
 */
export default function LinieDetail({ ticketId, query, main, onAct, onClose, onPickTrace }: Props) {
  const [detail, setDetail] = useState<WorkDetail | null>(null);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [note, setNote] = useState("");
  const [round, setRound] = useState(0);
  const path = `/work/${encodeURIComponent(ticketId)}`;
  useEffect(() => {
    let live = true;
    api<unknown>(`/api/pletor/linie${path}?${query}`).then(
      (raw) => { if (live) { setDetail(workDetail(raw)); setError(""); } },
      (failure: unknown) => { if (live) setError(failureText(failure, "Detail se nenačetl.")); },
    );
    return () => { live = false; };
  }, [path, query, round]);

  if (!detail) return (
    <section className="pletor-dashboard__linie-detail" aria-label="Detail kuličky">
      <button type="button" className="pletor-dashboard__button" onClick={onClose}>← zpět na linii</button>
      {error ? <p className="pletor-dashboard__error" role="alert">{error}</p> : <p className="pletor-dashboard__note" role="status">Načítám detail…</p>}
    </section>
  );

  const d = detail;
  const can = workActions(d, main);
  const run = (sub: string, body: object, done: string, method?: WriteMethod) => {
    setFlash("");
    void onAct(`${path}${sub}`, body, done, method).then((text) => { setFlash(text); setRound((n) => n + 1); });
  };

  return (
    <section className="pletor-dashboard__linie-detail" aria-label="Detail kuličky">
      <div className="pletor-dashboard__linie-detail-head">
        <button type="button" className="pletor-dashboard__button" onClick={onClose}>← zpět na linii</button>
        <h2 className="pletor-dashboard__linie-detail-title">{d.title || d.ticketId}</h2>
        <span className="pletor-dashboard__tag">{d.stateLabel || d.state}</span>
        {d.mark && <><span className="pletor-dashboard__mono">{d.mark}</span><button type="button" className="pletor-dashboard__button" onClick={() => onPickTrace(d.mark)}>Celá cesta</button></>}
        {d.next && <span className="pletor-dashboard__note">další krok: {d.next}</span>}
      </div>
      <div className="pletor-dashboard__linie-detail-cols">
        <div className="pletor-dashboard__linie-detail-col">
          <div className="pletor-dashboard__linie-detail-card">
            <h3 className="pletor-dashboard__linie-detail-h">Zadání</h3>
            <Row k="podstata">{d.essence || "—"}</Row>
            <Row k="stavba">{d.build || "—"}</Row>
            <Row k="hotovo když">{d.doneCriteria || "—"}</Row>
          </div>
          <div className="pletor-dashboard__linie-detail-card">
            <h3 className="pletor-dashboard__linie-detail-h">Větev a revize</h3>
            <Row k="větev">{d.branch || "bez větve"}</Row>
            <Row k="báze"><span className="pletor-dashboard__mono">{d.baseBranch || "—"} @ {short(d.baseSha) || "—"}</span></Row>
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
          </div>
          <div className="pletor-dashboard__linie-detail-card">
            <h3 className="pletor-dashboard__linie-detail-h">Přijetí a náhled</h3>
            <Row k="přijetí">{acceptanceSentence(d)}</Row>
            <Row k="povolení">{d.mergeAllowed ? `do ${d.mergeAllowed.target} při ${short(d.mergeAllowed.targetSha)}` : "—"}</Row>
            <Row k="náhled">{previewSentence(d)}{d.preview?.url && <> · <a href={d.preview.url} target="_blank" rel="noreferrer">otevřít ↗</a></>}</Row>
          </div>
          <div className="pletor-dashboard__linie-detail-card">
            <h3 className="pletor-dashboard__linie-detail-h">Akce člověka</h3>
            <input className="pletor-dashboard__input" aria-label="Poznámka k přijetí" placeholder="poznámka k přijetí" value={note} onChange={(event) => setNote(event.target.value)} />
            <span className="pletor-dashboard__tools pletor-dashboard__linie-acts">
              <button type="button" className="pletor-dashboard__button" disabled={!can.preview} onClick={() => run("/preview", {}, "Náhled se spouští.")}>Spustit náhled</button>
              <button type="button" className="pletor-dashboard__button" disabled={!can.accept}
                onClick={() => run("/accept", { sha: d.headSha, note }, `Přijato ${short(d.headSha)}.`)}>Přijmout tuto revizi</button>
              {can.revoke && <button type="button" className="pletor-dashboard__button" onClick={() => run("/accept", {}, "Přijetí zrušeno.", "DELETE")}>Zrušit přijetí</button>}
              <button type="button" className="pletor-dashboard__button" disabled={!can.allow}
                onClick={() => run("/allow-merge", { target: d.target }, `Začlenění do ${d.target} povoleno.`)}>Povolit začlenění do {d.target || "—"}</button>
              <button type="button" className="pletor-dashboard__button" disabled={!can.merge} onClick={() => run("/merge", {}, "Začleněno službou.")}>Začlenit (služba)</button>
              {can.deploy && d.merged && (
                <button type="button" className="pletor-dashboard__button"
                  onClick={() => { setFlash(""); void onAct("/deployed", { sha: d.merged!.sha }, `Nasazení zapsáno: ${short(d.merged!.sha)}.`).then(setFlash); }}>Zapsat nasazení</button>
              )}
            </span>
            <p className="pletor-dashboard__note">Agent tato tlačítka nikdy nestiskne za tebe.</p>
            {flash && <p className="pletor-dashboard__linie-flash" role="status">{flash}</p>}
          </div>
        </div>
      </div>
    </section>
  );
}
