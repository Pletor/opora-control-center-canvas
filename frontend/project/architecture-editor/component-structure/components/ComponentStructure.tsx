import { useMemo } from "react";
import type { Graph } from "@/shared/types/logic/types";
import type { NodePhase } from "@/shared/desktop-state/logic/types";
import { breadcrumbs, buildStructure, pipelineSteps, toneOf, workflowChain } from "../logic/structure-model";
import StructureArea from "./StructureArea";
import StructureFlows from "./StructureFlows";
import StructureIcon from "./StructureIcon";
import "../styles/component-structure.css";

export type ComponentStructureProps = {
  graph: Graph;
  rootId: string;
  selectedId: string | null;
  phaseOf: (id: string) => NodePhase;
  isDone: (id: string) => boolean;
  disabled: boolean;
  onSelect: (id: string) => void;
  onOpen: (id: string) => void;
  onAddNode: (parentId: string) => void;
  onAddSector: (parentId: string) => void;
  onAddArea: (parentId: string) => void;
  onClose: () => void;
};

/** Sloupec „Hierarchický editor komponenty“: vnitřní struktura rootu, workflow a pipeline práce. */
export default function ComponentStructure(props: ComponentStructureProps) {
  const { graph, rootId, selectedId, phaseOf, isDone, disabled, onSelect, onOpen, onAddNode, onAddSector, onAddArea, onClose } = props;
  const root = graph.nodes.find((node) => node.id === rootId) ?? null;
  const groups = useMemo(() => buildStructure(graph, rootId, phaseOf, isDone), [graph, rootId, phaseOf, isDone]);
  const crumbs = useMemo(() => breadcrumbs(graph, rootId, selectedId), [graph, rootId, selectedId]);
  const workflow = useMemo(() => workflowChain(graph, rootId), [graph, rootId]);
  const steps = pipelineSteps(phaseOf(selectedId ?? rootId));

  return (
    <section className="component-structure" aria-label="Hierarchický editor komponenty">
      <header className="component-structure__head">
        <StructureIcon name="structure" className="component-structure__head-icon" />
        <div className="component-structure__head-text">
          <h2 className="component-structure__heading">Hierarchický editor komponenty</h2>
          <p className="component-structure__subheading">Detailní struktura, úkoly a workflow vybrané komponenty</p>
        </div>
        <button type="button" className="component-structure__back" onClick={onClose}>
          ← Zpět na mapu
        </button>
      </header>
      {root ? (
        <>
          <nav className="component-structure__crumbs" aria-label="Drobečková cesta">
            {crumbs.map((node, index) => (
              <span key={node.id} className="component-structure__crumb">
                {index > 0 ? <span aria-hidden="true">/</span> : null}
                <button
                  type="button"
                  className="component-structure__crumb-link"
                  aria-current={index === crumbs.length - 1 ? "location" : undefined}
                  onClick={() => onOpen(node.id)}
                >
                  {node.name.trim() || "Bez názvu"}
                </button>
              </span>
            ))}
          </nav>
          <div className={`component-structure__title component-structure__title--${toneOf(root)}`}>
            <StructureIcon name={root.kind === "sector" ? "sector" : toneOf(root)} className="component-structure__title-icon" />
            <div>
              <h3 className="component-structure__name">{root.name.trim() || "Bez názvu"} · vnitřní struktura</h3>
              <p className="component-structure__purpose">{root.purpose.trim() || "Účel zatím nic"}</p>
            </div>
          </div>
          <div className="component-structure__body">
            {groups.length ? null : <>
              <p className="component-structure__empty">Uvnitř zatím nic</p>
              <button type="button" className="component-structure__add" disabled={disabled} onClick={() => onAddNode(rootId)}>+ Přidat uzel</button>
              <button type="button" className="component-structure__add" disabled={disabled} onClick={() => onAddSector(rootId)}>+ Sektor</button>
            </>}
            {groups.map((group) => (
              <StructureArea
                key={group.id ?? "loose"}
                group={group}
                rootId={rootId}
                selectedId={selectedId}
                disabled={disabled}
                onSelect={onSelect}
                onOpen={onOpen}
                onAddNode={onAddNode}
                onAddSector={onAddSector}
              />
            ))}
            <button type="button" className="component-structure__add" disabled={disabled} onClick={() => onAddArea(rootId)}>
              + Přidat oblast
            </button>
            <StructureFlows workflow={workflow} steps={steps} selectedId={selectedId} onSelect={onSelect} />
          </div>
        </>
      ) : (
        <p className="component-structure__empty">Prvek je nedostupný.</p>
      )}
    </section>
  );
}
