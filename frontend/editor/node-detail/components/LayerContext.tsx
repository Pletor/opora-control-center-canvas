import { useState } from "react";
import NodeJournal from "@/editor/node-detail/journal/components/NodeJournal";
import NodeLinksPanel from "@/editor/node-detail/links/components/NodeLinksPanel";
import type { LinkTarget } from "@/editor/node-detail/content/components/BlockOutline";
import type { CanvasNode } from "@/shared/types/logic/types";

/** Kontext vrstvy v módu Text: souvislosti a datovaný deník téhož uzlu. */
export default function LayerContext({
  project,
  workspace,
  layer,
  targets,
  readOnly,
  revision,
  onOpenNode,
  onAgentTask,
}: {
  project: string;
  workspace: string;
  layer: CanvasNode;
  targets: LinkTarget[];
  readOnly: boolean;
  /** Bump po uložení textu vrstvy nebo dětí: souvislosti se načtou znovu ze serveru. */
  revision: number;
  onOpenNode: (id: string) => void;
  onAgentTask: (text: string) => void;
}) {
  const [side, setSide] = useState<"links" | "journal">("links");
  return (
    <div className="layer-context">
      <div className="eyebrow">VRSTVA · KONTEXT</div>
      <h2>{layer.name}</h2>
      <div className="panel-tabs" role="tablist" aria-label="Souvislosti a deník">
        <button type="button" role="tab" aria-selected={side === "links"} onClick={() => setSide("links")}>
          Souvislosti
        </button>
        <button type="button" role="tab" aria-selected={side === "journal"} onClick={() => setSide("journal")}>
          Deník
        </button>
      </div>
      {side === "links" ? (
        <NodeLinksPanel project={project} workspace={workspace} node={layer.id} revision={revision} readOnly={readOnly} onOpenNode={onOpenNode} />
      ) : (
        <NodeJournal project={project} workspace={workspace} node={layer.id} nodeName={layer.name} targets={targets} onOpenNode={onOpenNode} onAgentTask={onAgentTask} />
      )}
    </div>
  );
}
