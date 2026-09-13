import {useEffect,useMemo,useRef,useState} from 'react';
import '@/project/maps/styles/archify-map.css';
import MapUpdateMenu from '@/project/maps/components/MapUpdateMenu';

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

/** Výhradně původní Graphify HTML. Ruční uzly Editoru se nemění. */
export default function GraphifyMap({project}:{project:string}){
  const [value,setValue]=useState<Artifact|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(true);
  const alive=useRef(false),sequence=useRef(0),root=useRef<HTMLElement>(null);
  async function load(rebuild=false){
    const current=++sequence.current;setBusy(true);setError('');
    try{const next=await requestGraph(project,rebuild);if(alive.current&&sequence.current===current)setValue(next)}
    catch(e){if(alive.current&&sequence.current===current)setError(e instanceof Error?e.message:'Graf nelze načíst.')}
    finally{if(alive.current&&sequence.current===current)setBusy(false)}
  }
  useEffect(()=>{alive.current=true;void load();return()=>{alive.current=false;sequence.current++}},[project]);
  // CSP a sandbox platí jen pro vložený náhled; uložené a stažené HTML jsou beze změny.
  const preview=useMemo(()=>value?'<meta http-equiv="Content-Security-Policy" content="'+policy+'">'+value.html:'',[value]);
  return <section className="archify-workspace" ref={root} aria-label="Graphify hlavního projektu">
    <div className="archify-toolbar"><strong>Graphify · graf projektu</strong>
      <MapUpdateMenu key={project} project={project} tool="graphify" busy={busy} onUpdate={()=>load(true)} onReload={()=>load()}/>
      <button type="button" disabled={!value} onClick={()=>value&&download(value.html,'graph.html')}>Stáhnout HTML</button>
      <button type="button" disabled={!value} onClick={()=>value&&download(value.graphJson,'graph.json')}>Stáhnout JSON</button>
      <button type="button" onClick={()=>{if(document.fullscreenElement)void document.exitFullscreen().catch(()=>{});else void root.current?.requestFullscreen().catch(()=>setError('Prohlížeč nepovolil celou obrazovku.'))}}>Celá obrazovka</button>
    </div>
    <div className="archify-caption"><span>{value?`${value.counts.nodes} uzlů · ${value.counts.edges} vztahů`:'Původní Graphify · analýza otevřeného projektu'}</span><span>Lokální kód · bez placeného modelu</span></div>
    {busy&&<p role="status" className="archify-status">Načítám graf; pokud chybí, Graphify jej vytváří z projektu…</p>}
    {error&&<p role="alert" className="archify-error">{error}</p>}
    {value&&<><div className="archify-body"><iframe title="Graphify — graf projektu" sandbox="allow-scripts allow-downloads" srcDoc={preview} referrerPolicy="no-referrer"/></div>
      <details className="archify-receipt"><summary>Původní Graphify · {value.version??'externí výstup'} · zdroj a rozsah</summary>
        <p>Hlavní projekt: <code>{value.sourceRoot}</code></p><p>Výstup: <code>{value.sourcePath}</code></p>
        <p>{value.scope} Dokumenty a média se v tomto režimu neanalyzují. Automatická aktualizace po mergi do main se nastavuje v menu; rozepsané změny ve worktrees ji nespouštějí.</p>
        <p>Vytvořeno: {value.generatedAt??'čas generování nedoložen'}. Knihovnu pro zobrazení načítá původní HTML z unpkg.com.</p>
        {value.corpus&&<p>Analyzováno: {value.corpus.codeFiles} zdrojových souborů.</p>}
        {value.warnings?.map((warning,index)=><p key={index}>Upozornění původního Graphify: {warning}</p>)}
      </details></>}
  </section>;
}
