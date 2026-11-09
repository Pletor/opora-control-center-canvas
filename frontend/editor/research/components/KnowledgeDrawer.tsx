import type { WorkScope } from "@/shared/work-scope/logic/work-scope";
import type { WorkspaceMode } from "@/shared/types/logic/workspace-mode";
import KnowledgePanel from "./KnowledgePanel";
import "../styles/knowledge-drawer.css";
export const knowledgeAvailable = (mode: WorkspaceMode) => mode !== "map";
export default function KnowledgeDrawer({ open, mode, scope, scopeLabel, workspace, projects, onClose }: {
 open: boolean; mode: WorkspaceMode; scope: WorkScope; workspace: string;
 scopeLabel?: string;
 projects: {id:string;name:string}[]; onClose:()=>void;
}) {
 if (!open || !knowledgeAvailable(mode)) return null;
 return <aside className="knowledge-drawer" aria-label="Sdílené podklady kontextu" data-work-scope={scope.nodeId ?? ""}>
  <header><strong>{scopeLabel ?? "Projekt"}</strong><button type="button" onClick={onClose}>{"Zav\u0159\u00edt podklady"}</button></header>
  <KnowledgePanel key={JSON.stringify([scope.projectId,workspace,scope.nodeId])} project={scope.projectId} workspace={workspace} nodeId={scope.nodeId} projects={projects} />
 </aside>;
}
