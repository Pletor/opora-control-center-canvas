import "../styles/pletor-dashboard-linie-trace.css";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/shared/types/logic/types";
import { statusLabel, traceView, type EdgeStatus, type TraceView } from "../logic/linie-trace";
import { failureText } from "../logic/linie-work";

type Props = { mark: string; query: string; onClose: () => void; onPickTicket: (ticketId: string) => void; onPickCommit: (sha: string) => void };

const Row = ({ k, children }: { k: string; children: ReactNode }) => (
  <div className="pletor-dashboard__linie-kv"><span className="pletor-dashboard__linie-k">{k}</span><span>{children}</span></div>
);
const Layer = ({ title, children }: { title: string; children: ReactNode }) => (
  <div className="linie-trace__layer"><h3 className="linie-trace__h">{title}</h3>{children}</div>
);
const Status = ({ status }: { status: EdgeStatus }) => <span className={`linie-trace__status linie-trace__status--${status}`}>{statusLabel(status)}</span>;

/**
 * Cesta OP-… z `GET /trace/{mark}` (docs/navrhy/2026-11-06-linie-vodotisk-cesty.md): pět vrstev Proč, Kdo, Co, Kde
 * a Mezery. Každá hrana nese štítek stavu; chybějící článek se přizná, nic se nedomýšlí.
 */
export default function LinieTrace({ mark, query, onClose, onPickTicket, onPickCommit }: Props) {
  const [d, setD] = useState<TraceView | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setD(null);
    api<unknown>(`/api/pletor/linie/trace/${encodeURIComponent(mark)}?${query}`).then(
      (raw) => { if (live) { setD(traceView(raw)); setError(""); } },
      (failure: unknown) => { if (live) setError(failureText(failure, "Cesta se nenačetla.")); },
    );
    return () => { live = false; };
  }, [mark, query]);

  const close = <button type="button" className="pletor-dashboard__button" onClick={onClose}>Zavřít</button>;
  if (!d) return (
    <section className="linie-trace" aria-label="Cesta práce">
      {close}
      {error ? <p className="pletor-dashboard__error" role="alert">{error}</p> : <p className="pletor-dashboard__note" role="status">Načítám cestu…</p>}
    </section>
  );

  const { ticket: t, card, preview } = d;
  return (
    <section className="linie-trace" aria-label="Cesta práce">
      <div className="linie-trace__head">
        <p className="linie-trace__sentence"><strong>{d.mark || mark}</strong> {d.sentence}</p>
        {close}
      </div>

      <Layer title="Proč">
        {card ? <Row k="karta">{card.name || card.id} · <a href={card.link}>otevřít na plátně</a>{!card.known && " (neznámá)"}</Row> : <Row k="karta"><Status status="missing" /></Row>}
        <Row k="revize">{d.revision || "—"}</Row>
        <Row k="podstata">{t?.essence || "—"}</Row>
        <Row k="stavba">{t?.build || "—"}</Row>
        <Row k="hotovo když">{t?.doneCriteria.length ? <ul className="linie-trace__list">{t.doneCriteria.map((x) => <li key={x}>{x}</li>)}</ul> : "—"}</Row>
        {d.plan.length > 0 && (
          <Row k="kroky"><ol className="linie-trace__list">
            {d.plan.map((s) => <li key={s.id}>{s.title}{s.acceptance && <span className="pletor-dashboard__note"> · {s.acceptance}</span>}</li>)}
          </ol></Row>
        )}
        {t && <Row k="kulička"><button type="button" className="pletor-dashboard__button" onClick={() => onPickTicket(t.ticketId)}>{t.title || t.ticketId}</button> {t.stateLabel}</Row>}
      </Layer>

      <Layer title="Kdo">
        {d.runs.length ? d.runs.map((r) => (
          <div key={r.runId} className="linie-trace__item">
            <span className="pletor-dashboard__mono">{r.agent || "—"}</span> {r.startedAt} <span className="pletor-dashboard__note">od {r.fromSha7 || "—"}</span> <Status status={r.status} />
          </div>
        )) : <p className="pletor-dashboard__note">žádná evidovaná relace</p>}
      </Layer>

      <Layer title="Co">
        {d.commits.map((c) => (
          <div key={c.sha} className="linie-trace__item">
            <button type="button" className="pletor-dashboard__button pletor-dashboard__mono" onClick={() => onPickCommit(c.sha)}>{c.sha7}</button> {c.title}{" "}
            <Status status={c.status} /> <span className="pletor-dashboard__note">{c.runId ? `relace ${c.runId}` : "bez relace"}</span>
          </div>
        ))}
        {d.commits.length === 0 && <p className="pletor-dashboard__note">žádné commity</p>}
        {d.code.map((c) => (
          <div key={`${c.path}:${c.line}`} className="linie-trace__item">
            <span className="pletor-dashboard__mono">{c.path}:{c.line}</span>{c.symbol && <> · <span className="pletor-dashboard__mono">{c.symbol}</span></>}
            {c.step && <span className="pletor-dashboard__note"> · krok {c.step}</span>} <Status status={c.status} />
          </div>
        ))}
        {d.code.length === 0 && <p className="pletor-dashboard__note">v kódu značka není</p>}
      </Layer>

      <Layer title="Kde">
        <Row k="PR">{d.pr ? <a href={d.pr.url} target="_blank" rel="noreferrer">PR #{d.pr.number} ({d.pr.state}) ↗</a> : "bez PR"}</Row>
        <Row k="kontroly">{d.checks.length ? d.checks.map((c) => `${c.name}=${c.status}@${c.sha7}`).join(", ") : "neproběhly"}</Row>
        <Row k="přijetí">{d.acceptance ? `přijato ${d.acceptance.sha7}${d.acceptance.note ? ` · ${d.acceptance.note}` : ""}` : "nepřijato"}</Row>
        <Row k="začlenění">{d.merged ? `${d.merged.sha7} do ${d.merged.target} · ${d.merged.at}` : "—"}</Row>
        {preview?.url && <button type="button" className="pletor-dashboard__button" onClick={() => window.open(preview.url, "_blank", "noopener")}>Otevřít náhled</button>}
      </Layer>

      <Layer title="Mezery">
        {d.gaps.length ? <ul className="linie-trace__list">{d.gaps.map((g) => <li key={g}>{g}</li>)}</ul> : <p className="pletor-dashboard__note">žádné</p>}
      </Layer>
    </section>
  );
}
