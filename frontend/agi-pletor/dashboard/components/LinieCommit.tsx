import "../styles/pletor-dashboard-linie-commit.css";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/shared/types/logic/types";
import { commitView, type CommitDetail } from "../logic/linie-commit";
import { failureText } from "../logic/linie-work";

type Props = { sha: string; query: string; onClose: () => void; onPickTicket: (ticketId: string) => void; onPickTrace: (mark: string) => void };

const Row = ({ k, children }: { k: string; children: ReactNode }) => (
  <div className="pletor-dashboard__linie-kv"><span className="pletor-dashboard__linie-k">{k}</span><span>{children}</span></div>
);
const Layer = ({ title, children }: { title: string; children: ReactNode }) => (
  <div className="pletor-dashboard__linie-commit-layer"><h3 className="pletor-dashboard__linie-commit-h">{title}</h3>{children}</div>
);

/**
 * Detail commitu z `GET /commit/{sha}` (docs/navrhy/2026-11-06-linie-detail-commitu.md): čtyři vrstvy Proč, Kdo, Co,
 * Kde v linii. Bez ticketu se tři z nich nahradí jedním textem; nic se nevymýšlí.
 */
export default function LinieCommit({ sha, query, onClose, onPickTicket, onPickTrace }: Props) {
  const [d, setD] = useState<CommitDetail | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setD(null);
    api<unknown>(`/api/pletor/linie/commit/${encodeURIComponent(sha)}?${query}`).then(
      (raw) => { if (live) { setD(commitView(raw)); setError(""); } },
      (failure: unknown) => { if (live) setError(failureText(failure, "Commit se nenačetl.")); },
    );
    return () => { live = false; };
  }, [sha, query]);

  const close = <button type="button" className="pletor-dashboard__button" onClick={onClose}>Zavřít</button>;
  if (!d) return (
    <section className="pletor-dashboard__linie-commit" aria-label="Detail commitu">
      {close}
      {error ? <p className="pletor-dashboard__error" role="alert">{error}</p> : <p className="pletor-dashboard__note" role="status">Načítám commit…</p>}
    </section>
  );

  const { commit: c, ticket: t, pr, preview } = d;
  const mark = t?.mark || c.mark;
  return (
    <section className="pletor-dashboard__linie-commit" aria-label="Detail commitu">
      <div className="pletor-dashboard__linie-commit-head">
        <p className="pletor-dashboard__linie-commit-sentence">{mark && <strong>{mark} </strong>}{d.sentence}</p>
        {mark && <button type="button" className="pletor-dashboard__button" onClick={() => onPickTrace(mark)}>Celá cesta</button>}
        {close}
      </div>

      {!t ? (
        <div className="pletor-dashboard__linie-commit-layer pletor-dashboard__linie-commit-layer--none">bez evidovaného plánu (žádný ticket)</div>
      ) : (
        <>
          <Layer title="Proč">
            {t.card && <Row k="karta">{t.card.name || t.card.id} · <a href={t.card.link}>otevřít na plátně</a></Row>}
            <Row k="podstata">{t.essence || "—"}</Row>
            <Row k="stavba">{t.build || "—"}</Row>
            <Row k="hotovo když">{t.doneCriteria.length ? <ul className="pletor-dashboard__linie-commit-list">{t.doneCriteria.map((x) => <li key={x}>{x}</li>)}</ul> : "—"}</Row>
            {t.plan.length > 0 && (
              <Row k="kroky plánu"><ol className="pletor-dashboard__linie-commit-list">
                {t.plan.map((s) => <li key={s.id}>{s.title}{s.acceptance && <span className="pletor-dashboard__note"> · {s.acceptance}</span>}</li>)}
              </ol></Row>
            )}
          </Layer>
          <Layer title="Kdo">
            {t.office ? (
              <>
                <Row k="dělník">{t.office.worker || "—"}{t.office.role && ` (${t.office.role})`}</Row>
                <Row k="zadavatel">{[t.office.department, t.office.profile].filter(Boolean).join(" / ") || "—"}</Row>
                <Row k="exekuce"><span className="pletor-dashboard__mono">{t.office.executionId || "—"}</span></Row>
              </>
            ) : <p className="pletor-dashboard__note">kancelář neevidována</p>}
          </Layer>
        </>
      )}

      <Layer title="Co">
        <Row k="commit"><span className="pletor-dashboard__mono">{c.sha7}</span> {c.title}</Row>
        <Row k="soubory">{c.stat || c.files || "—"}</Row>
        {c.paths.length > 0 && <ul className="pletor-dashboard__linie-commit-paths">{c.paths.map((path) => <li key={path} className="pletor-dashboard__mono">{path}</li>)}</ul>}
        <Row k="větve">{c.branches.join(", ") || "—"}</Row>
        <Row k="PR">{pr ? <a href={pr.url} target="_blank" rel="noreferrer">PR #{pr.number} ({pr.state}) ↗</a> : "bez PR"}</Row>
        {preview?.url && <button type="button" className="pletor-dashboard__button" onClick={() => window.open(preview.url, "_blank", "noopener")}>Otevřít náhled</button>}
      </Layer>

      {t && (
        <Layer title="Kde v linii">
          <Row k="kulička"><button type="button" className="pletor-dashboard__button" onClick={() => onPickTicket(t.ticketId)}>{t.title || t.ticketId}</button></Row>
          <Row k="stav">{t.stateLabel || t.state || "—"}</Row>
          <Row k="další krok">{t.next || "—"}</Row>
        </Layer>
      )}
    </section>
  );
}
