import {useEffect,useMemo,useState} from 'react';
import '@/project/maps/styles/map-view.css';
import '@/project/maps/project-map/styles/project-map.css';
import MapCanvas from '@/project/maps/project-map/components/MapCanvas';
import MapSidebar from '@/project/maps/project-map/components/MapSidebar';
import MapLegend from '@/project/maps/project-map/components/MapLegend';
import {communityTone,edgeLines,filterCommunities,fitView,isOverview,layoutCommunities,neighbors,type CommunityId,type Overview,type View} from '@/project/maps/project-map/logic/project-map-model';

const WIDTH=1000,HEIGHT=640;
type Props={project:string;revision:number;onMissing?:()=>void;onLoaded?:(value:Overview)=>void};

/** Lehká mapa kódu z /api/graphify/overview: rodič drží data, výběr, hledání a pohled a skládá dílky. */
export default function ProjectMap({project,revision,onMissing,onLoaded}:Props){
  const [value,setValue]=useState<Overview|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(true),[missing,setMissing]=useState(false);
  const [selected,setSelected]=useState<CommunityId|null>(null),[query,setQuery]=useState(''),[view,setView]=useState<View|null>(null);
  useEffect(()=>{
    let alive=true;setBusy(true);setError('');setMissing(false);
    void (async()=>{
      try{
        const response=await fetch('/api/graphify/overview?project='+encodeURIComponent(project),{cache:'no-store'});
        const next=await response.json();
        if(!alive)return;
        if(response.status===404){setMissing(true);onMissing?.();return}
        if(!response.ok)throw new Error(next.error??'Přehled grafu nelze načíst.');
        if(!isOverview(next,project))throw new Error('Chybí přehled vybraného projektu.');
        setValue(next);setView(null);onLoaded?.(next);
      }catch(e){if(alive)setError(e instanceof Error?e.message:'Přehled grafu nelze načíst.')}
      finally{if(alive)setBusy(false)}
    })();
    return()=>{alive=false};
  },[project,revision]);
  const model=useMemo(()=>{
    if(!value)return null;
    const layout=layoutCommunities(value.communities,value.edges,WIDTH,HEIGHT);
    const byId=new Map(value.communities.map((community,index)=>[String(community.id),{community,tone:communityTone(index)}]));
    return {layout,byId,lines:edgeLines(layout,value.edges),base:fitView(layout)};
  },[value]);
  const matches=useMemo(()=>value&&query.trim()?filterCommunities(value.communities,query):null,[value,query]);
  const matchIds=useMemo(()=>matches?new Set(matches.map(c=>String(c.id))):null,[matches]);
  if(busy&&!value)return <p role="status" className="map-view__status">Načítám mapu kódu…</p>;
  if(missing)return <p role="status" className="map-view__status">Graf zatím není; Graphify ho vytváří z projektu…</p>;
  if(error&&!value)return <p role="alert" className="map-view__error">{error}</p>;
  if(!value||!model)return null;
  const entry=selected==null?null:model.byId.get(String(selected))??null;
  const list=(matches??value.communities).map(community=>model.byId.get(String(community.id))!);
  return <div className="project-map">
    {error&&<p role="alert" className="map-view__error project-map__error">{error}</p>}
    <div className="project-map__stage">
      <MapCanvas layout={model.layout} lines={model.lines} byId={model.byId} selected={entry?selected:null} matches={matchIds}
        view={view??model.base} base={model.base} onSelect={setSelected} onView={setView}/>
      <div className="project-map__tools">
        <button type="button" onClick={()=>setView(null)}>Celý graf</button>
      </div>
      <MapLegend shownEdges={model.lines.length} totalEdges={value.edges.length} truncated={value.truncated}/>
    </div>
    <MapSidebar list={list} total={value.communities.length} query={query} selected={entry}
      links={entry?neighbors(entry.community.id,value.edges,value.communities):[]} onQuery={setQuery} onSelect={setSelected}/>
  </div>;
}
