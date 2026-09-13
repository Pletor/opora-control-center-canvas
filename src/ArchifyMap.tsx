import {useEffect, useMemo, useRef, useState} from 'react';
import '@/archify-map.css';
import MapUpdateMenu from '@/MapUpdateMenu';

type Artifact = {
  html:string; specificationJson:string; fileName:string; specificationName:string;
  sourceRoot:string; sourcePath:string; sourceRevision:string|null; freshness:string;
  artifact:{sha256:string;bytes:number}; specification:{sha256:string;bytes:number};
  validation:{compositionProfile:string;checksPassed:number;checkCount:number;warnings:number};
  browserEvidence:{status:string;coverage:unknown[]};
  counts:{components:number;connections:number;boundaries:number}; specificationDocument:string;
};
const policy="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src blob:; connect-src 'none'; base-uri 'none'; form-action 'none'";
function download(content:string,name:string,mime:string){
  const url=URL.createObjectURL(new Blob([content],{type:mime}));
  const a=document.createElement('a');a.href=url;a.download=name;a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}

/** Původní HTML bez převodu grafu; aktualizace se řídí sdíleným projektovým menu. */
export default function ArchifyMap({project}:{project:string}){
  const [value,setValue]=useState<Artifact|null>(null);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const request=useRef<AbortController|null>(null);
  const root=useRef<HTMLDivElement>(null);
  async function load(){
    request.current?.abort();
    const controller=new AbortController();request.current=controller;
    setValue(null);setError('');setBusy(true);
    try{
      const response=await fetch('/api/archify/artifact?project='+encodeURIComponent(project),{cache:'no-store',signal:controller.signal});
      const data=await response.json();
      if(!response.ok)throw new Error(data.error??'Mapu nelze načíst.');
      if(typeof data.html!=='string'||typeof data.specificationJson!=='string'||!data.artifact?.sha256)throw new Error('Chybí ověřený výstup Archify.');
      if(!controller.signal.aborted)setValue(data);
    }catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Mapu nelze načíst.');}
    finally{if(!controller.signal.aborted)setBusy(false);}
  }
  useEffect(()=>{void load();return()=>request.current?.abort();},[project]);
  // Izolace náhledu nemění uložené HTML ani přesné bajty stahovaného souboru.
  const preview=useMemo(()=>value?.html.replace(/<head(?:\s[^>]*)?>/i,match=>match+'<meta http-equiv="Content-Security-Policy" content="'+policy+'">')??'',[value]);
  return <section className="archify-workspace" ref={root} aria-label="Mapa hlavního projektu">
    <div className="archify-toolbar">
      <strong>Archify · mapa projektu</strong>
      <MapUpdateMenu key={project} project={project} tool="archify" busy={busy} onReload={load}/>
      <button type="button" disabled={!value} onClick={()=>value&&download(value.html,value.fileName,'text/html;charset=utf-8')}>Stáhnout HTML</button>
      <button type="button" disabled={!value} onClick={()=>value&&download(value.specificationJson,value.specificationName,'application/json')}>Stáhnout JSON</button>
      <button type="button" onClick={()=>{if(document.fullscreenElement)void document.exitFullscreen().catch(()=>{});else void root.current?.requestFullscreen().catch(()=>setError('Prohlížeč nepovolil celou obrazovku.'));}}>Celá obrazovka</button>
    </div>
    <div className="archify-caption"><span>{value?`${value.counts.components} komponent · ${value.counts.connections} vztahů · ${value.counts.boundaries} hranice`:'Uložený výstup původního skillu Archify'}</span><span>Náhled HTML · aktualizace přes Sonnet</span></div>
    {error&&<p className="archify-error" role="alert">{error}</p>}
    {busy&&<p className="archify-status" role="status">Načítám uložený diagram…</p>}
    {value?<>
      <div className="archify-body"><iframe title="Archify — mapa projektu" sandbox="allow-scripts allow-downloads" srcDoc={preview} referrerPolicy="no-referrer"/></div>
      <details className="archify-receipt"><summary>Původ a ověření · {value.validation.compositionProfile} · {value.freshness==='changed'?'projekt má novější revizi':'aktuálnost zdrojů neověřena'}</summary>
        <p>Hlavní projekt: <code>{value.sourceRoot}</code></p><p>Soubor: <code>{value.sourcePath}</code></p>
        <p>Mapa odpovídá doručovacímu potvrzení. Novou analýzu vytváří Sonnet s původním Archify po volbě „Aktualizovat teď“ nebo po změně main, pokud je automatika zapnutá. Samotné čtení uloženého HTML agenta nespouští.</p>
        <p>Revize uvedená autorem: <code>{value.sourceRevision??'neuvedena'}</code></p>
        <p>Validace: {value.validation.checksPassed}/{value.validation.checkCount}, upozornění: {value.validation.warnings}. Doložená kontrola prohlížeče: {value.browserEvidence.status}, záznamů: {value.browserEvidence.coverage.length}.</p>
        <p>HTML SHA-256: <code>{value.artifact.sha256}</code></p>
        <details><summary>Specifikace a omezení autora</summary><pre>{value.specificationDocument||'SPEC.md nebyl dodán.'}</pre></details>
      </details>
    </>:!busy&&<div className="archify-empty">Ve VS Code spusťte původní Archify nad hlavním projektem. HTML, JSON a deliver-receipt.json patří do <code>docs/architecture/archify/</code>. Poté použijte „Načíst ze souboru“.</div>}
  </section>;
}
