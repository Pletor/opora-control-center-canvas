import { useRef, useState, type ReactNode } from "react";
import { createElementFlow } from "@/project/library-canvas/logic/library-api";
import { logicFlowTitle } from "../logic/project-flows";
import { ProjectFlowsContext } from "../logic/project-flows-context";
import { useProjectFlows } from "../logic/use-project-flows";
import LogicFlowDialog from "./LogicFlowDialog";

type Props = { project: string; workspace: string; digest: string | undefined; onOpen?: (flowId: string) => void; children: ReactNode };

/** Plátna toku projektu pro editor architektury: převzatá plátna u domén a stránek a plátno logiky prvku plátna 2.
 * „Nastavit logiku“ otevře existující plátno prvku, jinak jedno okno Prázdné plátno / Z knihovny…, které plátno
 * založí a rovnou otevře. Dvojklik na prvek (`onOpenLogic`) okno přeskočí: chybějící plátno založí prázdné a otevře; když
 * založení selže, ukáže totéž okno s důvodem. Plátno toku není graf architektury, proto ho zakládá tento rodič, ne editor. */
export default function ProjectFlowsProvider({ project, workspace, digest, onOpen, children }: Props) {
  const flows = useProjectFlows(project, digest);
  const [setup, setSetup] = useState<{ id: string; name: string; error?: string } | null>(null);
  const opening = useRef(false);
  const onSetLogic = onOpen && ((node: { id: string; name: string }) => {
    const existing = flows.get(node.id)?.[0];
    if (existing) onOpen(existing.id); else setSetup(node);
  });
  const onOpenLogic = onOpen && ((node: { id: string; name: string }) => {
    const existing = flows.get(node.id)?.[0];
    if (existing) return onOpen(existing.id);
    if (opening.current) return; // druhý dvojklik během zakládání nesmí poslat druhý požadavek
    opening.current = true;
    createElementFlow(project, workspace, node.id, logicFlowTitle(node.name))
      .then((flow) => onOpen(flow.id), (cause) => setSetup({ ...node, error: cause instanceof Error ? cause.message : String(cause) }))
      .finally(() => { opening.current = false; });
  });
  return <ProjectFlowsContext.Provider value={{ flows, onOpen, onSetLogic, onOpenLogic }}>
    {children}
    {setup && onOpen && <LogicFlowDialog project={project} workspace={workspace} node={setup} error={setup.error} onClose={() => setSetup(null)} onCreated={(id) => { setSetup(null); onOpen(id); }}/>}
  </ProjectFlowsContext.Provider>;
}
