// Obsah zásuvky pro vybraný blok: boční menu bloku = stopa práce jeho karty (docs/navrhy/2026-10-31-panel-bloku.md).
// Tenhle rodič jen načte data (blok z Desktop v3, kartu z agent-state, stopu z `card-trail`) a předá je dílku;
// panel nic neukládá. Odpověď srdci posílá App, odkazy otevírají jednotný detail karty.
import { useEffect } from "react";
import BlockPanel from "@/editor/block-panel/components/BlockPanel";
import { panelView } from "@/editor/block-panel/logic/panel-view";
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
  onSelectNode,
  onAskHeart,
}: {
  project: string;
  workspace: string;
  node: CanvasNode;
  workflow: NodeWorkflowFull;
  blockId: string;
  /** Vazby grafu: popisek portu bloku, ze kterého vazba vede. */
  edges: GraphEdge[];
  /** Blok zmizel (smazán jinde): výběr spadne zpět na uzel. */
  onSelectNode: () => void;
  /** Odpověď člověka srdci; `true` = odesláno. */
  onAskHeart: (text: string) => Promise<boolean>;
}) {
  const block = workflow.blocks.find((b) => b.id === blockId);
  // Externí zásah (smazání bloku odjinud) shodí vybraný blok ze stavu; tady se to jen doloží pojistkou,
  // hlavní přepnutí výběru dělá App v useEffect nad `selection`.
  useEffect(() => { if (!block) onSelectNode(); }, [block, onSelectNode]);
  const agent = useAgentState(project, workspace);
  const trail = useCardTrail(project, workspace, node.id, agent.etag);
  const card = cardEntry(agent.state, node.id);
  if (!block) return null;
  const view = panelView({ block, blocks: workflow.blocks, cardName: node.name, card, trail: trail.data, edges });
  return (
    <BlockPanel
      {...view}
      loading={trail.busy && !trail.data}
      error={trail.error}
      onOpenCard={(tab) => openCardDrawer(node.id, tab)}
      onAnswerHeart={(item, text) => onAskHeart(heartReply({ id: node.id, name: node.name }, item, text))}
    />
  );
}
