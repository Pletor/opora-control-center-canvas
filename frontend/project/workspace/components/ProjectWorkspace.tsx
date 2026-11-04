import type {ProjectMapKind} from '@/project/shell/logic/project-view';
import ArchitectureEditor, {type ArchitectureLiveProps} from '@/project/architecture-editor/components/ArchitectureEditor';
import Studio from '@/project/studio/components/Studio';
import IntentCanvas from '@/project/intent-canvas/components/IntentCanvas';
import SiteAdmin from '@/project/site-admin/components/SiteAdmin';
import LibraryCanvas from '@/project/library-canvas/components/LibraryCanvas';
import type {Project} from '@/shared/types/logic/types';

/** Hlavní stránka skládá hotové komponenty; kontext a dokumentový editor zůstávají v Editoru. */
export default function ProjectWorkspace({project,workspace,mapKind,intentPage,onCloseIntent,onCloseSite,libraryFlow,projects=[],onOpenLibraryFlow,projectName,onGraphChanged,onOpenEditor,onOpenArchitecture,architectureLive,onOpenAssistant}:{
  /** Otevře panel Asistent (kanál k srdci), třeba když srdce u zadání z plátna toku mlčí. */
  onOpenAssistant?:()=>void;
  projectName?:string;
  mapKind:ProjectMapKind;
  /** Stránka plátna záměru (`page` v adrese); bez ní se záměr neotevře. */
  intentPage?:string;
  /** Zpět ze záměru do Architektury projektu; rozsah editoru (doména, stránka) zůstal v adrese. */
  onCloseIntent?:()=>void;
  /** Zpět ze Správy webu (`projectView=site`) do Architektury projektu. */
  onCloseSite?:()=>void;
  /** Plátno toku v knihovně (`flow` v adrese) a projekty pro „Převzít do projektu“; zpět jde stejně jako ze Správy webu. */
  libraryFlow?:string;
  projects?:Project[];
  onOpenLibraryFlow?:(id:string)=>void;
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
  // Správa webu: jeden dokument na projekt (design systém a nastavení webu), sdílený všemi doménami.
  // Plátno toku v knihovně: globální (napříč projekty), otevřené z panelu Komponenty nebo od domény či stránky.
  if (mapKind === 'library' && libraryFlow) return <LibraryCanvas key={libraryFlow} flowId={libraryFlow} project={project} workspace={workspace} onOpenAssistant={onOpenAssistant} projects={projects} onOpenFlow={(id)=>onOpenLibraryFlow?.(id)} onBack={()=>onCloseSite?.()}/>;
  if (mapKind === 'site') return <SiteAdmin key={project} project={project} onBack={()=>onCloseSite?.()}/>;
  // Editor architektury se klíčuje jen projektem: přepnutí worktree nechá otevřenou doménu i stránku a jen znovu načte obsah (docs/domeny-a-worktree.md §10).
  return <ArchitectureEditor key={JSON.stringify([project])} project={project} workspace={workspace} projectName={projectName} onGraphChanged={onGraphChanged} onOpenEditor={onOpenEditor} live={architectureLive}/>;
}
