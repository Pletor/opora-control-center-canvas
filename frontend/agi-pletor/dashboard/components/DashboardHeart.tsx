import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { heartView } from "../logic/heart-view";
import { explainView } from "../logic/heart-explain";
import HeartExplain from "./HeartExplain";
import HeartCaps from "./HeartCaps";
import "../styles/pletor-dashboard-heart-explain.css";

const POLL_MS = 5000;

/** Srdce: karty stavu, fronta po prostorech a posledních 20 dávek z `GET /api/pletor/heart`, čte se každých 5 s. */
export default function DashboardHeart({ project, workspace }: { project: string; workspace: string }) {
  const [raw, setRaw] = useState<unknown>(null);
  const [error, setError] = useState("");
  usePolling(() => api<unknown>(`/api/pletor/heart?${new URLSearchParams({ project, workspace })}`).then(
    (next) => { setRaw(next); setError(""); },
    (failure: unknown) => setError(failure instanceof Error ? failure.message : "Načtení selhalo."),
  ), { intervalMs: POLL_MS, enabled: !!project && !!workspace, refreshKeys: [project, workspace] });
  const [explain, setExplain] = useState<unknown>(null);
  const [explainError, setExplainError] = useState("");
  usePolling(() => api<unknown>(`/api/pletor/heart/explain?${new URLSearchParams({ project })}`).then(
    (next) => { setExplain(next); setExplainError(""); },
    (failure: unknown) => setExplainError(failure instanceof Error ? failure.message : "Načtení průhledu selhalo."),
  ), { intervalMs: POLL_MS, enabled: !!project, refreshKeys: [project] });
  const view = heartView(raw);
  return (
    <>
      {explainError && <p className="pletor-dashboard__error" role="alert">{explainError}</p>}
      <HeartExplain view={explainView(explain)} />
      <HeartCaps />
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
      {view.problem && <p className="pletor-dashboard__error">{view.problem}</p>}
      <div className="pletor-dashboard__cards">
        {view.cards.map((card) => (
          <section key={card.id} className="pletor-dashboard__card" aria-label={card.title}>
            <h2 className="pletor-dashboard__card-title">{card.title}</h2>
            <p className="pletor-dashboard__card-value">{card.value}</p>
          </section>
        ))}
      </div>
      <h2 className="pletor-dashboard__group-title">Fronta po prostorech</h2>
      <table className="pletor-dashboard__table">
        <thead><tr><th>Prostor</th><th>Čeká</th></tr></thead>
        <tbody>
          {view.queue.map((row) => <tr key={row.workspace}><td>{row.workspace}</td><td>{row.pending}</td></tr>)}
          {view.queue.length === 0 && <tr><td colSpan={2} className="pletor-dashboard__empty">Fronta je prázdná.</td></tr>}
        </tbody>
      </table>
      <h2 className="pletor-dashboard__group-title">Posledních 20 dávek</h2>
      <table className="pletor-dashboard__table">
        <thead><tr><th>Čas</th><th>Stav</th><th>Shrnutí</th><th>Cena</th></tr></thead>
        <tbody>
          {view.batches.map((row, index) => <tr key={index}><td>{row.at}</td><td>{row.status}</td><td>{row.summary}</td><td>{row.cost}</td></tr>)}
          {view.batches.length === 0 && <tr><td colSpan={4} className="pletor-dashboard__empty">Zatím žádné dávky.</td></tr>}
        </tbody>
      </table>
    </>
  );
}
