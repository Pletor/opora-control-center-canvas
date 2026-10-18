// Pruh osmi teček bran cyklu u fragmentu ve stromu (docs/schranka-neurony.md §6): zapnutá, další na řadě,
// vypnutá, zneplatněná. Každá tečka má titulek brány česky. Jen zobrazení.
import type { GateSummary } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { gateBarLabel, gateDots } from "@/editor/node-detail/brief-vault/logic/gate-bar";

export default function GateBar({ node }: { node: GateSummary }) {
  return (
    <span className="brief-gates" role="img" aria-label={gateBarLabel(node)} title={gateBarLabel(node)} data-testid="brief-gates">
      {gateDots(node).map((dot) => (
        <i key={dot.gate} className={"brief-gates__dot brief-gates__dot--" + dot.state} title={dot.label} />
      ))}
    </span>
  );
}
