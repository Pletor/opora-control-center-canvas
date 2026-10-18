import type {Community,CommunityId,Neighbor} from '@/project/maps/project-map/logic/project-map-model';

type Props={
  list:{community:Community;tone:number}[];total:number;query:string;selected:{community:Community;tone:number}|null;
  links:Neighbor[];onQuery:(query:string)=>void;onSelect:(id:CommunityId|null)=>void;
};
const kindNames:Record<string,string>={code:'kód',doc:'dokumenty',rationale:'zdůvodnění',concept:'pojmy',document:'dokumenty',image:'obrázky'};

/** Boční panel: hledání, seznam oblastí podle velikosti a detail vybrané oblasti s jejími sousedy. */
export default function MapSidebar({list,total,query,selected,links,onQuery,onSelect}:Props){
  return <aside className="project-map-sidebar" aria-label="Oblasti kódu">
    <input className="project-map-sidebar__search" type="search" value={query} placeholder="Hledat složku, soubor, symbol…"
      aria-label="Hledat v oblastech" onChange={event=>onQuery(event.target.value)}/>
    {selected&&<section className="project-map-sidebar__detail" aria-label="Vybraná oblast">
      <header className="project-map-sidebar__detail-head">
        <span className={'project-map-sidebar__swatch project-map-sidebar__swatch--tone-'+selected.tone}/>
        <strong className="project-map-sidebar__detail-name">{selected.community.name}</strong>
        <button type="button" className="project-map-sidebar__close" onClick={()=>onSelect(null)} aria-label="Zrušit výběr">×</button>
      </header>
      <p className="project-map-sidebar__meta">{selected.community.size} uzlů · {selected.community.files} souborů · {Object.entries(selected.community.kinds).map(([kind,count])=>`${kindNames[kind]??kind} ${count}`).join(', ')}{selected.community.rawName?` · Graphify: ${selected.community.rawName}`:''}</p>
      <h4 className="project-map-sidebar__heading">Nejpropojenější</h4>
      <ol className="project-map-sidebar__top">
        {selected.community.top.map(node=><li key={node.id} className="project-map-sidebar__top-item">
          <span className="project-map-sidebar__top-label">{node.label}</span>
          <span className="project-map-sidebar__degree" title="Počet vazeb">{node.degree}</span>
          {node.source_file&&<code className="project-map-sidebar__path">{node.source_file}</code>}
        </li>)}
      </ol>
      <h4 className="project-map-sidebar__heading">Sousední oblasti</h4>
      {links.length?<ul className="project-map-sidebar__links">
        {links.slice(0,12).map(link=><li key={String(link.id)}><button type="button" className="project-map-sidebar__link" onClick={()=>onSelect(link.id)}>
          <span className="project-map-sidebar__link-name">{link.name}</span><span className="project-map-sidebar__weight">{link.weight.toLocaleString('cs-CZ',{maximumFractionDigits:1})}</span>
        </button></li>)}
      </ul>:<p className="project-map-sidebar__meta">Žádné vazby na jiné oblasti.</p>}
    </section>}
    <p className="project-map-sidebar__count">{list.length===total?`${total} oblastí`:`${list.length} z ${total} oblastí`}</p>
    <ul className="project-map-sidebar__list">
      {list.map(({community,tone})=><li key={String(community.id)}>
        <button type="button" aria-pressed={selected?.community.id===community.id}
          className={'project-map-sidebar__item'+(selected?.community.id===community.id?' project-map-sidebar__item--selected':'')} onClick={()=>onSelect(community.id)}>
          <span className={'project-map-sidebar__swatch project-map-sidebar__swatch--tone-'+tone}/>
          <span className="project-map-sidebar__item-name">{community.name}</span>
          <span className="project-map-sidebar__item-size">{community.size}</span>
          {community.paths.length>0&&<span className="project-map-sidebar__item-paths">{community.paths.join(' · ')}</span>}
        </button>
      </li>)}
    </ul>
  </aside>;
}
