import "../styles/pletor-dashboard-linie.css";
import "../styles/pletor-dashboard-linie-editor.css";
import { useEffect, useRef, useState } from "react";
import { useElementBox } from "@/editor/storyboard/logic/use-element-box";
import { api, type WriteMethod } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { PAD, SPAN, boardView, layoutBoard, pletorSentence } from "../logic/linie-board";
import { layoutGraph } from "../logic/linie-graph";
import { graphView, shortSha } from "../logic/linie-view";
import { failureText } from "../logic/linie-work";
import { FOLD_KEY, manualRow, readFolded, shownBoard } from "../logic/linie-fold";
import LinieBoard from "./LinieBoard";
import LinieDetail, { type LinieAct } from "./LinieDetail";
import LinieCommit from "./LinieCommit";
import LinieTrace from "./LinieTrace";
import LinieGraph from "./LinieGraph";
import LinieLegend from "./LinieLegend";
import LinieRowForm from "./LinieRowForm";
import LinieWorkForm from "./LinieWorkForm";

const POLL_MS = 10000;
const BASE = "/api/pletor/linie";
const ROWS_COLUMN = 300; // šířka sloupce hlaviček řádků (styl .pletor-dashboard__linie-board)

/**
 * Linie (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §6): editor řádků a kuliček z `GET /board` (výchozí), nebo
 * Git graf z M1 (`GET /graph`). Pod lištou jedna řádka stavu main (server, nasazení, ochrana). Editor má celou šířku;
 * detail kuličky, Cesta nebo commit se otevře vpravo jako panel. Drží sbalení (L6: ruční řádek na serveru, ostatní
 * v `localStorage`) a zaměření `?branch=`. Zápisy jdou přes `write`/`act`, které po zápisu znovu načtou stav.
 */
export default function DashboardLinie({ project, workspace }: { project: string; workspace: string }) {
  const [mode, setMode] = useState<"editor" | "git">("editor");
  const [boardRaw, setBoardRaw] = useState<unknown>(null);
  const [graphRaw, setGraphRaw] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [form, setForm] = useState<"" | "row" | "work">("");
  // Hluboký odkaz `?ticket=` (z PR, Pletora) otevře detail kuličky; `?branch=` jen zaměří editor, detail neotevře.
  const [picked, setPicked] = useState(() => new URLSearchParams(location.search).get("ticket") ?? "");
  const [focus, setFocus] = useState(() => new URLSearchParams(location.search).get("branch") ?? "");
  const [lane, setLane] = useState("");
  const [folded, setFolded] = useState(() => readFolded(globalThis.localStorage));
  const [commit, setCommit] = useState("");
  const [trace, setTrace] = useState("");
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

  useEffect(() => {
    if (!commit && !trace) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { if (trace) setTrace(""); else setCommit(""); } };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [commit, trace]);

  const plotRef = useRef<HTMLDivElement>(null);
  const box = useElementBox(plotRef, true);
  const board = boardView(boardRaw);
  const shown = shownBoard(board, folded, focus);
  // Časová osa vyplní šířku plátna; užší obrazovka dostane nejméně SPAN a posouvá se.
  const layout = layoutBoard(shown.board, Math.max(SPAN, (box?.width ?? 0) - ROWS_COLUMN - 2 * PAD));
  const view = graphView(graphRaw);
  const main = view.lanes.find((item) => item.role === "main");
  // Rodič se hledá i mezi větvemi, které jsou jen v gitu (bez řádku a kuličky), jinak by mezičlánek spadl na develop.
  const heads = [...new Set([board.mapping.main, board.mapping.develop, ...board.rows.map((row) => row.branch), ...board.balls.map((ball) => ball.branch), ...view.lanes.map((item) => item.name)].filter(Boolean))];
  // Git graf: klik na linii ji zvýrazní a otevře detail kuličky té větve.
  const pickBranch = (name: string) => { setLane(name); setPicked(board.balls.find((ball) => ball.branch === name)?.ticketId ?? ""); };
  const close = () => { setPicked(""); setLane(""); };
  const focusOn = (branch: string) => {
    setFocus(branch);
    const params = new URLSearchParams(location.search);
    if (branch) params.set("branch", branch); else params.delete("branch");
    history.replaceState(history.state, "", `${location.pathname}?${params}`);
  };
  // Ruční řádek si sbalení ukládá na server, ostatní (automatické, pevné, z gitu) v prohlížeči pro celou aplikaci.
  const fold = (id: string, collapsed: boolean) => {
    const row = board.rows.find((item) => item.id === id);
    if (row && manualRow(row)) { void write(`/rows/${encodeURIComponent(id)}`, { collapsed }, collapsed ? "Řádek sbalen." : "Řádek rozbalen.", "PATCH"); return; }
    const next = new Set(folded);
    if (collapsed) next.add(id); else next.delete(id);
    setFolded(next);
    try { localStorage.setItem(FOLD_KEY, JSON.stringify([...next])); } catch { /* bez úložiště platí sbalení jen do obnovení */ }
  };
  const panel = trace ? (
    <LinieTrace mark={trace} query={query} onClose={() => setTrace("")}
      onPickTicket={(id) => { setTrace(""); setCommit(""); setPicked(id); }} onPickCommit={(sha) => { setTrace(""); setCommit(sha); }} />
  ) : commit ? (
    <LinieCommit sha={commit} query={query} onClose={() => setCommit("")} onPickTicket={(id) => { setCommit(""); setPicked(id); }} onPickTrace={setTrace} />
  ) : picked ? (
    <LinieDetail ticketId={picked} query={query} main={board.mapping.main} onAct={act} onClose={close} onPickTrace={setTrace} />
  ) : null;
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
      <p className="pletor-dashboard__linie-status">
        <span className="pletor-dashboard__mono">main {shortSha(main?.sha ?? "") || "—"} lokál / {shortSha(main?.remote ?? "") || "—"} origin</span>
        <span className="pletor-dashboard__mono">server: {view.server.branch || "—"} @ {shortSha(view.server.sha) || "—"}{view.server.dirty ? " (necommitnuté změny)" : ""}</span>
        <span className="pletor-dashboard__mono">nasazeno: {view.deployed ? `${shortSha(view.deployed.sha)} ${view.deployed.at}` : "neevidováno"}</span>
        <span className="pletor-dashboard__tag pletor-dashboard__tag--warn">ochrana: {view.enforcement}</span>
        <button type="button" className="pletor-dashboard__button" disabled={!view.server.sha}
          onClick={() => void write("/deployed", { sha: view.server.sha }, `Nasazené zapsáno: ${shortSha(view.server.sha)}.`)}>Zapsat nasazené = HEAD serveru</button>
      </p>
      {form === "row" && <LinieRowForm onClose={() => setForm("")} onSubmit={(body) => write("/rows", body, "Řádek přidán (větev se nezaložila).")} />}
      {form === "work" && <LinieWorkForm rows={board.rows} heads={heads} onClose={() => setForm("")} onSubmit={(body) => write("/work", body, "Kulička zadána (větev založí agent).")} />}
      <p className="pletor-dashboard__note">Přidání řádku větev nezakládá a přejmenování ji nepřejmenuje. Klik na název = zaměřit, dvojklik = přejmenovat, šipka = sbalit podstrom.</p>
      {mode === "editor" && focus && (
        <p className="pletor-dashboard__linie-crumb">
          Zaměřeno: <strong>{focus}</strong> › <button type="button" className="pletor-dashboard__linie-crumb-back" onClick={() => focusOn("")}>zpět na vše ✕</button>
        </p>
      )}

      <div className={`pletor-dashboard__linie${panel ? " pletor-dashboard__linie--with-panel" : ""}`}>
        <div className="pletor-dashboard__linie-graph" ref={plotRef}>
          {mode === "editor" ? (
            <LinieBoard layout={layout} selected={picked} chips={shown.chips} onPick={setPicked} onFold={fold} onFocus={focusOn}
              onRename={(id, name) => void write(`/rows/${encodeURIComponent(id)}`, { name }, `Řádek přejmenován na ${name}.`, "PATCH")} />
          ) : (
            <LinieGraph layout={layoutGraph(view.lanes)} selected={lane} links={links} onPick={pickBranch} onPickCommit={setCommit} />
          )}
        </div>
        {panel && <aside className="pletor-dashboard__linie-panel">{panel}</aside>}
        {mode === "editor" && <LinieLegend board={board} />}
      </div>
    </>
  );
}
