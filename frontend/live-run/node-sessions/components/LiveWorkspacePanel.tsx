import {NodeSessionsPanel} from '@/live-run/node-sessions/components/NodeSessionsPanel';
import '@/live-run/node-sessions/styles/live-workspace.css';

export function LiveWorkspacePanel({project,workspace,nodeId}:{project:string;workspace:string;nodeId?:string}){
  return <section className="live-workspace-root" aria-label="Live workspace">
    <NodeSessionsPanel key={JSON.stringify([project,workspace,nodeId])} project={project} workspace={workspace} nodeId={nodeId}/>
  </section>;
}
