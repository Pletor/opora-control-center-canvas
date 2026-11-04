import { useContext } from "react";
import { ProjectFlowsContext } from "../logic/project-flows-context";
import "../styles/project-flows.css";

/** Plátna toku převzatá k doméně nebo stránce: název otevře plátno, pod ním „vychází z <prvek>@<verze>“ a zlaté
 *  upozornění, když má zdroj v knihovně novější verzi. Bez převzatého plátna karta nic neukáže. */
export default function ProjectFlowLinks({ nodeId }: { nodeId: string }) {
  const { flows, onOpen } = useContext(ProjectFlowsContext);
  const own = flows.get(nodeId) ?? [];
  if (!own.length) return null;
  return <ul className="project-flows" aria-label="Plátna toku" data-testid={"project-flows-" + nodeId}>
    {own.map((flow) => <li key={flow.id} className="project-flows__item">
      <button type="button" className="project-flows__open" disabled={!onOpen} data-testid={"project-flow-open-" + flow.id} onClick={() => onOpen?.(flow.id)}>⇄ {flow.name}</button>
      {flow.from && <small className="project-flows__from">{flow.from}</small>}
      {flow.newer && <small className="project-flows__newer" data-testid={"project-flow-newer-" + flow.id}>{flow.newer}</small>}
    </li>)}
  </ul>;
}
