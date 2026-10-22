// Spodní pás Editoru (návrh „Opora Editor — lean“, rámy 1a a 5a/5b): sbalený ukazuje poslední děj jedním
// řádkem, rozbalená „Časová osa“ kreslí dráhy karet vrstvy v pořadí `topoIndex`. Data: jeden sdílený klient
// toku událostí (SSE s obnovou od kurzoru, záložně polling) + snímek agent-state pro jména a stav karet.
import { useMemo, useState } from "react";
import type { Graph } from "@/shared/types/logic/types";
import { useAgentState } from "@/hub/oporahub-agent-state/logic/use-agent-state";
import { openCardDrawer } from "@/hub/oporahub-card-drawer/logic/open";
import { cardFace } from "@/editor/canvas/card-face/logic/card-face";
import { TONE_GLYPH, toneOf } from "@/editor/canvas/card-face/logic/face-tones";
import { useNow } from "@/editor/canvas/card-face/logic/use-now";
import { useLiveEvents } from "../logic/use-live-events";
import { eventText, lanes, markOf, type LaneCard } from "../logic/live-model";
import LiveLanes from "./LiveLanes";
import "../styles/live-strip.css";

const WINDOWS = [{ label: "5 min", ms: 5 * 60_000 }, { label: "15 min", ms: 15 * 60_000 }, { label: "1 h", ms: 60 * 60_000 }];
const KEY = "opora:live-strip:open";
const readOpen = () => { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } };
const time = (at: string) => new Date(at).toLocaleTimeString("cs-CZ");

export default function LiveStrip({ project, workspace, graph, parent }: { project: string; workspace: string; graph: Graph; parent: string | null }) {
  const agent = useAgentState(project, workspace);
  const live = useLiveEvents(project, workspace, agent.refresh);
  const [open, setOpen] = useState(readOpen);
  const [windowMs, setWindowMs] = useState(WINDOWS[1].ms);
  const now = useNow(5000, open);
  const names = useMemo(() => new Map(graph.nodes.map((node) => [node.id, node.name])), [graph.nodes]);
  const nameOf = (id: string | null) => (id && names.get(id)) || id || "projekt";
  const cards = useMemo((): LaneCard[] => {
    const known = new Map((agent.state?.cards ?? []).map((card) => [card.nodeId, card]));
    return graph.nodes.filter((node) => node.parentId === parent && (node.kind === "node" || node.kind === "sector"))
      .map((node) => ({ node, card: known.get(node.id) }))
      .sort((a, b) => (a.card?.topoIndex ?? 1e9) - (b.card?.topoIndex ?? 1e9) || a.node.name.localeCompare(b.node.name))
      .map(({ node, card }) => ({ nodeId: node.id, name: node.name, leased: !!card?.lease,
        glyph: TONE_GLYPH[toneOf(cardFace({ nodeId: node.id, card, sector: node.kind === "sector", decisions: agent.state?.decisions ?? [], nameOf: String }))] }));
  }, [graph.nodes, parent, agent.state]);
  const toggle = () => setOpen((value) => { try { localStorage.setItem(KEY, value ? "0" : "1"); } catch { /* jen pohodlí */ } return !value; });
  const recent = [...live.events].reverse();
  const layerName = parent ? names.get(parent) ?? parent : "projekt";
  const transport = live.transport === "sse" ? `SSE · Last-Event-ID ${live.cursor}` : live.transport === "poll" ? `polling · od ${live.cursor}` : "připojuji…";
  return (
    <section className={"live-strip" + (open ? " live-strip--open" : "")} aria-label="Živý proces" data-oh-view="live-strip"
      data-oh-transport={live.transport} data-oh-cursor={live.cursor}>
      {!open && <div className="live-strip__bar">
        <span className={"live-strip__dot live-strip__dot--" + live.transport} aria-hidden="true" />
        <b className="live-strip__label">Děj</b>
        <div className="live-strip__ticker">
          {!recent.length && <span className="live-strip__muted">{live.error || "Zatím žádné události."}</span>}
          {recent.slice(0, 4).map((event) => <button key={event.id} type="button" className="live-strip__tick"
            onClick={() => event.nodeId && openCardDrawer(event.nodeId, markOf(event.kind).tab)} data-oh-event={event.id} data-oh-kind={event.kind}>
            <time>{time(event.at)}</time> <span className={"live-strip__glyph live-strip__glyph--" + markOf(event.kind).tone}>{markOf(event.kind).glyph}</span> {nameOf(event.nodeId)} · {eventText(event)}
          </button>)}
        </div>
        <button type="button" className="live-strip__toggle" aria-expanded={false} onClick={toggle}>Časová osa ▴</button>
      </div>}
      {open && <>
        <header className="live-strip__head">
          <b>Živý proces</b>
          <span className="live-strip__context">{parent ? "sektor" : "vrstva"} {layerName} · {cards.length} karet · řádky podle topoIndex</span>
          <span className="live-strip__grow" />
          <span className="live-strip__transport"><span className={"live-strip__dot live-strip__dot--" + live.transport} aria-hidden="true" /> {transport}</span>
          <div className="live-strip__windows" role="group" aria-label="Okno časové osy">
            {WINDOWS.map((item) => <button key={item.ms} type="button" aria-pressed={windowMs === item.ms} onClick={() => setWindowMs(item.ms)}>{item.label}</button>)}
          </div>
          <button type="button" className="live-strip__toggle" aria-expanded onClick={toggle} aria-label="Sbalit časovou osu">▾</button>
        </header>
        <LiveLanes lanes={lanes(live.events, cards, windowMs, now)} windowMs={windowMs} now={now}
          recent={recent.slice(0, 30).map((event) => ({ event, name: nameOf(event.nodeId), text: eventText(event), mark: markOf(event.kind) }))} />
      </>}
    </section>
  );
}
