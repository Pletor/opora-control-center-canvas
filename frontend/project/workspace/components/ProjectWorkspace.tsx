import ArchifyMap from '@/project/maps/components/ArchifyMap';
import GraphifyMap from '@/project/maps/components/GraphifyMap';
import ProjectLayout, {type ProjectMapKind} from '@/project/shell/components/ProjectLayout';
import type {WorkspaceSelection} from '@/shared/selection/logic/workspace-selection';

/** Hlavní stránka skládá hotové komponenty; kontext a dokumentový editor zůstávají v Editoru. */
export default function ProjectWorkspace({project,workspace,selection,onChange,mapKind}:{
  mapKind:ProjectMapKind;
  project:string;workspace:string;selection:WorkspaceSelection;onChange:(update:Partial<WorkspaceSelection>)=>void;
}){
  return <ProjectLayout key={JSON.stringify([project,workspace])} project={project} workspace={workspace}
    selected={selection.sourcePath} onSelect={path=>onChange({sourcePath:path})}>
    {mapKind==='graphify'?<GraphifyMap key={project} project={project}/>:<ArchifyMap key={project} project={project}/>}
  </ProjectLayout>;
}
