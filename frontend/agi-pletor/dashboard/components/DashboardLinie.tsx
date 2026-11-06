import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { acceptanceLabel, acceptanceTone, linieView, previewLabel, roleLabel, shortSha, type LinieBranch } from "../logic/linie-view";
import LinieBranchDetail from "./LinieBranchDetail";

const POLL_MS = 10000;
const BASE = "/api/pletor/linie";
const TONE = { ok: "pletor-dashboard__tag--ok", stale: "pletor-dashboard__tag--stale", none: "pletor-dashboard__tag--warn" } as const;

/**
 * Linie (docs/navrhy/2026-11-06-velin-git-linie.md §5): main, develop a server nahoře, pod nimi větve s přijetím a náhledem.
 * Čte `GET /api/pletor/linie/` každých 10 s; každý zápis (náhled, přijetí, nasazení) hlásí větu a stav načte znovu.
 */
export default function DashboardLinie({ project }: { project: string }) {
  const [raw, setRaw] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [selected, setSelected] = useState("");
  const poll = usePolling(() => api<unknown>(`${BASE}/`).then(
    (next) => { setRaw(next); setError(""); },
    (failure: unknown) => setError(failure instanceof Error ? failure.message : "Načtení selhalo."),
  ), { intervalMs: POLL_MS });
  const act = (write: Promise<unknown>, done: string) => {
    setNote("");
    write.then(() => { setNote(done); setError(""); }, (failure: unknown) => setError(failure instanceof Error ? failure.message : "Zápis selhal."))
      .finally(() => void poll.refresh());
  };
  const view = linieView(raw);
  const branch = view.branches.find((item) => item.name === selected) ?? null;

  const previewCell = (row: LinieBranch) => {
    const p = row.preview;
    if (p?.state === "building") return <span className="pletor-dashboard__tag pletor-dashboard__tag--warn">sestavuje se…</span>;
    if (p?.state === "running") return (
      <span className="pletor-dashboard__tools">
        {p.url && <a href={p.url} target="_blank" rel="noreferrer">Otevřít náhled</a>}
        <button type="button" className="pletor-dashboard__button" onClick={() => act(api(`${BASE}/previews/${encodeURIComponent(p.slug)}`, {}, "DELETE"), `Náhled ${row.name} zastaven.`)}>Zastavit</button>
      </span>
    );
    return (
      <span className="pletor-dashboard__tools">
        {p && <span className="pletor-dashboard__tag">{previewLabel(p)}</span>}
        <button type="button" className="pletor-dashboard__button" disabled={!project}
          onClick={() => act(api(`${BASE}/previews`, { branch: row.name, project }), `Náhled ${row.name} se spouští.`)}>Spustit náhled</button>
      </span>
    );
  };

  return (
    <>
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
      {view.problem && <p className="pletor-dashboard__error">{view.problem}</p>}
      {note && <p className="pletor-dashboard__note" role="status">{note}</p>}
      <div className="pletor-dashboard__linie-cards">
        <section className="pletor-dashboard__linie-card" aria-label="main">
          <h2 className="pletor-dashboard__group-title">main</h2>
          <p className="pletor-dashboard__mono">{shortSha(view.main.sha) || "—"} lokál / {shortSha(view.main.remote) || "—"} origin</p>
          <span className="pletor-dashboard__tag pletor-dashboard__tag--warn">ochrana: {view.enforcement}</span>
        </section>
        <section className="pletor-dashboard__linie-card" aria-label="develop">
          <h2 className="pletor-dashboard__group-title">develop</h2>
          <p className="pletor-dashboard__mono">{view.develop ? shortSha(view.develop.sha) : "nezaložen"}</p>
        </section>
        <section className="pletor-dashboard__linie-card" aria-label="Server a nasazení">
          <h2 className="pletor-dashboard__group-title">Server a nasazení</h2>
          <p className="pletor-dashboard__mono">{view.server.branch || "—"} @ {shortSha(view.server.sha) || "—"}</p>
          {view.server.dirty && <span className="pletor-dashboard__tag pletor-dashboard__tag--stale">necommitnuté změny</span>}
          <p className="pletor-dashboard__mono">nasazeno: {view.deployed ? `${shortSha(view.deployed.sha)} ${view.deployed.at}` : "neevidováno"}</p>
          <button type="button" className="pletor-dashboard__button" disabled={!view.server.sha}
            onClick={() => act(api(`${BASE}/deployed`, { sha: view.server.sha }), `Nasazené zapsáno: ${shortSha(view.server.sha)}.`)}>Zapsat nasazené = HEAD serveru</button>
        </section>
      </div>
      <h2 className="pletor-dashboard__group-title">Větve</h2>
      <table className="pletor-dashboard__table">
        <thead><tr><th>Větev</th><th>Role</th><th>Rodič</th><th>HEAD</th><th>±</th><th>Přijetí</th><th>Náhled</th></tr></thead>
        <tbody>
          {view.branches.map((row) => (
            <tr key={row.name} className={row.name === selected ? "pletor-dashboard__row--selected" : undefined} onClick={() => setSelected(row.name)}>
              <td><button type="button" className="pletor-dashboard__row-pick" aria-pressed={row.name === selected}>{row.name}</button></td>
              <td>{roleLabel(row.role)}</td>
              <td>{row.parent || "—"}</td>
              <td className="pletor-dashboard__mono">{shortSha(row.sha)}</td>
              <td className="pletor-dashboard__mono">+{row.ahead} / −{row.behind}</td>
              <td><span className={`pletor-dashboard__tag ${TONE[acceptanceTone(row)]}`}>{acceptanceLabel(row)}</span></td>
              <td>{previewCell(row)}</td>
            </tr>
          ))}
          {view.branches.length === 0 && <tr><td colSpan={7} className="pletor-dashboard__empty">Žádné větve.</td></tr>}
        </tbody>
      </table>
      {branch && <LinieBranchDetail branch={branch} onAct={act} />}
    </>
  );
}
