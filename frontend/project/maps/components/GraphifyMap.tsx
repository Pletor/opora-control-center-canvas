import {useEffect,useMemo,useRef,useState} from 'react';
import '@/project/maps/styles/map-view.css';
import MapUpdateMenu from '@/project/maps/components/MapUpdateMenu';
import ProjectMap from '@/project/maps/project-map/components/ProjectMap';
import type {Overview} from '@/project/maps/project-map/logic/project-map-model';

type Artifact={project:string;html:string;graphJson:string;sourceRoot:string;sourcePath:string;counts:{nodes:number;edges:number};version:string|null;scope:string;generatedAt:string|null;warnings?:string[];corpus?:{codeFiles:number}};
// Sdílení probíhajícího požadavku zabrání dvojímu startu při React StrictMode/remountu.
const pending=new Map<string,Promise<Artifact>>();
function requestGraph(project:string,rebuild=false):Promise<Artifact>{
  const running=pending.get(project);if(running)return running;
  const request=(async()=>{
    const query='?project='+encodeURIComponent(project);
    let response=rebuild?null:await fetch('/api/graphify/artifact'+query,{cache:'no-store'});
    if(!response||response.status===404)response=await fetch('/api/graphify/generate'+query,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const value=await response.json();
    if(!response.ok)throw new Error(value.error??'Graphify není dostupný.');
    if(value.project!==project||typeof value.html!=='string'||typeof value.graphJson!=='string')throw new Error('Chybí výstup vybraného projektu.');
    return value as Artifact;
  })();
  pending.set(project,request);
  void request.finally(()=>{if(pending.get(project)===request)pending.delete(project)}).catch(()=>{});
  return request;
}
function download(value:string,name:string){
  const url=URL.createObjectURL(new Blob([value],{type:name.endsWith('.html')?'text/html;charset=utf-8':'application/json'}));
  const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
const policy="default-src 'none'; script-src 'unsafe-inline' https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'";

/** Výchozí pohled je lehká mapa oblastí; původní Graphify HTML (~MB) se stahuje až na vyžádání. Ruční uzly Editoru se nemění. */
export default function GraphifyMap({project}:{project:string}){
  const [value,setValue]=useState<Artifact|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [mode,setMode]=useState<'map'|'html'>('map'),[revision,setRevision]=useState(0),[summary,setSummary]=useState<Overview|null>(null);
  const alive=useRef(false),sequence=useRef(0),root=useRef<HTMLElement>(null),autoBuilt=useRef(false);
  async function load(rebuild=false):Promise<Artifact|null>{
    const current=++sequence.current;setBusy(true);setError('');
    try{const next=await requestGraph(project,rebuild);if(alive.current&&sequence.current===current)setValue(next);return next}
    catch(e){if(alive.current&&sequence.current===current)setError(e instanceof Error?e.message:'Graf nelze načíst.');return null}
    finally{if(alive.current&&sequence.current===current)setBusy(false)}
  }
  // Přestavba nebo obnova po mergi: mapa si přehled načte znovu, HTML jen když už bylo otevřené.
  async function update(){if(await load(true))setRevision(r=>r+1)}
  async function reload(){setRevision(r=>r+1);if(value||mode==='html')await load()}
  async function save(kind:'html'|'json'){const artifact=value??await load();if(artifact)download(kind==='html'?artifact.html:artifact.graphJson,kind==='html'?'graph.html':'graph.json')}
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;sequence.current++}},[project]);
  // CSP a sandbox platí jen pro vložený náhled; uložené a stažené HTML jsou beze změny.
  const preview=useMemo(()=>value&&mode==='html'?'<meta http-equiv="Content-Security-Policy" content="'+policy+'">'+value.html:'',[value,mode]);
  const counts=summary?.counts??value?.counts;
  return <section className="map-view" ref={root} aria-label="Graphify hlavního projektu">
    <div className="map-view__toolbar"><strong>Mapa kódu · Graphify</strong>
      <MapUpdateMenu key={project} project={project} tool="graphify" busy={busy} onUpdate={update} onReload={reload}/>
      <button type="button" aria-pressed={mode==='html'} disabled={busy&&mode==='map'} onClick={()=>{if(mode==='html'){setMode('map');return}setMode('html');if(!value)void load()}}>{mode==='html'?'Zpět na mapu kódu':'Původní Graphify HTML'}</button>
      <button type="button" disabled={busy} onClick={()=>void save('html')}>Stáhnout HTML</button>
      <button type="button" disabled={busy} onClick={()=>void save('json')}>Stáhnout JSON</button>
      <button type="button" onClick={()=>{if(document.fullscreenElement)void document.exitFullscreen().catch(()=>{});else void root.current?.requestFullscreen().catch(()=>setError('Prohlížeč nepovolil celou obrazovku.'))}}>Celá obrazovka</button>
    </div>
    <div className="map-view__caption"><span>{counts?`${counts.nodes} uzlů · ${counts.edges} vztahů${summary?` · ${summary.counts.communities} oblastí`:''}`:'Graphify · analýza otevřeného projektu'}</span><span>Lokální kód · bez placeného modelu</span></div>
    {busy&&<p role="status" className="map-view__status">Načítám graf; pokud chybí, Graphify jej vytváří z projektu…</p>}
    {error&&<p role="alert" className="map-view__error">{error}</p>}
    {mode==='map'&&<ProjectMap key={project} project={project} revision={revision} onLoaded={setSummary} onMissing={()=>{if(autoBuilt.current)return;autoBuilt.current=true;void update()}}/>}
    {mode==='html'&&value&&<div className="map-view__body"><iframe title="Graphify — graf projektu" sandbox="allow-scripts allow-downloads" srcDoc={preview} referrerPolicy="no-referrer"/></div>}
    {(value||summary)&&<details className="map-view__receipt"><summary>Původní Graphify · {value?.version??summary?.version??'externí výstup'} · zdroj a rozsah</summary>
        {value&&<><p>Hlavní projekt: <code>{value.sourceRoot}</code></p><p>Výstup: <code>{value.sourcePath}</code></p><p>{value.scope}</p></>}
        <p>Mapa kódu shrnuje uzly Graphify do oblastí podle společné složky; podrobný graf otevře tlačítko „Původní Graphify HTML“. Dokumenty a média se v tomto režimu neanalyzují. Automatická aktualizace po mergi do main se nastavuje v menu; rozepsané změny ve worktrees ji nespouštějí.</p>
        <p>Vytvořeno: {value?.generatedAt??summary?.generatedAt??'čas generování nedoložen'}. Knihovnu pro původní HTML načítá vložená stránka z unpkg.com.</p>
        {value?.corpus&&<p>Analyzováno: {value.corpus.codeFiles} zdrojových souborů.</p>}
        {value?.warnings?.map((warning,index)=><p key={index}>Upozornění původního Graphify: {warning}</p>)}
      </details>}
  </section>;
}
