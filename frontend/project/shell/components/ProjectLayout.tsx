import {useState, type ReactNode} from 'react';
import SourceExplorer from '@/project/source-tree/components/SourceExplorer';
import '@/project/shell/styles/project-layout.css';

// Jediná definice filtrů a rozložení hlavního projektu. Štítky třídí cesty, ne obsah souborů.
const filters = [
  {id:'all',label:'Štítky',hint:'Všechny cesty',match:(_path:string)=>true},
  {id:'backend',label:'Backend',hint:'backend, api, server a Python soubory',match:(p:string)=>/(^|\/)(backend|api|server)(\/|$)|\.py$/i.test(p)},
  {id:'frontend',label:'Frontend',hint:'src, frontend, client, public a webové vstupy',match:(p:string)=>/(^|\/)(src|frontend|client|public)(\/|$)|\.(tsx?|jsx?|html|css)$/i.test(p)},
  {id:'database',label:'Databáze',hint:'Databázové a migrační cesty; rozbalte zdrojové složky',match:(p:string)=>/(database|sqlite|migration|alembic|(^|[\/_.-])db([\/_.-]|$))/i.test(p)||/^(backend|src)$/.test(p)},
  {id:'cache',label:'Cache',hint:'Cache, závislosti a generované výstupy',match:(p:string)=>/(^|\/)(\.?cache|__pycache__|node_modules|dist|build|\.data|\.pytest_cache)(\/|$)/i.test(p)},
  {id:'settings',label:'Nastavení',hint:'Konfigurační cesty a manifesty',match:(p:string)=>/(config|settings|package|pyproject|tsconfig|\.gitignore|\.gitattributes|\.env\.example)/i.test(p)||/^(backend|src)$/.test(p)},
] as const;

/** Sdílený přepínač mapy v existující hlavičce; žádná další kopie horní lišty. */
export type ProjectMapKind = 'archify' | 'graphify';
export function ProjectMapNavigation({value,onChange}:{value:ProjectMapKind;onChange:(value:ProjectMapKind)=>void}){
  return <div className="project-map-navigation" role="group" aria-label="Výstup mapy">
    <button type="button" aria-pressed={value==='archify'} onClick={()=>onChange('archify')}>Archify</button>
    <button type="button" aria-pressed={value==='graphify'} title="Původní Graphify: načíst nebo vytvořit graf hlavního projektu" onClick={()=>onChange('graphify')}>Graphify-out</button>
  </div>;
}

/** Geometrie, strom, hledání a filtry jsou společné pro libovolný obsah hlavní plochy. */
export default function ProjectLayout({project,workspace,selected,onSelect,children}:{
  project:string;workspace:string;selected:string;onSelect:(path:string)=>void;children:ReactNode;
}){
  const [search,setSearch]=useState('');
  const [filter,setFilter]=useState<(typeof filters)[number]['id']>('all');
  const [visibility,setVisibility]=useState<'all'|'working'>('all');
  const active=filters.find(item=>item.id===filter)!;
  return <section className="project-layout" aria-label="Hlavní projekt">
    <div className="project-layout-sidebar">
      <div className="project-tree-search" role="search">
        <label htmlFor="project-tree-query">Strom</label>
        <input id="project-tree-query" aria-label="Hledat v načteném stromu" placeholder="Hledat v načteném stromu…" value={search} onChange={event=>setSearch(event.target.value)}/>
        <select aria-label="Filtr viditelnosti stromu" value={visibility} onChange={event=>setVisibility(event.target.value as 'all'|'working')}>
          <option value="all">Filtr: vše</option><option value="working">Pracovní</option>
        </select>
      </div>
      <div className="project-tree-filters" role="group" aria-label="Štítky cest">
        {filters.map(item=><button key={item.id} type="button" aria-pressed={filter===item.id} title={item.hint}
          onClick={()=>setFilter(item.id===filter?'all':item.id)}>{item.label}</button>)}
      </div>
      <SourceExplorer key={JSON.stringify([project,workspace])} project={project} workspace={workspace}
        selected={selected} onSelect={onSelect} search={search} refresh={0} compact rootLabel="" visibility={visibility} filterPath={active.match}/>
    </div>
    <main className="project-layout-content">{children}</main>
  </section>;
}
