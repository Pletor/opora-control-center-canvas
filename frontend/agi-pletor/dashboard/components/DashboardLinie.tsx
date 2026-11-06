import "../styles/pletor-dashboard-linie.css";
import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { layoutGraph } from "../logic/linie-graph";
import { graphView, shortSha, workLane } from "../logic/linie-view";
import LinieGraph from "./LinieGraph";
import LiniePreview from "./LiniePreview";
import LinieWorkCard from "./LinieWorkCard";

const POLL_MS = 10000;
const BASE = "/api/pletor/linie";

/**
 * Linie (docs/navrhy/2026-11-06-velin-git-linie.md §5) podle obrázku workflow: vlevo graf větví, vpravo karty
 * PRACOVNÍ VĚTEV / DEVELOP / MAIN, dole pravidlo. Čte `GET /graph` každých 10 s; každý zápis hlásí větu a stav načte znovu.
 */
export default function DashboardLinie({ project }: { project: string }) {
  const [raw, setRaw] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  // Hluboký odkaz `?branch=` (z PR, Pletora) předvybere větev.
  const [picked, setPicked] = useState(() => new URLSearchParams(location.search).get("branch") ?? "");
  const poll = usePolling(() => api<unknown>(`${BASE}/graph`).then(
    (next) => { setRaw(next); setError(""); },
    (failure: unknown) => setError(failure instanceof Error ? failure.message : "Načtení selhalo."),
  ), { intervalMs: POLL_MS });
  const act = (write: Promise<unknown>, done: string) => {
    setNote("");
    write.then(() => { setNote(done); setError(""); }, (failure: unknown) => setError(failure instanceof Error ? failure.message : "Zápis selhal."))
      .finally(() => void poll.refresh());
  };

  const view = graphView(raw);
  const layout = layoutGraph(view.lanes);
  const work = workLane(view.lanes, picked, view.active);
  const main = view.lanes.find((lane) => lane.role === "main");
  const develop = view.lanes.find((lane) => lane.role === "develop");
  const links = Object.fromEntries(view.lanes.flatMap((lane) => [
    ...(lane.preview?.url ? [[`preview:${lane.name}`, lane.preview.url]] : []),
    ...(lane.pr?.url ? [[`pr:${lane.name}`, lane.pr.url]] : []),
  ]));

  return (
    <>
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
      {view.problem && <p className="pletor-dashboard__error">{view.problem}</p>}
      {note && <p className="pletor-dashboard__note" role="status">{note}</p>}
      <div className="pletor-dashboard__linie">
        <div className="pletor-dashboard__linie-graph">
          <LinieGraph layout={layout} selected={work?.name ?? ""} links={links} onPick={setPicked} />
        </div>
        <div className="pletor-dashboard__linie-side">
          <LinieWorkCard lane={work} project={project} onAct={act} />
          <section className="pletor-dashboard__linie-card pletor-dashboard__linie-card--develop" aria-label="Develop">
            <h2 className="pletor-dashboard__linie-card-title">Develop</h2>
            <ul className="pletor-dashboard__linie-points">
              <li>Spojení přijatých změn.</li>
              <li>Ověření souhry celé aplikace.</li>
              <li>Při chybě oprava v nové větvi; main se nemění.</li>
            </ul>
            {develop ? (
              <>
                <p className="pletor-dashboard__mono">{shortSha(develop.sha)}</p>
                <LiniePreview lane={develop} project={project} onAct={act} />
              </>
            ) : <p className="pletor-dashboard__note">develop není založen.</p>}
          </section>
          <section className="pletor-dashboard__linie-card pletor-dashboard__linie-card--main" aria-label="Main">
            <h2 className="pletor-dashboard__linie-card-title">Main</h2>
            <ul className="pletor-dashboard__linie-points">
              <li>Poslední přijatý stabilní stav.</li>
              <li>Žádné přímé experimentální zápisy.</li>
              <li>Nasazení je samostatný krok.</li>
            </ul>
            <p className="pletor-dashboard__mono">{shortSha(main?.sha ?? "") || "—"} lokál / {shortSha(main?.remote ?? "") || "—"} origin</p>
            <span className="pletor-dashboard__tag pletor-dashboard__tag--warn">ochrana: {view.enforcement}</span>
            <p className="pletor-dashboard__mono">server: {view.server.branch || "—"} @ {shortSha(view.server.sha) || "—"}{view.server.dirty ? " (necommitnuté změny)" : ""}</p>
            <p className="pletor-dashboard__mono">nasazeno: {view.deployed ? `${shortSha(view.deployed.sha)} ${view.deployed.at}` : "neevidováno"}</p>
            <button type="button" className="pletor-dashboard__button" disabled={!view.server.sha}
              onClick={() => act(api(`${BASE}/deployed`, { sha: view.server.sha }), `Nasazené zapsáno: ${shortSha(view.server.sha)}.`)}>Zapsat nasazené = HEAD serveru</button>
          </section>
        </div>
        <footer className="pletor-dashboard__linie-rule">
          <strong>Každý náhled: větev + commit + vlastní testovací data.</strong>
          <span>Pravidlo: merge až po kontrolách a tvém přijetí konkrétního výsledku.</span>
        </footer>
      </div>
    </>
  );
}
