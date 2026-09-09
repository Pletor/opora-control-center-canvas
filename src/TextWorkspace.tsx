import NodeTextEditor from "./NodeTextEditor";
import type { CanvasNode } from "./types";

export default function TextWorkspace({ project, workspace, layer, children, onEnter }: { project: string; workspace: string; layer?: CanvasNode; children: CanvasNode[]; onEnter: (id: string) => void }) {
  return <div className="text-workspace" aria-label="Fraktální text">
    <header><div className="eyebrow">DOKUMENT A OUTLINER · STEJNÉ UZLY JAKO CANVAS</div><h2>{layer?.name ?? "Projektový kořen"}</h2><p>Každý blok je skutečný uzel nebo sektor. Zanořit otevře jeho dokument a děti. Ctrl+S ukládá právě psaný text; před reloadem uložte.</p></header>
    {layer && <NodeTextEditor key={JSON.stringify([project, workspace, layer.id])} project={project} workspace={workspace} node={layer.id} />}
    <div className="text-children">{children.map(node => <article className="text-block" data-testid="text-block" data-node-id={node.id} key={node.id}>
      <header><h3>{node.kind === "sector" ? "◇" : "•"} {node.name}</h3><button onClick={() => onEnter(node.id)}>Zanořit</button></header>
      <NodeTextEditor key={JSON.stringify([project, workspace, node.id])} project={project} workspace={workspace} node={node.id} />
    </article>)}</div>
    {!children.length && <p className="muted">Tato vrstva nemá děti. Přidejte uzel nebo sektor horním tlačítkem.</p>}
  </div>;
}
