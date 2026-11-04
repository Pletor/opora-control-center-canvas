// Kam převzít plátno toku v projektu (kontrakt knihovny §1 „opora:project-flow:<nodeId>“, rozhodnutí člověka:
// převzaté plátno je vidět u domény i u stránky). Nabídka = domény (jako u přiřazení worktree) a pod nimi stránky,
// čtené z pohledu projektu (`/api/view`). Prostor pohledu určuje druh projektu přes `project-capabilities`.
import { api, type Graph, type Project, type View } from "@/shared/types/logic/types";
import { isLocalKind } from "@/shared/project-capabilities/logic/project-capabilities";
import { domainChoices } from "@/project/architecture-editor/landing/logic/domain-choices";

export type AdoptTarget = { id: string; label: string };

export function adoptTargets(graph: Graph): AdoptTarget[] {
  const domains = domainChoices(graph).map((choice) => ({ id: choice.id, label: `Doména · ${choice.label}` }));
  const pages = graph.nodes.flatMap((node) => node.site?.kind === "page" ? [{ id: node.id, label: `Stránka · ${node.name}${node.site.path ? ` (${node.site.path})` : ""}` }] : []);
  return [...domains, ...pages];
}

/** Pracovní prostor pro čtení cizího projektu: lokální projekt jen návrh, git projekt main. */
export const viewWorkspace = (project: Project | undefined) => isLocalKind(project?.sourceKind) || project?.id === "draft" ? "draft" : "main";

export const loadAdoptTargets = (project: Project) =>
  api<View>(`/api/view?${new URLSearchParams({ project: project.id, workspace: viewWorkspace(project) })}`).then((view) => adoptTargets(view.graph));
