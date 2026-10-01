import { useEffect, useRef, useState } from "react";
import NodeTextEditor from "@/editor/node-detail/content/components/NodeTextEditor";
import TextChapters from "@/editor/node-detail/content/components/TextChapters";
import TextWorkspaceHead from "@/editor/node-detail/content/components/TextWorkspaceHead";
import AgentSegmentsBoard from "@/editor/node-detail/agent-workspace/segments/components/AgentSegmentsBoard";
import AgentSummary from "@/editor/node-detail/agent-summary/components/AgentSummary";
import type { LinkTarget } from "@/editor/node-detail/content/components/BlockOutline";
import {
  EMPTY_CHAPTER_VIEW, collapseAll, expandAll, expandedCount, toggleChapter, viewWithExpanded, type ChapterView,
} from "@/editor/node-detail/content/logic/text-chapters";
import { summaryRows, type SummaryFilter, type SummarySort } from "@/editor/node-detail/agent-summary/logic/agent-summary";
import { useChapterOverviews } from "@/editor/node-detail/agent-summary/logic/use-chapter-overviews";
import { useNow } from "@/editor/node-detail/agent-summary/logic/use-now";
import type { CanvasNode } from "@/shared/types/logic/types";

/** Podzáložka celé stránky Text: dnešní obsah uzlu, nebo pracovní prostor agenta (docs/karta-pro-agenty.md). */
export type TextSubtab = "user" | "agents";

/** Jak dlouho svítí kapitola, na kterou se skočilo ze souhrnu. */
export const HIGHLIGHT_MS = 1500;

/**
 * Stránka módu Text (`docs/souhrn-prace-agentu.md`). Podzáložka Uživatel skládá shora dolů hlavičku,
 * souhrn práce agentů, dokument vrstvy a sbalitelné kapitoly dětí. Rodič drží jen stav pohledu —
 * rozbalení a připojené editory podle vrstvy (výchozí vše sbalené), filtr, řazení, hover a krátké
 * zvýraznění po skoku ze souhrnu — a nic z toho neukládá na server ani do localStorage. Text ukládá
 * `NodeTextEditor`. Podzáložka Agenti opouští sloupec a rozprostře se přes plochu (`AgentSegmentsBoard`).
 */
export default function TextWorkspace({
  project,
  workspace,
  layer,
  children,
  targets,
  subtab,
  onSubtab,
  isClosed,
  onEnter,
  onOpenNode,
  onAgentTask,
  onTextSaved,
  refreshKey = "",
}: {
  project: string;
  workspace: string;
  layer?: CanvasNode;
  children: CanvasNode[];
  targets: LinkTarget[];
  subtab: TextSubtab;
  onSubtab: (subtab: TextSubtab) => void;
  /** Uzavřená karta (done.confirmed) nedovolí zápis do pracovního prostoru agenta. */
  isClosed: (nodeId: string) => boolean;
  onEnter: (id: string) => void;
  onOpenNode: (id: string) => void;
  onAgentTask: (nodeId: string, text: string, source: "block" | "journal") => void;
  /** Uložení textu vrstvy nebo dítěte: inspektor obnoví souvislosti ze serveru. */
  onTextSaved: () => void;
  /** Otisk stavu plátna; jeho změna (se zpožděním) obnoví souhrn paměti a briefy rozbalených karet. */
  refreshKey?: string;
}) {
  const agents = subtab === "agents";
  const viewKey = JSON.stringify([project, workspace, layer?.id ?? "root"]);
  const [views, setViews] = useState<Record<string, ChapterView>>({});
  const view = views[viewKey] ?? EMPTY_CHAPTER_VIEW;
  const [filter, setFilter] = useState<SummaryFilter>("all");
  const [sort, setSort] = useState<SummarySort>("canvas");
  const [hovered, setHovered] = useState<string | null>(null);
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const highlightTimer = useRef<number | null>(null);
  const page = useRef<HTMLDivElement>(null);
  const now = useNow();
  useEffect(() => () => { if (highlightTimer.current) window.clearTimeout(highlightTimer.current); }, []);

  const cards = children.filter((node) => node.kind !== "comment");
  // Na podzáložce Agenti se briefy kapitol nenačítají: kapitoly tam nejsou vidět.
  const expandedIds = agents ? [] : cards.filter((node) => view.expanded.has(node.id)).map((node) => node.id);
  const { works, overviews, refresh } = useChapterOverviews({ project, workspace, expandedIds, refreshKey });
  const rows = summaryRows(children, view.expanded, works, overviews, isClosed);

  function changeExpanded(next: (expanded: ReadonlySet<string>) => ReadonlySet<string>) {
    setViews((prev) => {
      const current = prev[viewKey] ?? EMPTY_CHAPTER_VIEW;
      return { ...prev, [viewKey]: viewWithExpanded(current, next(current.expanded)) };
    });
  }

  /** Skok ze souhrnu: kapitola dojede nahoru a krátce se rozsvítí, ať oko ví, kam se dívat. */
  function jump(id: string) {
    const target = page.current?.querySelector<HTMLElement>(`article.text-block[data-node-id="${CSS.escape(id)}"]`);
    target?.scrollIntoView({ block: "start", behavior: "smooth" });
    setHighlighted(id);
    if (highlightTimer.current) window.clearTimeout(highlightTimer.current);
    highlightTimer.current = window.setTimeout(() => {
      highlightTimer.current = null;
      setHighlighted(null);
    }, HIGHLIGHT_MS);
  }

  return (
    <div ref={page} className={"text-workspace" + (agents ? " text-workspace--agents" : "")} aria-label="Fraktální text">
      <TextWorkspaceHead
        title={layer?.name ?? "Projektový kořen"}
        subtab={subtab}
        onSubtab={onSubtab}
        expandedCount={expandedCount(children.map((node) => node.id), view.expanded)}
        totalCount={children.length}
        onExpandAll={() => changeExpanded(() => expandAll(children.map((node) => node.id)))}
        onCollapseAll={() => changeExpanded(() => collapseAll())}
      />
      {agents ? (
        <AgentSegmentsBoard
          key={JSON.stringify([project, workspace, layer?.id ?? ""])}
          project={project}
          workspace={workspace}
          layer={layer}
          children={children}
          isClosed={isClosed}
          onEnter={onEnter}
        />
      ) : (
        <>
          <AgentSummary
            rows={rows}
            expandedCount={rows.length}
            totalCount={cards.length}
            filter={filter}
            sort={sort}
            onFilter={setFilter}
            onSort={setSort}
            onRefresh={refresh}
            hovered={hovered}
            onHover={setHovered}
            onJump={jump}
            now={now}
          />
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
          <TextChapters
            project={project}
            workspace={workspace}
            nodes={children}
            targets={targets}
            view={view}
            highlighted={highlighted}
            hovered={hovered}
            works={works}
            overviews={overviews}
            isClosed={isClosed}
            now={now}
            onToggle={(id) => changeExpanded((expanded) => toggleChapter(expanded, id))}
            onHover={setHovered}
            onEnter={onEnter}
            onOpenNode={onOpenNode}
            onAgentTask={onAgentTask}
            onTextSaved={onTextSaved}
          />
          {!children.length && (
            <p className="muted">Tato vrstva nemá děti. Přidejte uzel nebo sektor horním tlačítkem, nebo dvojklikem na prázdné plátno ve Struktuře.</p>
          )}
        </>
      )}
    </div>
  );
}
