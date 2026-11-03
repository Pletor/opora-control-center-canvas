import '@/project/shell/styles/project-map-navigation.css';
import type {ProjectMapKind} from '../logic/project-view';
export type {ProjectMapKind} from '../logic/project-view';

/** Přepínač pohledu Projektu v existující hlavičce: jen architektura projektu. Srdce má vlastní obrazovku
 * (`project/heart-screen/`, vstup ze stránky projektu), záměr stránky se otevírá z karty stránky. */
export function ProjectMapNavigation({value,onChange}:{value:ProjectMapKind;onChange:(value:ProjectMapKind)=>void}){
  return <div className="project-map-navigation" role="group" aria-label="Výstup mapy">
    <button type="button" aria-pressed={value==='architecture'} data-testid="project-view-architecture" onClick={()=>onChange('architecture')}>Architektura projektu</button>
    <button type="button" aria-pressed={value==='studio'} data-testid="project-view-studio" title="Studio: co stojí a jak teče data, od projektu po komponentu" onClick={()=>onChange('studio')}>Studio</button>
  </div>;
}
