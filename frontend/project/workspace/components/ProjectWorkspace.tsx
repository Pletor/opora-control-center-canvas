import type {ProjectMapKind} from '@/project/shell/logic/project-view';
import ArchitectureEditor, {type ArchitectureLiveProps} from '@/project/architecture-editor/components/ArchitectureEditor';
import Studio from '@/project/studio/components/Studio';
import IntentCanvas from '@/project/intent-canvas/components/IntentCanvas';

/** Hlavní stránka skládá hotové komponenty; kontext a dokumentový editor zůstávají v Editoru. */
export default function ProjectWorkspace({project,workspace,mapKind,intentPage,onCloseIntent,projectName,onGraphChanged,onOpenEditor,onOpenArchitecture,architectureLive}:{
  projectName?:string;
  mapKind:ProjectMapKind;
  /** Stránka plátna záměru (`page` v adrese); bez ní se záměr neotevře. */
  intentPage?:string;
  /** Zpět ze záměru do Architektury projektu; rozsah editoru (doména, stránka) zůstal v adrese. */
  onCloseIntent?:()=>void;
  project:string;workspace:string;
  onGraphChanged:()=>void;
  onOpenEditor:(id:string)=>void;
  /** Studio: „Otevřít v Editoru stránky“ přepne na Architekturu projektu s parametry editoru (vyřizuje App). */
  onOpenArchitecture:(params:Record<string,string>)=>void;
  /** Živý stav domén: schopnost projektu a akce (přepnout worktree, nová relace, nový worktree), které vyřizuje App. */
  architectureLive:ArchitectureLiveProps;
}){
  // Studio jen čte; worktree mění data, proto je klíčované projektem i prostorem.
  if (mapKind === 'studio') return <Studio key={JSON.stringify([project,workspace])} project={project} workspace={workspace} worktreeLive={architectureLive.worktreeLive} onOpenArchitecture={onOpenArchitecture}/>;
  // Záměr stránky (plátno 2) patří jedné stránce projektu; zpět vede do Architektury s jejím zachovaným rozsahem.
  if (mapKind === 'intent' && intentPage) return <IntentCanvas key={project+':'+intentPage} project={project} page={intentPage} onBack={()=>onCloseIntent?.()}/>;
  // Editor architektury se klíčuje jen projektem: přepnutí worktree nechá otevřenou doménu i stránku a jen znovu načte obsah (docs/domeny-a-worktree.md §10).
  return <ArchitectureEditor key={JSON.stringify([project])} project={project} workspace={workspace} projectName={projectName} onGraphChanged={onGraphChanged} onOpenEditor={onOpenEditor} live={architectureLive}/>;
}
