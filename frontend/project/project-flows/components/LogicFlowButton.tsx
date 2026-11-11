import { useContext } from "react";
import { ProjectFlowsContext } from "../logic/project-flows-context";
import "../styles/project-flows.css";

/** Nastavit logiku prvku plátna 2: ⚙ otevře plátno logiky, a když ho prvek ještě nemá, okno jeho založení.
 * `compact` je značka na štítku prvku (plné ⚙ = plátno existuje), jinak řádek v Detailu prvku. */
export default function LogicFlowButton({ node, compact = false }: { node: { id: string; name: string }; compact?: boolean }) {
  const { flows, onSetLogic } = useContext(ProjectFlowsContext);
  if (!onSetLogic) return null;
  const has = !!flows.get(node.id)?.length;
  const label = has ? "Otevřít plátno logiky" : "Nastavit logiku";
  return <button type="button" className={"project-flows__logic" + (compact ? " project-flows__logic--compact" : "") + (has ? " project-flows__logic--set" : "")}
    title={label} aria-label={compact ? `${label}: ${node.name}` : undefined} data-testid={"logic-flow-" + node.id} onClick={() => onSetLogic(node)}>
    {compact ? "⚙" : `⚙ ${label}`}
  </button>;
}
