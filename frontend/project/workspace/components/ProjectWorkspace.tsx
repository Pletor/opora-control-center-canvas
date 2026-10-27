import GraphifyMap from '@/project/maps/components/GraphifyMap';
import ProjectLayout, {type ProjectMapKind} from '@/project/shell/components/ProjectLayout';
import type {WorkspaceSelection} from '@/shared/selection/logic/workspace-selection';
import ArchitectureEditor, {type ArchitectureLiveProps} from '@/project/architecture-editor/components/ArchitectureEditor';
import Studio from '@/project/studio/components/Studio';

/** Hlavní stránka skládá hotové komponenty; kontext a dokumentový editor zůstávají v Editoru. */
export default function ProjectWorkspace({project,workspace,selection,onChange,mapKind,projectName,onGraphChanged,onOpenEditor,onOpenArchitecture,architectureLive}:{
  projectName?:string;
  mapKind:ProjectMapKind;
  project:string;workspace:string;selection:WorkspaceSelection;onChange:(update:Partial<WorkspaceSelection>)=>void;
  onGraphChanged:()=>void;
  onOpenEditor:(id:string)=>void;
  /** Studio: „Otevřít v Editoru stránky“ přepne na Architekturu projektu s parametry editoru (vyřizuje App). */
  onOpenArchitecture:(params:Record<string,string>)=>void;
  /** Živý stav domén: schopnost projektu a akce (přepnout worktree, nová relace, nový worktree), které vyřizuje App. */
  architectureLive:ArchitectureLiveProps;
}){
  // Studio jen čte; worktree mění data, proto je klíčované projektem i prostorem.
  if (mapKind === 'studio') return <Studio key={JSON.stringify([project,workspace])} project={project} workspace={workspace} worktreeLive={architectureLive.worktreeLive} onOpenArchitecture={onOpenArchitecture}/>;
  // Editor architektury se klíčuje jen projektem: přepnutí worktree nechá otevřenou doménu i stránku a jen znovu načte obsah (docs/domeny-a-worktree.md §10).
  if (mapKind === 'architecture') return <ArchitectureEditor key={JSON.stringify([project])} project={project} workspace={workspace} projectName={projectName} onGraphChanged={onGraphChanged} onOpenEditor={onOpenEditor} live={architectureLive}/>;
  return <ProjectLayout key={JSON.stringify([project,workspace])} project={project} workspace={workspace}
    selected={selection.sourcePath} onSelect={path=>onChange({sourcePath:path})}>
    <GraphifyMap key={project} project={project}/>
  </ProjectLayout>;
}
