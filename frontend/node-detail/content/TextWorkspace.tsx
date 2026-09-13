import NodeTextEditor from "@/node-detail/content/NodeTextEditor";
import type { LinkTarget } from "@/node-detail/content/BlockOutline";
import type { CanvasNode } from "@/shared/types/types";

/** Dokument vrstvy a jejích dětí: jeden sloupec textu, kontext (souvislosti, deník) nese inspektor. */
export default function TextWorkspace({
  project,
  workspace,
  layer,
  children,
  targets,
  onEnter,
  onOpenNode,
  onAgentTask,
  onTextSaved,
}: {
  project: string;
  workspace: string;
  layer?: CanvasNode;
  children: CanvasNode[];
  targets: LinkTarget[];
  onEnter: (id: string) => void;
  onOpenNode: (id: string) => void;
  onAgentTask: (nodeId: string, text: string, source: "block" | "journal") => void;
  /** Uložení textu vrstvy nebo dítěte: inspektor obnoví souvislosti ze serveru. */
  onTextSaved: () => void;
}) {
  return (
    <div className="text-workspace" aria-label="Fraktální text">
      <header className="text-head">
        <h2>{layer?.name ?? "Projektový kořen"}</h2>
        <p className="muted">
          Enter přidá blok, Tab zanoří, <kbd>/</kbd> otevře příkazy, <kbd>[[</kbd> odkáže na uzel. Bloky se ukládají samy; zdrojový text ručně.
        </p>
      </header>
      {layer && (
        <NodeTextEditor
          key={JSON.stringify([project, workspace, layer.id])}
          project={project}
          workspace={workspace}
          node={layer.id}
          targets={targets}
          onOpenNode={onOpenNode}
          onAgentTask={(text) => onAgentTask(layer.id, text, "block")}
          onSaved={onTextSaved}
        />
      )}
      <div className="text-children">
        {children.map((node) => (
          <article className="text-block" data-testid="text-block" data-node-id={node.id} key={node.id}>
            <header>
              <h3>
                <span className="kind-mark">{node.kind === "sector" ? "Sektor" : "Uzel"}</span> {node.name}
              </h3>
              <button type="button" onClick={() => onEnter(node.id)}>
                Zanořit
              </button>
            </header>
            <NodeTextEditor
              key={JSON.stringify([project, workspace, node.id])}
              project={project}
              workspace={workspace}
              node={node.id}
              targets={targets}
              onOpenNode={onOpenNode}
              onAgentTask={(text) => onAgentTask(node.id, text, "block")}
              onSaved={onTextSaved}
            />
          </article>
        ))}
      </div>
      {!children.length && (
        <p className="muted">Tato vrstva nemá děti. Přidejte uzel nebo sektor horním tlačítkem, nebo dvojklikem na prázdné plátno ve Struktuře.</p>
      )}
    </div>
  );
}
