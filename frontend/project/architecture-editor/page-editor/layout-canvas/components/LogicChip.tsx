import { useContext, type PointerEvent } from "react";
import type { CanvasNode } from "@/shared/types/logic/types";
import type { CardState } from "../../../card-state/logic/card-state";
import { elementMilestones } from "../../logic/plan-progress";
import { logicLook } from "../../element-palette/logic/logic-groups";
import PageIcon from "../../components/PageIcon";
import LogicFlowButton from "@/project/project-flows/components/LogicFlowButton";
import { ProjectFlowsContext } from "@/project/project-flows/logic/project-flows-context";

type Props = {
  node: CanvasNode; state: CardState | undefined; selected: boolean; disabled: boolean;
  onSelect: (id: string) => void; onRemove: (id: string) => void; onCarry: (node: CanvasNode, event: PointerEvent) => void;
};

/** Štítek prvku logiky v boxu: symbol, druh, název a milníky Návrh → Realizace → Ověření. Klik vybere, dvojklik otevře plátno
 * logiky prvku (chybějící založí prázdné), ✕ odebere, tah přesune. ⚙ nabídne i převzetí z knihovny (plné = plátno existuje);
 * jde i na mainu, plátno toku není obsah grafu. */
export default function LogicChip({ node, state, selected, disabled, onSelect, onRemove, onCarry }: Props) {
  const look = node.element ? logicLook(node.element.kind) : { label: "Prvek", icon: "logic" as const };
  const steps = elementMilestones(state?.state);
  const { onOpenLogic } = useContext(ProjectFlowsContext);
  return <span className={"layout-canvas__chip" + (selected ? " layout-canvas__chip--selected" : "")} data-testid={"architecture-logic-" + node.id}
    onPointerDown={(event) => { if (!disabled && !(event.target as Element).closest("button.layout-canvas__chip-remove, button.project-flows__logic")) onCarry(node, event); }}>
    <button type="button" className="layout-canvas__chip-body" aria-pressed={selected} title={(state ? `${look.label} · ${state.label}` : look.label) + " · dvojklikem plátno logiky"} onClick={() => onSelect(node.id)}
      onDoubleClick={(event) => { event.stopPropagation(); onOpenLogic?.(node); }}>
      <PageIcon name={look.icon} size={14} className="layout-canvas__chip-icon"/>
      <span className="layout-canvas__chip-kind">{look.label}</span>
      <span className="layout-canvas__chip-name">{node.name}</span>
      <span className="layout-canvas__chip-steps" aria-label={steps.map((step) => `${step.label}: ${step.step === "done" ? "hotovo" : step.step === "now" ? "teď" : "čeká"}`).join(", ")}>
        {steps.map((step) => <i key={step.label} className={"layout-canvas__chip-step layout-canvas__chip-step--" + step.step}/>)}
      </span>
    </button>
    <LogicFlowButton node={node} compact/>
    {!disabled && <button type="button" className="layout-canvas__chip-remove" aria-label={`Odebrat ${node.name}`} data-testid={"architecture-logic-remove-" + node.id} onClick={() => onRemove(node.id)}>✕</button>}
  </span>;
}
