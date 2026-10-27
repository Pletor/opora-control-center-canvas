import { useCallback, useMemo, useState } from "react";
import type { CanvasNode } from "@/shared/types/logic/types";
import { derivedForDomain } from "@/project/architecture-editor/domain-map/logic/derived-journeys";
import { useStudioData } from "../logic/use-studio-data";
import { useStudioFocus } from "../logic/use-studio-focus";
import { levelOf } from "../logic/studio-level";
import { cardStatus } from "../logic/studio-status";
import { cardInLevel, studioTrail } from "../logic/studio-tree";
import { focusUp } from "../logic/studio-route";
import { cardView, KIND_LABEL } from "../studio-card/logic/card-view";
import { detailView } from "../studio-detail/logic/detail-model";
import { studioLanes } from "../studio-journeys/logic/studio-lanes";
import StudioCanvas from "../studio-canvas/components/StudioCanvas";
import StudioBreadcrumbs from "../studio-breadcrumbs/components/StudioBreadcrumbs";
import StudioDetail from "../studio-detail/components/StudioDetail";
import StudioJourneys from "../studio-journeys/components/StudioJourneys";
import "../styles/studio.css";

type Props = {
  project: string; workspace: string;
  /** Schopnost projektu (od App): stav práce worktree se čte jen u projektů, které worktree mají. */
  worktreeLive: boolean;
  /** Otevře Architekturu projektu s parametry editoru (`editorId`, `domainId`, `pageId`, `architectureNode`). */
  onOpenArchitecture: (params: Record<string, string>) => void;
};

/** Záložka Studio (docs/studio.md, vrstva Skutečnost): fraktální plátno projekt → doména → stránka → sekce → komponenta
 * v designu TechViz, drobečky nahoře, panel detailu vpravo a na doméně pás cest zákazníka pod plátnem. Skládá dílky,
 * drží zanoření (v adrese) a výběr; nic neukládá, všechno jen čte. */
export default function Studio({ project, workspace, worktreeLive, onOpenArchitecture }: Props) {
  const data = useStudioData(project, workspace, worktreeLive);
  const { tree, graph, facts } = data;
  const { focus, selected, select, open } = useStudioFocus(tree, data.loaded);
  const [lanesOpen, setLanesOpen] = useState(true);
  const level = useMemo(() => levelOf(tree, graph, focus), [tree, graph, focus]);
  const statuses = useMemo(() => new Map([...level.cards, ...(level.focus ? [level.focus] : [])].map((item) => [item.id, cardStatus(tree, item, facts)])), [tree, level, facts]);
  const views = useMemo(() => level.cards.map((item) => cardView(item, statuses.get(item.id)!)), [level, statuses]);
  const grouped = useMemo(() => new Set(level.cards.filter((item) => item.unsectioned).map((item) => item.id)), [level]);
  const crumbs = [{ id: null, label: "Projekt", kind: "Projekt" }, ...studioTrail(tree, focus).map((item) => ({ id: item.id, label: item.name, kind: KIND_LABEL[item.kind] }))];
  const shown = (selected && level.cards.find((item) => item.id === selected)) || level.focus;
  const detail = shown ? detailView({ tree, item: shown, status: statuses.get(shown.id)!, facts, links: level.links, focus: shown === level.focus, project, workspace }) : null;
  const enter = useCallback((id: string) => { if (tree.items.has(id)) open(id); }, [tree, open]);
  const up = () => { if (focus) open(focusUp(tree, focus), focus); };
  const domain = level.focus?.kind === "domain" ? level.focus : null;
  const lanes = useMemo(() => {
    if (!domain || domain.node?.site?.kind !== "application") return null;
    const pages = [...tree.items.values()].filter((item) => item.kind === "page" && item.domainId === domain.id).map((item) => item.node as CanvasNode);
    return studioLanes(domain.node.site, pages, derivedForDomain(data.derived ?? [], domain.id));
  }, [domain, tree, data.derived]);
  return <section className="studio" data-testid="studio">
    <header className="studio__bar">
      <span className="studio__layer" title="Vrstva Skutečnost: jen co v projektu opravdu je; nic se tu neukládá">Skutečnost</span>
      <StudioBreadcrumbs crumbs={crumbs} onOpen={(id) => open(id, focus ? cardInLevel(tree, id, focus) : null)}/>
      <button type="button" className="studio__reload" onClick={data.reload} disabled={data.loading} title="Znovu načíst mapu a stav práce">Obnovit</button>
    </header>
    {data.error && <p className="studio__error" role="alert">{data.error}</p>}
    <div className="studio__body">
      <div className="studio__stage">
        {!data.loaded ? <p className="studio__loading">Načítám architekturu…</p>
          : <StudioCanvas levelKey={focus ?? "project"} cards={views} grouped={grouped} links={level.links} selected={selected} onSelect={select} onEnter={enter} onUp={up}/>}
        {lanes && <StudioJourneys lanes={lanes} open={lanesOpen} onToggle={() => setLanesOpen((value) => !value)} onPage={(pageId) => open(tree.parent.get(pageId) ?? null, pageId)}/>}
      </div>
      <StudioDetail view={detail} selected={!!selected && shown !== level.focus} onOpenEditor={onOpenArchitecture} onClear={() => select(null)}/>
    </div>
  </section>;
}
