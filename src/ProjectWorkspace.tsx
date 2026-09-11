import ArchifyMap from './ArchifyMap';
import ProjectLayout from './ProjectLayout';
import type {WorkspaceSelection} from './workspace-selection';

/** Hlavní stránka skládá hotové komponenty; kontext a dokumentový editor zůstávají v Editoru. */
export default function ProjectWorkspace({project,workspace,selection,onChange}:{
  project:string;workspace:string;selection:WorkspaceSelection;onChange:(update:Partial<WorkspaceSelection>)=>void;
}){
  return <ProjectLayout key={JSON.stringify([project,workspace])} project={project} workspace={workspace}
    selected={selection.sourcePath} onSelect={path=>onChange({sourcePath:path})}>
    <ArchifyMap key={project} project={project}/>
  </ProjectLayout>;
}
