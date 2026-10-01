// Seznam kapitol pod dokumentem vrstvy: každé dítě vrstvy jedna `TextChapter`. Tady se rozhoduje, kdy
// kapitola dostane svůj editor: až při prvním rozbalení (`view.mounted`), a pak už napořád, dokud se
// nezmění vrstva — sbalení editor jen skryje. Dílek nic nenačítá; souhrn paměti a briefy dostává hotové.
import NodeTextEditor from "@/editor/node-detail/content/components/NodeTextEditor";
import TextChapter from "@/editor/node-detail/content/components/TextChapter";
import type { LinkTarget } from "@/editor/node-detail/content/components/BlockOutline";
import type { ChapterView } from "@/editor/node-detail/content/logic/text-chapters";
import { chapterWork, type ChapterWork, type OverviewEntry } from "@/editor/node-detail/agent-summary/logic/agent-summary";
import type { CanvasNode } from "@/shared/types/logic/types";

export default function TextChapters({
  project, workspace, nodes, targets, view, highlighted, hovered, works, overviews, isClosed, now,
  onToggle, onHover, onEnter, onOpenNode, onAgentTask, onTextSaved,
}: {
  project: string;
  workspace: string;
  nodes: CanvasNode[];
  targets: LinkTarget[];
  view: ChapterView;
  highlighted: string | null;
  hovered: string | null;
  works: Record<string, ChapterWork>;
  overviews: Record<string, OverviewEntry>;
  isClosed: (nodeId: string) => boolean;
  now: Date;
  onToggle: (id: string) => void;
  onHover: (id: string | null) => void;
  onEnter: (id: string) => void;
  onOpenNode: (id: string) => void;
  onAgentTask: (nodeId: string, text: string, source: "block" | "journal") => void;
  onTextSaved: () => void;
}) {
  return (
    <div className="text-children">
      {nodes.map((node) => {
        const card = node.kind !== "comment";
        return (
          <TextChapter
            key={node.id}
            node={node}
            expanded={view.expanded.has(node.id)}
            highlighted={highlighted === node.id}
            hovered={hovered === node.id}
            work={card ? chapterWork(node.id, works, overviews) ?? null : null}
            overview={card ? overviews[node.id]?.overview ?? null : null}
            closed={isClosed(node.id)}
            now={now}
            onToggle={onToggle}
            onHover={onHover}
            onEnter={onEnter}
          >
            {view.mounted.has(node.id) && (
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
            )}
          </TextChapter>
        );
      })}
    </div>
  );
}
