// Velín: celá pyramida projektu (oblast → sektor → karta) se stavem procesu a jedinou frontou „Čeká na tebe“.
// Rodič drží jen přehled práce, rozbalení sektorů a stránkování/filtr fronty; data skládá
// `logic/tower-model.ts` (struktura z grafu zvlášť, stav nad ní), dílky jen kreslí.
// Nic se tu nevyplňuje ani neukládá — klik otevře kartu nebo vstoupí do vrstvy na plátně.
import { useEffect, useMemo, useState } from "react";
import type { Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { useWorkOverview } from "@/editor/canvas/node-card/logic/use-work-overview";
import { INBOX_LIMIT, inboxCardCount, inboxKinds, inboxPage, looseArea, towerFrom, towerStructure, type InboxFilter, type WorkState } from "../logic/tower-model";
import { confirmSummary, proposalsBySector, runConfirm } from "../logic/inbox-actions";
import { collapseChain, layerChildren, readOpen, rootLayer, writeOpen, type OpenOverrides } from "../logic/tower-view";
import TowerArea from "./TowerArea";
import TowerChain from "./TowerChain";
import TowerLayer from "./TowerLayer";
import TowerInbox from "./TowerInbox";
import TowerSummary from "./TowerSummary";
import "../styles/control-tower.css";

type Props = {
  project: string; workspace: string; graph: Graph; state: DesktopState;
  onOpenNode: (id: string) => void; onEnterLayer: (id: string) => void;
  /** Potvrdit uzavření karty navržené agentem (tentýž handler jako na plátně). */
  onConfirmProposal?: (nodeId: string) => Promise<boolean>;
  /** Hromadně potvrdit návrhy v sektoru (tentýž handler jako na plátně). */
  onConfirmSector?: (sectorId: string, ids: string[]) => Promise<void>;
};

export default function ControlTower({ project, workspace, graph, state, onOpenNode, onEnterLayer, onConfirmProposal, onConfirmSector }: Props) {
  const revisionKey = JSON.stringify([graph.nodes.length, Object.keys(state.nodes).length]);
  const work = useWorkOverview(project, workspace, revisionKey);
  const workState: WorkState = !work ? "loading" : work.data ? "loaded" : "unavailable";
  // Ruční rozbalení přebíjí výchozí; paměť per projekt (App dává ControlTower key={project}).
  const [overrides, setOverrides] = useState<OpenOverrides>(() => readOpen(safeStorage(), project));
  useEffect(() => writeOpen(safeStorage(), project, overrides), [project, overrides]);
  const [filter, setFilter] = useState<InboxFilter>("all");
  const [limit, setLimit] = useState(INBOX_LIMIT);
  const structure = useMemo(() => towerStructure(graph), [graph]);
  const tower = useMemo(() => towerFrom(structure, state, work?.data, workState), [structure, state, work?.data, workState]);
  const loose = looseArea(tower);
  const areas = loose ? [...tower.areas, loose] : tower.areas;
  const root = useMemo(() => collapseChain(rootLayer(tower)), [tower]);
  const page = inboxPage(tower.inbox, filter, limit);
  const proposals = useMemo(() => proposalsBySector(tower.inbox), [tower.inbox]);
  // Sdílený zámek: karty, které se právě potvrzují; tlačítka, jejichž rozsah se s nimi kříží, jsou vypnutá.
  const [busy, setBusy] = useState<ReadonlySet<string>>(() => new Set());
  const names = useMemo(() => new Map(graph.nodes.map((n) => [n.id, n.name.trim() || "Nepojmenovaná karta"])), [graph]);
  const nameOf = (id: string) => names.get(id) ?? id;
  const canConfirm = !!onConfirmProposal || !!onConfirmSector;
  async function confirm(ids: string[], sectorId: string) {
    setBusy((old) => new Set([...old, ...ids]));
    try {
      // Po kartách přes onConfirmProposal (výsledek za každou), hromadné onConfirmSector jen když chybí.
      const result = await runConfirm(ids, sectorId, onConfirmProposal, onConfirmSector);
      return { message: ids.length === 1 && result.failed.length ? result.failed[0].error : confirmSummary(result, nameOf), failed: result.failed.length > 0 };
    } finally {
      setBusy((old) => new Set([...old].filter((id) => !ids.includes(id))));
    }
  }
  const nav = {
    isOpen: (id: string, byDefault: boolean) => overrides[id] ?? byDefault,
    onToggle: (id: string, open: boolean) => setOverrides((old) => ({ ...old, [id]: open })),
    onOpenNode, onEnterLayer,
  };
  const chooseFilter = (next: InboxFilter) => { setFilter(next); setLimit(INBOX_LIMIT); };
  return (
    <section className="control-tower" aria-label="Velín">
      <TowerSummary counts={tower.totals} requests={tower.inbox.length} requestCards={inboxCardCount(tower.inbox)} workState={workState} />
      <div className="control-tower__body">
        <div className="control-tower__pyramid">
          {root.chain.length > 0 ? <>
            <TowerChain chain={root.chain} onEnterLayer={onEnterLayer} />
            <TowerLayer layer={root.layer} depth={1} nav={nav} top />
          </> : areas.map((area) => (
            <TowerArea key={area.id} area={area} depth={1} siblings={layerChildren(rootLayer(tower))} nav={nav} />
          ))}
          {!areas.length && <p className="control-tower__empty">Plátno je prázdné. Velín ukáže oblasti, sektory a karty, jakmile vzniknou.</p>}
        </div>
        <TowerInbox items={page.items} total={page.total} more={page.more} kinds={inboxKinds(tower.inbox)} filter={filter}
          workState={workState} workError={work?.error} proposals={proposals}
          busy={busy} nameOf={nameOf} onConfirm={canConfirm ? confirm : undefined} onFilter={chooseFilter} onMore={() => setLimit((n) => n + INBOX_LIMIT)} onOpenNode={onOpenNode} />
      </div>
    </section>
  );
}

/** `localStorage`, nebo nic, když přístup k němu vyhodí (soukromé okno, zakázaná data). */
function safeStorage(): Storage | undefined {
  try {
    return window.localStorage;
  } catch {
    return undefined;
  }
}
