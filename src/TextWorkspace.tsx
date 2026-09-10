import { useState } from "react";
import NodeTextEditor from "./NodeTextEditor";
import NodeJournal from "./NodeJournal";
import NodeLinksPanel from "./NodeLinksPanel";
import type { LinkTarget } from "./BlockOutline";
import type { CanvasNode } from "./types";

export default function TextWorkspace({
  project,
  workspace,
  layer,
  children,
  targets,
  readOnly,
  onEnter,
  onOpenNode,
  onAgentTask,
}: {
  project: string;
  workspace: string;
  layer?: CanvasNode;
  children: CanvasNode[];
  targets: LinkTarget[];
  readOnly: boolean;
  onEnter: (id: string) => void;
  onOpenNode: (id: string) => void;
  onAgentTask: (nodeId: string, text: string, source: "block" | "journal") => void;
}) {
  const [side, setSide] = useState<"links" | "journal">("links");
  return <div className="text-workspace" aria-label="Fraktální text">
    <header><div className="eyebrow">DOKUMENT A OUTLINER · STEJNÉ UZLY JAKO CANVAS</div><h2>{layer?.name ?? "Projektový kořen"}</h2><p>Každý blok je součást dokumentu uzlu. Enter přidá blok, Tab zanoří, <kbd>/</kbd> otevře příkazy, <kbd>[[</kbd> odkáže na existující uzel. Bloky se ukládají samy; zdrojový text má ruční uložení.</p></header>
    {layer && <div className="text-layer">
      <NodeTextEditor key={JSON.stringify([project, workspace, layer.id])} project={project} workspace={workspace} node={layer.id} targets={targets} onOpenNode={onOpenNode} onAgentTask={text => onAgentTask(layer.id, text, "block")} />
      <aside className="text-side">
        <div className="side-tabs" role="tablist" aria-label="Souvislosti a deník">
          <button role="tab" aria-selected={side === "links"} onClick={() => setSide("links")}>Souvislosti</button>
          <button role="tab" aria-selected={side === "journal"} onClick={() => setSide("journal")}>Deník</button>
        </div>
        {side === "links"
          ? <NodeLinksPanel project={project} workspace={workspace} node={layer.id} revision={0} readOnly={readOnly} onOpenNode={onOpenNode} />
          : <NodeJournal project={project} workspace={workspace} node={layer.id} nodeName={layer.name} targets={targets} onOpenNode={onOpenNode} onAgentTask={text => onAgentTask(layer.id, text, "journal")} />}
      </aside>
    </div>}
    <div className="text-children">{children.map(node => <article className="text-block" data-testid="text-block" data-node-id={node.id} key={node.id}>
      <header><h3>{node.kind === "sector" ? "◇" : "•"} {node.name}</h3><button onClick={() => onEnter(node.id)}>Zanořit</button></header>
      <NodeTextEditor key={JSON.stringify([project, workspace, node.id])} project={project} workspace={workspace} node={node.id} targets={targets} onOpenNode={onOpenNode} onAgentTask={text => onAgentTask(node.id, text, "block")} />
    </article>)}</div>
    {!children.length && <p className="muted">Tato vrstva nemá děti. Přidejte uzel nebo sektor horním tlačítkem, nebo dvojklikem na prázdné plátno ve struktuře.</p>}
  </div>;
}
