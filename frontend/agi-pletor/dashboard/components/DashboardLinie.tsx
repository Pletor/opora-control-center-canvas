import "../styles/pletor-dashboard-linie.css";
import "../styles/pletor-dashboard-linie-editor.css";
import { useState } from "react";
import { api, type WriteMethod } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { boardView, layoutBoard, pletorSentence } from "../logic/linie-board";
import { layoutGraph } from "../logic/linie-graph";
import { graphView, shortSha } from "../logic/linie-view";
import { failureText } from "../logic/linie-work";
import LinieBoard from "./LinieBoard";
import LinieDetail, { type LinieAct } from "./LinieDetail";
import LinieGraph from "./LinieGraph";
import LinieLegend from "./LinieLegend";
import LinieRowForm from "./LinieRowForm";
import LinieWorkForm from "./LinieWorkForm";

const POLL_MS = 10000;
const BASE = "/api/pletor/linie";

/**
 * Linie (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §6): editor řádků a kuliček z `GET /board` (výchozí), nebo
 * Git graf z M1 (`GET /graph`). Klik na kuličku otevře detail; vpravo karta MAIN (server, nasazení, ochrana).
 * Drží zápisy: řádky, kuličky a akce detailu jdou přes `write`/`act`, které po zápisu znovu načtou stav.
 */
export default function DashboardLinie({ project, workspace }: { project: string; workspace: string }) {
  const [mode, setMode] = useState<"editor" | "git">("editor");
  const [boardRaw, setBoardRaw] = useState<unknown>(null);
  const [graphRaw, setGraphRaw] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [form, setForm] = useState<"" | "row" | "work">("");
  // Hluboký odkaz `?ticket=` nebo `?branch=` (z PR, Pletora) předvybere kuličku.
  const [picked, setPicked] = useState(() => new URLSearchParams(location.search).get("ticket") ?? "");
  const [hint, setHint] = useState(() => new URLSearchParams(location.search).get("branch") ?? "");
  const query = new URLSearchParams({ project, workspace }).toString();
  const fail = (failure: unknown) => setError(failureText(failure, "Načtení selhalo."));
  const poll = usePolling(() => Promise.all([
    api<unknown>(`${BASE}/board?${query}`).then((next) => { setBoardRaw(next); setError(""); }, fail),
    api<unknown>(`${BASE}/graph?${query}`).then(setGraphRaw, fail),
  ]), { intervalMs: POLL_MS, refreshKeys: [query] });

  const act: LinieAct = (path, body, done, method = "POST") => api(`${BASE}${path}?${query}`, body, method)
    .then(() => done, (failure: unknown) => failureText(failure)).finally(() => void poll.refresh());
  const write = (path: string, body: object, done: string, method: WriteMethod = "POST") => api(`${BASE}${path}?${query}`, body, method).then(
    () => { setNote(done); setError(""); void poll.refresh(); return true; },
    (failure: unknown) => { setError(failureText(failure)); return false; },
  );

  const board = boardView(boardRaw);
  const layout = layoutBoard(board);
  const view = graphView(graphRaw);
  const main = view.lanes.find((lane) => lane.role === "main");
  const selected = picked || (hint ? board.balls.find((ball) => ball.branch === hint)?.ticketId ?? "" : "");
  const pickBranch = (name: string) => { setPicked(""); setHint(name); };
  const close = () => { setPicked(""); setHint(""); };
  const links = Object.fromEntries(view.lanes.flatMap((lane) => [
    ...(lane.preview?.url ? [[`preview:${lane.name}`, lane.preview.url]] : []),
    ...(lane.pr?.url ? [[`pr:${lane.name}`, lane.pr.url]] : []),
  ]));

  return (
    <>
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
      {view.problem && <p className="pletor-dashboard__error">{view.problem}</p>}
      {note && <p className="pletor-dashboard__note" role="status">{note}</p>}
      <div className="pletor-dashboard__linie-bar">
        <span className="pletor-dashboard__tools" role="group" aria-label="Pohled">
          <button type="button" className="pletor-dashboard__button" aria-pressed={mode === "editor"} onClick={() => setMode("editor")}>Editor</button>
          <button type="button" className="pletor-dashboard__button" aria-pressed={mode === "git"} onClick={() => setMode("git")}>Git graf</button>
        </span>
        <span className="pletor-dashboard__tools">
          <button type="button" className="pletor-dashboard__button" aria-expanded={form === "row"} onClick={() => setForm(form === "row" ? "" : "row")}>+ Přidat řádek</button>
          <button type="button" className="pletor-dashboard__button" aria-expanded={form === "work"} onClick={() => setForm(form === "work" ? "" : "work")}>+ Nová kulička</button>
        </span>
        <p className="pletor-dashboard__linie-pletor"><strong>Pletor: kde pracujeme</strong> {pletorSentence(board)}</p>
      </div>
      {form === "row" && <LinieRowForm onClose={() => setForm("")} onSubmit={(body) => write("/rows", body, "Řádek přidán (větev se nezaložila).")} />}
      {form === "work" && <LinieWorkForm rows={board.rows} onClose={() => setForm("")} onSubmit={(body) => write("/work", body, "Kulička zadána (větev založí agent).")} />}
      <p className="pletor-dashboard__note">Přidání řádku větev nezakládá a přejmenování ji nepřejmenuje. Dvojklik na název = přejmenovat, šipka = sbalit.</p>

      <div className="pletor-dashboard__linie">
        <div className="pletor-dashboard__linie-graph">
          {selected ? (
            <LinieDetail ticketId={selected} query={query} main={board.mapping.main} onAct={act} onClose={close} />
          ) : mode === "editor" ? (
            <LinieBoard layout={layout} selected={selected} onPick={setPicked}
              onRename={(id, name) => void write(`/rows/${encodeURIComponent(id)}`, { name }, `Řádek přejmenován na ${name}.`, "PATCH")}
              onFold={(id, collapsed) => void write(`/rows/${encodeURIComponent(id)}`, { collapsed }, collapsed ? "Řádek sbalen." : "Řádek rozbalen.", "PATCH")} />
          ) : (
            <LinieGraph layout={layoutGraph(view.lanes)} selected={hint} links={links} onPick={pickBranch} />
          )}
        </div>
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
            onClick={() => void write("/deployed", { sha: view.server.sha }, `Nasazené zapsáno: ${shortSha(view.server.sha)}.`)}>Zapsat nasazené = HEAD serveru</button>
        </section>
        {mode === "editor" && !selected && <LinieLegend board={board} />}
        <footer className="pletor-dashboard__linie-rule">
          <strong>Každý náhled: větev + commit + vlastní testovací data.</strong>
          <span>Pravidlo: merge až po kontrolách a tvém přijetí konkrétního výsledku.</span>
        </footer>
      </div>
    </>
  );
}
