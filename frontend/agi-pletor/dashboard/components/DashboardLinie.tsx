import "../styles/pletor-dashboard-linie.css";
import "../styles/pletor-dashboard-linie-editor.css";
import "../styles/pletor-dashboard-linie-panel.css";
import "../styles/pletor-dashboard-linie-marks.css";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useElementBox } from "@/editor/storyboard/logic/use-element-box";
import { api, type WriteMethod } from "@/shared/types/logic/types";
import { layoutBoard, timeRange } from "../logic/linie-board";
import { layoutGraph } from "../logic/linie-graph";
import { escTarget, keepScroll, type Mark } from "../logic/linie-keep";
import { labelWidth, placeLabels } from "../logic/linie-labels";
import { laneRows } from "../logic/linie-marks";
import { FULL_KEY, LAYERS_KEY, NAMES_KEY, readFull, readLayers, readNames, save, type LayerId } from "../logic/linie-prefs";
import { queueLines, queues, type QueueId } from "../logic/linie-queues";
import { humanRequest, idleText, refusalText, type HumanRow } from "../logic/linie-human-queue";
import { actionRequest, actionsOf } from "../logic/linie-actions";
import { useLinieZoom } from "../logic/use-linie-zoom";
import { BASE, useLinieFeed, type Group } from "../logic/use-linie-feed";
import { shortSha } from "../logic/linie-view";
import { failureText, type WorkDetail } from "../logic/linie-work";
import { FOLD_KEY, manualRow, readFolded, shownBoard } from "../logic/linie-fold";
import LinieBoard from "./LinieBoard";
import LinieFullHead from "./LinieFullHead";
import LinieGraph from "./LinieGraph";
import LinieJournal from "./LinieJournal";
import LinieLegend from "./LinieLegend";
import LinieHumanQueue from "./LinieHumanQueue";
import LiniePanel from "./LiniePanel";
import LinieQueues from "./LinieQueues";
import LinieRowForm from "./LinieRowForm";
import LinieStatus from "./LinieStatus";
import LinieToolbar from "./LinieToolbar";
import LinieWorkForm from "./LinieWorkForm";

/**
 * Linie (docs/navrhy/2026-11-06-linie-rebrand.md §6, UI podle prototypu Linie v3): nahoře fronty odpovědnosti, lišta
 * s pohledem podle větví | podle plánu, měřítkem, vrstvami a „Sledovat živě“, pod ní jediný posuvný editor (nebo Git
 * graf), vpravo panel Pletora s detailem, dole sbalený deník. Data dává `useLinieFeed`; rodič drží výběr, předvolby
 * (`localStorage` pro aplikaci), stálou polohu výběru a Esc po vrstvách; zápisy jdou přes `write`/`act`.
 */
export default function DashboardLinie({ project, workspace }: { project: string; workspace: string }) {
  const [mode, setMode] = useState<"editor" | "git">("editor");
  const [group, setGroup] = useState<Group>("branch");
  const [follow, setFollow] = useState(false);
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
  const [full, setFull] = useState(() => readFull(globalThis.localStorage));
  const [queue, setQueue] = useState<QueueId | "">("");
  const [detail, setDetail] = useState<WorkDetail | null>(null);
  const [commit, setCommit] = useState("");
  const [trace, setTrace] = useState("");
  const [said, setSaid] = useState<Record<string, string>>({}); // odpověď služby na akci řádku „Čeká na tebe“
  const renaming = useRef(false);
  const feed = useLinieFeed(project, workspace, group);
  const { query, board, view, now, lastSuccessAt } = feed;

  const act = (path: string, body: object, done: string, method: WriteMethod = "POST") => api(`${BASE}${path}?${query}`, body, method)
    .then(() => done, (failure: unknown) => failureText(failure)).finally(() => void feed.refresh());
  const write = (path: string, body: object, done: string, method: WriteMethod = "POST") => api(`${BASE}${path}?${query}`, body, method).then(
    () => { setNote(done); feed.setError(""); void feed.refresh(); return true; },
    (failure: unknown) => { feed.setError(failureText(failure)); return false; },
  );

  const scrollRef = useRef<HTMLDivElement>(null);
  const box = useElementBox(scrollRef, mode === "editor");
  const shown = shownBoard(board, folded, focus);
  const range = timeRange(shown.board, now);
  const plotWidth = Math.max(200, (box?.width ?? 1000) - names);
  const zoom = useLinieZoom(scrollRef, names, plotWidth, range.t0, range.t1, mode === "editor");
  const ball = board.balls.find((item) => item.ticketId === picked);
  // Pruhy worktree: vrstva zapnutá = všechny řádky s vazbou, jinak jen řádek vybrané kuličky.
  const laneSet = layers.worktree ? new Set(laneRows(shown.board).keys()) : new Set(ball ? [ball.rowId] : []);
  const layout = layoutBoard(shown.board, { k: zoom.k, now, lanes: laneSet });
  const labels = placeLabels(layout.balls, picked, laneSet);
  const laid = layout.balls.find((item) => item.ticketId === picked);
  const queueList = queues(board.balls, board.queues, feed.requests ? feed.requests.filter((r) => r.open).length : null);
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
  // Sledovat živě: s každým úspěšným čtením se plátno posune za „teď“; hodiny tikají i při výpadku, posun jen při datech.
  const jump = useRef(zoom.now);
  jump.current = zoom.now;
  useEffect(() => { if (follow && lastSuccessAt) jump.current(lastSuccessAt); }, [follow, lastSuccessAt]);

  const close = () => { setPicked(""); setLane(""); };
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      // OP-F1B343.1: celá obrazovka je poslední vrstva před Velínem, takže Esc nejdřív zavře detail a teprve pak vrací.
      const target = escTarget({ renaming: renaming.current, trace: !!trace, commit: !!commit, detail: !!picked, full });
      if (!target) return; // nic otevřeného: Esc patří Velínu
      event.preventDefault();
      event.stopPropagation();
      if (target === "trace") setTrace(""); else if (target === "commit") setCommit(""); else if (target === "detail") close(); else if (target === "full") fullscreen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [trace, commit, picked, full]);

  // Rodič se hledá i mezi větvemi, které jsou jen v gitu (bez řádku a kuličky), jinak by mezičlánek spadl na develop.
  const heads = [...new Set([board.mapping.main, board.mapping.develop, ...feed.branchBoard.rows.map((row) => row.branch), ...board.balls.map((b) => b.branch), ...view.lanes.map((item) => item.name)].filter(Boolean))];
  const pick = (id: string) => { if (id !== picked) setAcceptNote(""); setPicked(id); setFlash(""); };
  const pickBranch = (name: string) => { setLane(name); pick(board.balls.find((b) => b.branch === name)?.ticketId ?? ""); };
  const focusOn = (branch: string) => {
    setFocus(branch);
    const params = new URLSearchParams(location.search);
    if (branch) params.set("branch", branch); else params.delete("branch");
    history.replaceState(history.state, "", `${location.pathname}?${params}`);
  };
  // Ruční řádek si sbalení ukládá na server, ostatní (automatické, pevné, z gitu, plánové) v prohlížeči pro celou aplikaci.
  const fold = (id: string, collapsed: boolean) => {
    const row = board.rows.find((item) => item.id === id);
    if (row && manualRow(row) && group === "branch") { void write(`/rows/${encodeURIComponent(id)}`, { collapsed }, collapsed ? "Řádek sbalen." : "Řádek rozbalen.", "PATCH"); return; }
    const next = new Set(folded);
    if (collapsed) next.add(id); else next.delete(id);
    setFolded(next);
    save(FOLD_KEY, [...next]);
  };
  const layer = (id: LayerId, on: boolean) => { const next = { ...layers, [id]: on }; setLayers(next); save(LAYERS_KEY, next); };
  const width = (value: number) => { setNames(value); save(NAMES_KEY, String(value)); };
  function fullscreen(on: boolean) { setFull(on); save(FULL_KEY, String(on)); }
  // Jedna cesta pro akce: seznam z allowed/blocked nad shodnou revizí boardu a detailu, provedení přes actionRequest.
  const actions = ball ? actionsOf(ball.judgement, picked, ball.headSha7, detail) : [];
  const runAction = (id: string) => {
    const request = detail && actions.find((a) => a.id === id)?.enabled ? actionRequest(id, picked, detail, acceptNote.trim()) : null;
    if (!request) return;
    setFlash("");
    if (id === "accept") setAcceptNote("");
    void act(request.path, request.body, request.done, request.method).then(setFlash);
  };
  // „Čeká na tebe“: jedna akce řádku, nové op na každé kliknutí; odmítnutí se vrací větou s jedinou opravou.
  const decide = (row: HumanRow) => { const r = humanRequest(row, crypto.randomUUID()); return r ? api(`${BASE}${r.path}?${query}`, r.body, r.method)
    .then(() => r.done, refusalText).then((text) => setSaid((old) => ({ ...old, [row.ticketId]: text }))).finally(() => void feed.refresh()) : Promise.resolve(); };

  const editor = mode === "editor";
  const links = Object.fromEntries(view.lanes.flatMap((item) => [
    ...(item.preview?.url ? [[`preview:${item.name}`, item.preview.url]] : []),
    ...(item.pr?.url ? [[`pr:${item.name}`, item.pr.url]] : []),
  ]));
  const sources = {
    commits: board.balls.some((b) => b.commits.length || b.judgement.evidence.some((e) => e.kind === "commit")),
    worktree: board.worktrees.some((w) => w.binding), plans: board.balls.some((b) => b.judgement.plan), prs: board.balls.some((b) => b.pr), tags: board.tags.length > 0 || board.deploy.length > 0,
  };
  const marks = Object.fromEntries(board.balls.map((b) => [b.ticketId, b.mark]));
  const activeQueue = queueList.find((item) => item.id === queue);

  return (
    <div className={`pletor-dashboard__linie-root${full ? " pletor-dashboard__linie-root--full" : ""}`}>
      {full && <LinieFullHead say={queueLines(queueList, board.balls.length).slice(0, -1).join(" ")} />}
      {editor && <LinieQueues queues={queueList} active={queue} onPick={setQueue} />}
      {feed.error && <p className="pletor-dashboard__error" role="alert">{feed.error}</p>}
      {view.problem && <p className="pletor-dashboard__error">{view.problem}</p>}
      {note && <p className="pletor-dashboard__note" role="status">{note}</p>}
      <LinieToolbar mode={mode} onMode={setMode} group={group} onGroup={setGroup} layers={layers} onLayer={layer} form={form} onForm={setForm} sources={sources}
        follow={follow} onFollow={setFollow} zoom={{ ...zoom, now: () => zoom.now(now) }} full={full} onFull={fullscreen} />
      <LinieStatus view={view} onDeployed={(sha) => void write("/deployed", { sha }, `Nasazené zapsáno: ${shortSha(sha)}.`)} />
      {form === "row" && <LinieRowForm onClose={() => setForm("")} onSubmit={(body) => write("/rows", body, "Řádek přidán (větev se nezaložila).")} />}
      {form === "work" && <LinieWorkForm rows={feed.branchBoard.rows} heads={heads} onClose={() => setForm("")} onSubmit={(body) => write("/work", body, "Kulička zadána (větev založí agent).")} />}
      {editor && (focus || activeQueue) && (
        <p className="pletor-dashboard__linie-crumb">
          {focus && <>Zaměřeno: <strong>{focus}</strong> › <button type="button" className="pletor-dashboard__linie-crumb-back" onClick={() => focusOn("")}>zpět na vše ✕</button></>}
          {activeQueue && <>Fronta: <strong>{activeQueue.label}</strong> › <button type="button" className="pletor-dashboard__linie-crumb-back" onClick={() => setQueue("")}>zrušit ✕</button></>}
        </p>
      )}
      {editor && queue === "clovek" && <LinieHumanQueue rows={feed.human} idle={idleText(board.balls, board.worktrees)} said={said} onAct={decide} />}
      <div className={`pletor-dashboard__linie${editor || trace || commit || picked ? " pletor-dashboard__linie--with-panel" : ""}`}>
        {editor ? (
          <LinieBoard scrollRef={scrollRef} names={names} layout={layout} selected={picked} labels={labels} lit={lit} layers={layers} chips={shown.chips}
            corner={group === "plan" ? "plátno 2 › plátno 3" : "řádek · větev · cíl"}
            onPick={pick} onFold={fold} onFocus={focusOn} onNames={width} onRenaming={(on) => { renaming.current = on; }}
            onRename={(id, name) => void write(`/rows/${encodeURIComponent(id)}`, { name }, `Řádek přejmenován na ${name}.`, "PATCH")} />
        ) : (
          <div className="pletor-dashboard__linie-graph">
            <LinieGraph layout={layoutGraph(view.lanes)} selected={lane} links={links} onPick={pickBranch} onPickCommit={setCommit} />
          </div>
        )}
        <LiniePanel editor={editor} board={board} ball={ball} picked={picked} detail={detail} query={query} queueList={queueList} now={now} lastSuccessAt={lastSuccessAt}
          boardError={feed.boardError} requests={feed.requests} actions={actions} acceptNote={acceptNote} onAcceptNote={setAcceptNote} flash={flash} onAct={runAction} onAsk={feed.ask}
          trace={trace} onTrace={setTrace} commit={commit} onCommit={setCommit} cluster={cluster} onPick={pick} onClose={close} onDetail={setDetail} />
      </div>
      {editor && <LinieJournal journal={feed.journal} marks={marks} onPick={pick} />}
      {editor && <LinieLegend board={board} />}
    </div>
  );
}
