// Obsah zásuvky pro vybraný blok nebo kartu: boční menu = stopa práce karty (docs/navrhy/2026-10-31-panel-bloku.md).
// Bez `blockId` je to režim karty (karty srdce a kanceláře bloky nemají): hlavička nese název a účel karty.
// Tenhle rodič jen načte data (blok z Desktop v3, kartu z agent-state, stopu z `card-trail`) a předá je dílku;
// panel nic neukládá. Odpověď srdci posílá App, odkazy otevírají jednotný detail karty.
import { useEffect } from "react";
import BlockPanel from "@/editor/block-panel/components/BlockPanel";
import { cardLabel, panelView } from "@/editor/block-panel/logic/panel-view";
import { heartReply } from "@/editor/block-panel/logic/panel-work";
import { useCardTrail } from "@/editor/block-panel/logic/use-card-trail";
import { useAgentState } from "@/hub/oporahub-agent-state/logic/use-agent-state";
import { cardEntry } from "@/hub/oporahub-card-drawer/logic/card-header";
import { openCardDrawer } from "@/hub/oporahub-card-drawer/open";
import type { NodeWorkflowFull } from "@/shared/desktop-state/logic/types";
import type { CanvasNode, GraphEdge } from "@/shared/types/logic/types";

export default function BlockDrawerContent({
  project,
  workspace,
  node,
  workflow,
  blockId,
  edges,
  nodes,
  onSelectNode,
  onAskHeart,
}: {
  project: string;
  workspace: string;
  node: CanvasNode;
  workflow: NodeWorkflowFull;
  /** Vybraný blok; `null` = panel otevřený z karty bez bloku. */
  blockId: string | null;
  /** Vazby grafu: popisek portu bloku, ze kterého vazba vede. */
  edges: GraphEdge[];
  /** Karty grafu: jména předchůdců a zdrojů vazeb („na kartu 3·02 …“, „Vstup přichází z …“). */
  nodes: CanvasNode[];
  /** Blok zmizel (smazán jinde): výběr spadne zpět na uzel. */
  onSelectNode: () => void;
  /** Odpověď člověka srdci; `true` = odesláno. */
  onAskHeart: (text: string) => Promise<boolean>;
}) {
  const block = blockId ? workflow.blocks.find((b) => b.id === blockId) ?? null : null;
  const lost = !!blockId && !block;
  // Externí zásah (smazání bloku odjinud) shodí vybraný blok ze stavu; tady se to jen doloží pojistkou,
  // hlavní přepnutí výběru dělá App v useEffect nad `selection`.
  useEffect(() => { if (lost) onSelectNode(); }, [lost, onSelectNode]);
  const agent = useAgentState(project, workspace);
  const trail = useCardTrail(project, workspace, node.id, agent.etag);
  const card = cardEntry(agent.state, node.id);
  if (lost) return null;
  const labelOf = (id: string) => cardLabel(nodes.find((n) => n.id === id)?.name ?? id.slice(0, 8), cardEntry(agent.state, id)?.order);
  const view = panelView({ block, blocks: workflow.blocks, cardId: node.id, cardName: node.name, cardPurpose: node.purpose,
    card, trail: trail.data, edges, labelOf });
  return (
    <BlockPanel
      {...view}
      loading={trail.busy && !trail.data}
      error={trail.error}
      onOpenCard={(tab) => openCardDrawer(node.id, tab)}
      onAnswerHeart={(item, text) => onAskHeart(heartReply({ id: node.id, name: node.name }, item, text))}
      onClose={onSelectNode}
    />
  );
}
