import ArchifyMap from '@/project/maps/components/ArchifyMap';
import GraphifyMap from '@/project/maps/components/GraphifyMap';
import ProjectLayout, {type ProjectMapKind} from '@/project/shell/components/ProjectLayout';
import type {WorkspaceSelection} from '@/shared/selection/logic/workspace-selection';
import ProductTree, {type ProductTreeProps} from '@/project/product-tree/components/ProductTree';
import ArchitectureEditor from '@/project/architecture-editor/components/ArchitectureEditor';

/** Hlavní stránka skládá hotové komponenty; kontext a dokumentový editor zůstávají v Editoru. */
export default function ProjectWorkspace({project,workspace,selection,onChange,mapKind,projectName,product,onGraphChanged,onOpenEditor}:{
  projectName?:string;
  mapKind:ProjectMapKind;
  project:string;workspace:string;selection:WorkspaceSelection;onChange:(update:Partial<WorkspaceSelection>)=>void;
  product:ProductTreeProps;
  onGraphChanged:()=>void;
  onOpenEditor:(id:string)=>void;
}){
  if (mapKind === 'architecture') return <ArchitectureEditor key={JSON.stringify([project,workspace])} project={project} workspace={workspace} projectName={projectName} onGraphChanged={onGraphChanged} onOpenEditor={onOpenEditor}/>;
  return <ProjectLayout key={JSON.stringify([project,workspace])} project={project} workspace={workspace}
    selected={selection.sourcePath} onSelect={path=>onChange({sourcePath:path})} productTree={<ProductTree {...product}/> }>
    {mapKind==='graphify'?<GraphifyMap key={project} project={project}/>:<ArchifyMap key={project} project={project}/>}
  </ProjectLayout>;
}
