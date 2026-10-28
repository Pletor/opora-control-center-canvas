import type { CanvasNode } from "@/shared/types/logic/types";
import type { NodePhase } from "@/shared/desktop-state/logic/types";
import type { SpecState } from "../logic/use-node-spec";
import BriefStatus from "./BriefStatus";
import IdentityForm from "./IdentityForm";

type Props = {
  node: CanvasNode;
  spec: SpecState;
  phase: NodePhase;
  done: boolean;
  disabled: boolean;
  onIdentity: (original: CanvasNode, name: string, purpose: string) => Promise<void>;
};

/** Záložka Zadání: identita, kritéria dokončení a stav. Vazby prvku ukazuje jen záložka Vazby. */
export default function BriefTab({ node, spec, phase, done, disabled, onIdentity }: Props) {
  return (
    <div className="element-detail__pane">
      <IdentityForm key={node.id} node={node} disabled={disabled} onIdentity={onIdentity} />
      <BriefStatus spec={spec} phase={phase} done={done} />
    </div>
  );
}
