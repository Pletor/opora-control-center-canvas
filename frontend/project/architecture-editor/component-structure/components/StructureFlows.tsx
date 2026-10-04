import type { CanvasNode } from "@/shared/types/logic/types";
import type { PipelineStep } from "../logic/structure-model";
import StructureIcon from "./StructureIcon";

type Props = {
  workflow: CanvasNode[];
  steps: PipelineStep[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

/** Spodní dva pásy: řetěz uzlů podle vazeb `next` a pipeline pracovních fází. */
export default function StructureFlows({ workflow, steps, selectedId, onSelect }: Props) {
  return (
    <>
      <section className="component-structure__flow" aria-label="Workflow uživatele">
        <h3 className="component-structure__flow-title">
          <StructureIcon name="workflow" />
          Workflow uživatele <span className="component-structure__flow-note">(chování aplikace)</span>
        </h3>
        {workflow.length ? (
          <ol className="component-structure__chain">
            {workflow.map((node, index) => (
              <li key={node.id} className="component-structure__link">
                {index > 0 ? <span className="component-structure__arrow" aria-hidden="true">→</span> : null}
                <button
                  type="button"
                  className={`component-structure__step${node.id === selectedId ? " component-structure__step--selected" : ""}`}
                  onClick={() => onSelect(node.id)}
                >
                  <span className="component-structure__step-name">{node.name.trim() || "Bez názvu"}</span>
                  {node.purpose.trim() ? <span className="component-structure__step-purpose">{node.purpose}</span> : null}
                </button>
              </li>
            ))}
          </ol>
        ) : (
          <p className="component-structure__empty">Zatím bez vazeb</p>
        )}
      </section>
      <section className="component-structure__flow" aria-label="Pipeline práce">
        <h3 className="component-structure__flow-title">
          <StructureIcon name="pipeline" />
          Pipeline práce <span className="component-structure__flow-note">(vývojový proces)</span>
        </h3>
        <ol className="component-structure__chain">
          {steps.map((step, index) => (
            <li key={step.phase} className="component-structure__link">
              {index > 0 ? <span className="component-structure__arrow" aria-hidden="true">→</span> : null}
              <span
                className={`component-structure__phase component-structure__phase--${step.state}`}
                aria-current={step.state === "current" ? "step" : undefined}
              >
                {step.label}
              </span>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}
