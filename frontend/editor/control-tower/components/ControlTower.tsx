// Velín (návrh „Opora Editor — lean“, rámy 4a/4b): projekt → vrstva → sektor → karta nad jediným snímkem
// agent-state, vpravo rozhodnutí pro člověka a další akce, dole „Teď běží“ s odpočtem pronájmu. Nic tu nezapisuje:
// klik na kartu, rozhodnutí nebo akci otevře detail karty (`openCardDrawer`), zápisy dál ověřuje původní API.
import { useMemo, useState } from "react";
import type { Graph } from "@/shared/types/logic/types";
import { useAgentState } from "@/hub/oporahub-agent-state/logic/use-agent-state";
import JsonMirror from "@/hub/oporahub-mirror/components/JsonMirror";
import { mapGapsForAgents, velinModel, type VelinFilter } from "../logic/velin-model";
import VelinLayer, { VelinCounts } from "./VelinLayer";
import VelinSide from "./VelinSide";
import VelinRunning from "./VelinRunning";
import VelinGuards from "./VelinGuards";
import { guardFindings, guardLine } from "../logic/velin-guards";
import { useGuardStatus } from "../logic/use-guard-status";
import VelinTrend from "./VelinTrend";
import { useGuardTrend } from "../logic/use-guard-trend";
import VelinWorktrees from "./VelinWorktrees";
import { velinWorktrees } from "../logic/velin-worktrees";
import { useMapWorktrees } from "@/project/architecture-editor/logic/use-map-worktrees";
import "../styles/velin.css";

const FILTERS: { id: VelinFilter; label: string }[] = [
  { id: "all", label: "Vše" }, { id: "human", label: "Na tebe" }, { id: "problems", label: "Problémy" }, { id: "running", label: "Běží" },
];

type Props = { project: string; workspace: string; graph: Graph; projectName?: string; onOpen: (nodeId: string) => void; onOpenMap?: () => void;
  /** Schopnost projektu (od App): práce ve worktree se čte jen u projektů, které worktree mají. */
  worktreeLive?: boolean };

export default function ControlTower({ project, workspace, graph, projectName, onOpen, onOpenMap, worktreeLive = false }: Props) {
  const agent = useAgentState(project, workspace);
  const [filter, setFilter] = useState<VelinFilter>("all");
  const view = useMemo(() => agent.state ? velinModel(graph, agent.state, filter) : null, [graph, agent.state, filter]);
  const all = useMemo(() => agent.state ? velinModel(graph, agent.state) : null, [graph, agent.state]);
  const holes = agent.state ? mapGapsForAgents(agent.state) : null;
  const guardStatus = useGuardStatus(project);
  const trend = useGuardTrend(project);
  const overlay = useMapWorktrees(project, worktreeLive);
  const worktrees = useMemo(() => {
    const names = new Map(graph.nodes.map(node => [node.id, node.name]));
    const sources = new Map(graph.edges.map(edge => [edge.id, edge.source]));
    return velinWorktrees(overlay, finding => finding.nodeId ?? (finding.edgeId ? sources.get(finding.edgeId) : undefined) ?? null, id => names.get(id) ?? id);
  }, [graph, overlay]);
  const alerts = useMemo(() => {
    if (!agent.state) return null;
    const names = new Map(graph.nodes.map(node => [node.id, node.name]));
    return guardFindings(agent.state, id => names.get(id) ?? id);
  }, [graph, agent.state]);
  const count = (id: VelinFilter) => !all ? 0 : id === "human" ? all.total.human : id === "problems" ? all.total.bad + all.total.blocked
    : id === "running" ? all.total.run : all.cards;
  return (
    <section className="velin" aria-label="Velín" data-oh-view="velin" data-oh-etag={agent.etag} data-oh-generated-at={agent.state?.generatedAt ?? ""}>
      <JsonMirror id="oh-velin" value={view ? { total: view.total, layers: view.layers.map(layer => ({ id: layer.id, counts: layer.counts,
        sectors: layer.sectors.map(sector => ({ id: sector.id, cards: sector.pills.map(pill => ({ nodeId: pill.nodeId, tone: pill.tone })) })) })) } : null} />
      <header className="velin__bar">
        <div className="velin__filters" role="tablist" aria-label="Filtr Velínu">
          {FILTERS.map(item => <button key={item.id} type="button" role="tab" aria-selected={filter === item.id}
            className={"velin__filter" + (filter === item.id ? " velin__filter--active" : "") + (item.id === "human" && count("human") > 0 ? " velin__filter--waiting" : "")} onClick={() => setFilter(item.id)}>
            {item.label}{item.id !== "all" ? ` · ${count(item.id)}` : ""}</button>)}
        </div>
        <span className="velin__source">agent-state · snímek {agent.state ? new Date(agent.state.generatedAt).toLocaleTimeString("cs-CZ") : "—"}</span>
      </header>
      {agent.error && !agent.state && <p className="velin__empty" role="alert">{agent.error}</p>}
      {!agent.state && !agent.error && <p className="velin__empty">Načítám stav pro agenty…</p>}
      {view && all && <div className="velin__grid">
        <div className="velin__main">
          <div className="velin__project">
            <div><span className="velin__eyebrow">Projekt</span><h2 className="velin__title">{projectName || project}</h2></div>
            <div className="velin__project-bar">
              <div className="velin__stack" aria-hidden="true">
                {(["ok", "run", "gate", "human", "bad", "blocked"] as const).map(tone => all.total[tone] ? <i key={tone} className={"velin__stack-part velin__stack-part--" + tone}
                  style={{ flexGrow: all.total[tone] }} /> : null)}
              </div>
              <small>{all.cards} karet · {all.total.ok} v pořádku · {all.total.run} běží · {all.total.gate} čekají na bránu · {all.total.human} na tebe · {all.total.bad} problémy · {all.total.blocked} blokované</small>
            </div>
            <VelinCounts counts={all.total} />
          </div>
          {holes && <p className="velin__map-gaps" data-oh-map-gaps={holes.count}>
            Díry mapy pro agenty: <b>{holes.count}{holes.more ? "+" : ""}</b>
            {onOpenMap && <button type="button" className="velin__button" onClick={onOpenMap}>Mapa domény</button>}
          </p>}
          <VelinGuards line={guardStatus ? guardLine(guardStatus) : null} findings={alerts} onOpen={onOpen} />
          <VelinWorktrees rows={worktrees} onOpen={onOpen} />
          <VelinTrend series={trend} />
          {!view.layers.length && <p className="velin__empty">Agent-state zatím nezná žádnou kartu. Velín ukáže vrstvy, sektory a karty, jakmile vzniknou.</p>}
          {view.layers.map(layer => <VelinLayer key={layer.id} layer={layer} onOpen={onOpen} />)}
          <VelinRunning running={view.running} onOpen={onOpen} />
          <p className="velin__legend">✓ v pořádku · ▸ agent pracuje · ◷ čeká na bránu / review · ● čeká na tebe · ✕ problém · ○ blokováno předchůdcem · karty v sektoru řazené podle topoIndex</p>
        </div>
        <VelinSide decisions={view.decisions} next={view.next} onOpen={onOpen} />
      </div>}
    </section>
  );
}
