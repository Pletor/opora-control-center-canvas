import "../styles/pletor-dashboard-linie.css";
import "../styles/pletor-dashboard-linie-editor.css";
import "../styles/pletor-dashboard-linie-panel.css";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useElementBox } from "@/editor/storyboard/logic/use-element-box";
import { api, type WriteMethod } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { boardView, clip, layoutBoard, timeRange } from "../logic/linie-board";
import { layoutGraph } from "../logic/linie-graph";
import { escTarget, keepScroll, type Mark } from "../logic/linie-keep";
import { labelWidth, placeLabels } from "../logic/linie-labels";
import { LAYERS_KEY, NAMES_KEY, readLayers, readNames, save, type LayerId } from "../logic/linie-prefs";
import { queueLines, queues, type QueueId } from "../logic/linie-queues";
import { actionRequest, actionsOf } from "../logic/linie-actions";
import { feedText, hhmm, pletorVerdict, sourceAges } from "../logic/linie-summary";
import { useLinieZoom } from "../logic/use-linie-zoom";
import { graphView, shortSha } from "../logic/linie-view";
import { failureText, type WorkDetail } from "../logic/linie-work";
import { FOLD_KEY, manualRow, readFolded, shownBoard } from "../logic/linie-fold";
import LinieBoard from "./LinieBoard";
import LinieDetail from "./LinieDetail";
import LinieCommit from "./LinieCommit";
import LinieTrace from "./LinieTrace";
import LinieGraph from "./LinieGraph";
import LinieLegend from "./LinieLegend";
import LiniePletor from "./LiniePletor";
import LinieQueues from "./LinieQueues";
import LinieRowForm from "./LinieRowForm";
import LinieStatus from "./LinieStatus";
import LinieToolbar from "./LinieToolbar";
import LinieWorkForm from "./LinieWorkForm";

const POLL_MS = 10000;
const CLOCK_MS = 15000;
const BASE = "/api/pletor/linie";

/**
 * Linie (docs/navrhy/2026-11-06-linie-rebrand.md §6): nahoře fronty odpovědnosti, lišta s měřítkem a vrstvami, pod ní
 * jediný posuvný editor (nebo Git graf) a vpravo panel Pletora s detailem. Rodič drží stav, předvolby (`localStorage`
 * pro aplikaci), výběr a jeho stálou polohu, Esc po vrstvách; zápisy jdou přes `write`/`act` a znovu načtou stav.
 */
export default function DashboardLinie({ project, workspace }: { project: string; workspace: string }) {
  const [mode, setMode] = useState<"editor" | "git">("editor");
  const [boardRaw, setBoardRaw] = useState<unknown>(null);
  const [graphRaw, setGraphRaw] = useState<unknown>(null);
  const [now, setNow] = useState(() => Date.now());
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [flash, setFlash] = useState("");
  const [acceptNote, setAcceptNote] = useState(""); // jedna poznámka k přijetí pro panel i záložku Git
  const [form, setForm] = useState<"" | "row" | "work">("");
  // Hluboký odkaz `?ticket=` (z PR, Pletora) otevře detail kuličky; `?branch=` jen zaměří editor, detail neotevře.
  const [picked, setPicked] = useState(() => new URLSearchParams(location.search).get("ticket") ?? "");
  const [focus, setFocus] = useState(() => new URLSearchParams(location.search).get("branch") ?? "");
  const [lane, setLane] = useState("");
  const [folded, setFolded] = useState(() => readFolded(globalThis.localStorage));
  const [names, setNames] = useState(() => readNames(globalThis.localStorage));
  const [layers, setLayers] = useState(() => readLayers(globalThis.localStorage));
  const [queue, setQueue] = useState<QueueId | "">("");
  const [detail, setDetail] = useState<WorkDetail | null>(null);
  const [commit, setCommit] = useState("");
  const [trace, setTrace] = useState("");
  const renaming = useRef(false);
  const query = new URLSearchParams({ project, workspace }).toString();
  const [lastSuccessAt, setLastSuccessAt] = useState<number | null>(null);
  const [boardError, setBoardError] = useState("");
  const fail = (failure: unknown) => setError(failureText(failure, "Načtení selhalo."));
  const poll = usePolling(() => Promise.all([
    api<unknown>(`${BASE}/board?${query}`).then(
      (next) => { const at = Date.now(); setBoardRaw(next); setNow(at); setLastSuccessAt(at); setBoardError(""); setError(""); },
      (failure: unknown) => { setBoardError(failureText(failure, "Načtení selhalo.")); fail(failure); },
    ),
    api<unknown>(`${BASE}/graph?${query}`).then(setGraphRaw, fail),
  ]), { intervalMs: POLL_MS, refreshKeys: [query] });
  // Hodiny tikají samy: při výpadku API stáří zdrojů i posledního čtení dál roste (jen stav `now`, sítě se nedotknou).
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), CLOCK_MS);
    return () => clearInterval(id);
  }, []);

  const act = (path: string, body: object, done: string, method: WriteMethod = "POST") => api(`${BASE}${path}?${query}`, body, method)
    .then(() => done, (failure: unknown) => failureText(failure)).finally(() => void poll.refresh());
  const write = (path: string, body: object, done: string, method: WriteMethod = "POST") => api(`${BASE}${path}?${query}`, body, method).then(
    () => { setNote(done); setError(""); void poll.refresh(); return true; },
    (failure: unknown) => { setError(failureText(failure)); return false; },
  );

  const scrollRef = useRef<HTMLDivElement>(null);
  const box = useElementBox(scrollRef, mode === "editor");
  const board = boardView(boardRaw);
  const shown = shownBoard(board, folded, focus);
  const range = timeRange(shown.board, now);
  const plotWidth = Math.max(200, (box?.width ?? 1000) - names);
  const zoom = useLinieZoom(scrollRef, names, plotWidth, range.t0, range.t1, mode === "editor");
  const layout = layoutBoard(shown.board, { k: zoom.k, now });
  const labels = placeLabels(layout.balls, picked);
  const ball = board.balls.find((item) => item.ticketId === picked);
  const laid = layout.balls.find((item) => item.ticketId === picked);
  const queueList = queues(board.balls.map((b) => ({ ticketId: b.ticketId, key: b.judgement.summary.key, openPr: b.openPr })));
  const lit = queue ? new Set(queueList.find((item) => item.id === queue)?.ids) : null;
  // Kuličky, které výběr vytlačil do shluku „+N“ u sebe, vypíše detail.
  const cluster = laid ? labels.clusters.filter((c) => c.rowId === laid.rowId && Math.abs(c.x - laid.x) <= labelWidth(laid)).flatMap((c) => c.ids)
    .map((id) => ({ ticketId: id, title: board.balls.find((b) => b.ticketId === id)?.title ?? id })) : [];

  // OP-159D4C.2: stálá poloha výběru – přepnutí vrstvy, sbalení i nová data dorovná posunem o Δy vybrané kuličky.
  const mark = useRef<Mark>(null);
  useLayoutEffect(() => {
    const el = scrollRef.current;
    const next = laid ? { id: laid.ticketId, y: laid.y } : null;
    if (el) { const top = keepScroll(mark.current, next, el.scrollTop); if (top !== el.scrollTop) el.scrollTop = top; }
    mark.current = next;
  });

  const close = () => { setPicked(""); setLane(""); };
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      const target = escTarget({ renaming: renaming.current, trace: !!trace, commit: !!commit, detail: !!picked });
      if (!target) return; // nic otevřeného: Esc patří Velínu
      event.preventDefault();
      event.stopPropagation();
      if (target === "trace") setTrace(""); else if (target === "commit") setCommit(""); else if (target === "detail") close();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [trace, commit, picked]);

  const view = graphView(graphRaw);
  // Rodič se hledá i mezi větvemi, které jsou jen v gitu (bez řádku a kuličky), jinak by mezičlánek spadl na develop.
  const heads = [...new Set([board.mapping.main, board.mapping.develop, ...board.rows.map((row) => row.branch), ...board.balls.map((b) => b.branch), ...view.lanes.map((item) => item.name)].filter(Boolean))];
  const pick = (id: string) => { if (id !== picked) setAcceptNote(""); setPicked(id); setFlash(""); };
  const pickBranch = (name: string) => { setLane(name); pick(board.balls.find((b) => b.branch === name)?.ticketId ?? ""); };
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
    save(FOLD_KEY, [...next]);
  };
  const layer = (id: LayerId, on: boolean) => { const next = { ...layers, [id]: on }; setLayers(next); save(LAYERS_KEY, next); };
  const width = (value: number) => { setNames(value); save(NAMES_KEY, String(value)); };
  // Jedna cesta pro akce: seznam z allowed/blocked nad shodnou revizí boardu a detailu, provedení přes actionRequest.
  const actions = ball ? actionsOf(ball.judgement, picked, ball.headSha7, detail) : [];
  const runAction = (id: string) => {
    const request = detail && actions.find((a) => a.id === id)?.enabled ? actionRequest(id, picked, detail, acceptNote.trim()) : null;
    if (!request) return;
    setFlash("");
    if (id === "accept") setAcceptNote("");
    void act(request.path, request.body, request.done, request.method).then(setFlash);
  };

  const panel = trace ? (
    <LinieTrace mark={trace} query={query} onClose={() => setTrace("")}
      onPickTicket={(id) => { setTrace(""); setCommit(""); pick(id); }} onPickCommit={(sha) => { setTrace(""); setCommit(sha); }} />
  ) : commit ? (
    <LinieCommit sha={commit} query={query} onClose={() => setCommit("")} onPickTicket={(id) => { setCommit(""); pick(id); }} onPickTrace={setTrace} />
  ) : picked ? (
    <LinieDetail ticketId={picked} query={query} judgement={ball?.judgement ?? null} cluster={cluster} revision={lastSuccessAt}
      actions={actions} note={acceptNote} onNote={setAcceptNote} flash={flash} onAct={runAction} onClose={close} onPickTrace={setTrace} onPick={pick} onLoad={setDetail} />
  ) : null;
  const editor = mode === "editor";
  const links = Object.fromEntries(view.lanes.flatMap((item) => [
    ...(item.preview?.url ? [[`preview:${item.name}`, item.preview.url]] : []),
    ...(item.pr?.url ? [[`pr:${item.name}`, item.pr.url]] : []),
  ]));

  return (
    <div className="pletor-dashboard__linie-root">
      {editor && <LinieQueues queues={queueList} active={queue} onPick={setQueue} />}
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
      {view.problem && <p className="pletor-dashboard__error">{view.problem}</p>}
      {note && <p className="pletor-dashboard__note" role="status">{note}</p>}
      <LinieToolbar mode={mode} onMode={setMode} layers={layers} onLayer={layer} form={form} onForm={setForm}
        sources={{ commits: board.balls.some((b) => b.judgement.evidence.some((e) => e.kind === "commit")), plans: true, tags: false, worktree: false }}
        zoom={{ ...zoom, now: () => zoom.now(now) }} />
      <LinieStatus view={view} onDeployed={(sha) => void write("/deployed", { sha }, `Nasazené zapsáno: ${shortSha(sha)}.`)} />
      {form === "row" && <LinieRowForm onClose={() => setForm("")} onSubmit={(body) => write("/rows", body, "Řádek přidán (větev se nezaložila).")} />}
      {form === "work" && <LinieWorkForm rows={board.rows} heads={heads} onClose={() => setForm("")} onSubmit={(body) => write("/work", body, "Kulička zadána (větev založí agent).")} />}
      {editor && focus && (
        <p className="pletor-dashboard__linie-crumb">
          Zaměřeno: <strong>{focus}</strong> › <button type="button" className="pletor-dashboard__linie-crumb-back" onClick={() => focusOn("")}>zpět na vše ✕</button>
        </p>
      )}
      <div className={`pletor-dashboard__linie${editor || panel ? " pletor-dashboard__linie--with-panel" : ""}`}>
        {editor ? (
          <LinieBoard scrollRef={scrollRef} names={names} layout={layout} selected={picked} labels={labels} lit={lit} layers={layers} chips={shown.chips}
            onPick={pick} onFold={fold} onFocus={focusOn} onNames={width} onRenaming={(on) => { renaming.current = on; }}
            onRename={(id, name) => void write(`/rows/${encodeURIComponent(id)}`, { name }, `Řádek přejmenován na ${name}.`, "PATCH")} />
        ) : (
          <div className="pletor-dashboard__linie-graph">
            <LinieGraph layout={layoutGraph(view.lanes)} selected={lane} links={links} onPick={pickBranch} onPickCommit={setCommit} />
          </div>
        )}
        {(editor || panel) && (
          <aside className={`pletor-dashboard__linie-panel${panel ? "" : " pletor-dashboard__linie-panel--idle"}`}>
            {editor && (
              <LiniePletor lines={ball ? pletorVerdict(ball.mark || clip(ball.title), ball.judgement, board.snapshot, now) : queueLines(queueList, board.balls.length)}
                next={ball ? ball.judgement.summary.next || (detail?.ticketId === picked ? detail.next : "") : ""} builtAt={board.snapshot ? hhmm(board.snapshot.builtAt) : ""} ages={sourceAges(board.snapshot, now)}
                feed={feedText(lastSuccessAt, boardError, now)} actions={actions} note={acceptNote} onNote={setAcceptNote} flash={flash} onAct={runAction} />
            )}
            {panel}
          </aside>
        )}
      </div>
      {editor && <LinieLegend board={board} />}
    </div>
  );
}
