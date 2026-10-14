// Velín: celá pyramida projektu (oblast → sektor → karta) se stavem procesu a jedinou frontou „Čeká na tebe“.
// Rodič drží jen přehled práce, rozbalení sektorů a stránkování/filtr fronty; data skládá
// `logic/tower-model.ts` (struktura z grafu zvlášť, stav nad ní), dílky jen kreslí.
// Nic se tu nevyplňuje ani neukládá — klik otevře kartu nebo vstoupí do vrstvy na plátně.
import { useMemo, useState } from "react";
import type { Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { useWorkOverview } from "@/editor/canvas/node-card/logic/use-work-overview";
import { INBOX_LIMIT, inboxCardCount, inboxKinds, inboxPage, looseArea, towerFrom, towerStructure, type InboxFilter, type WorkState } from "../logic/tower-model";
import TowerArea from "./TowerArea";
import TowerInbox from "./TowerInbox";
import TowerSummary from "./TowerSummary";
import "../styles/control-tower.css";

type Props = {
  project: string; workspace: string; graph: Graph; state: DesktopState;
  onOpenNode: (id: string) => void; onEnterLayer: (id: string) => void;
};

export default function ControlTower({ project, workspace, graph, state, onOpenNode, onEnterLayer }: Props) {
  const revisionKey = JSON.stringify([graph.nodes.length, Object.keys(state.nodes).length]);
  const work = useWorkOverview(project, workspace, revisionKey);
  const workState: WorkState = !work ? "loading" : work.data ? "loaded" : "unavailable";
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const [filter, setFilter] = useState<InboxFilter>("all");
  const [limit, setLimit] = useState(INBOX_LIMIT);
  const structure = useMemo(() => towerStructure(graph), [graph]);
  const tower = useMemo(() => towerFrom(structure, state, work?.data, workState), [structure, state, work?.data, workState]);
  const loose = looseArea(tower);
  const areas = loose ? [...tower.areas, loose] : tower.areas;
  const page = inboxPage(tower.inbox, filter, limit);
  const toggle = (id: string) => setExpanded((old) => {
    const next = new Set(old);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  const chooseFilter = (next: InboxFilter) => { setFilter(next); setLimit(INBOX_LIMIT); };
  return (
    <section className="control-tower" aria-label="Velín">
      <TowerSummary counts={tower.totals} requests={tower.inbox.length} requestCards={inboxCardCount(tower.inbox)} workState={workState} />
      <div className="control-tower__body">
        <div className="control-tower__pyramid">
          {areas.map((area) => (
            <TowerArea key={area.id} area={area} expanded={expanded} onToggle={toggle} onOpenNode={onOpenNode} onEnterLayer={onEnterLayer} />
          ))}
          {!areas.length && <p className="control-tower__empty">Plátno je prázdné. Velín ukáže oblasti, sektory a karty, jakmile vzniknou.</p>}
        </div>
        <TowerInbox items={page.items} total={page.total} more={page.more} kinds={inboxKinds(tower.inbox)} filter={filter}
          workState={workState} workError={work?.error} onFilter={chooseFilter} onMore={() => setLimit((n) => n + INBOX_LIMIT)} onOpenNode={onOpenNode} />
      </div>
    </section>
  );
}
