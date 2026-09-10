import {useEffect, useRef, useState} from 'react';
import {api} from '../types';
import {errorMessage, exportHandoff, fetchPlanningRuns} from './api';
import {useDesktopState} from './state-store';
import {ACTIVE_RUNS, downloadLiveText, fetchLiveRuns, handoffSession, planningSession, type LiveSession} from './live-sessions';
import {LiveTickets} from './LiveTickets';
import './live-workspace.css';

const tabs=['1 Události','2 Důkazy a výstup','3 Náklady a výkon','4 Paměť','5 Ovládání','6 Tickety','7 Kontext a osa'];
const stateFilters=[['all','Vše'],['active','Běží'],['completed','Dokončeno'],['failed','Problémy']] as const;
export function LiveWorkspacePanel({project,workspace,nodeId}:{project:string;workspace:string;nodeId?:string}) {
  const [planning,setPlanning]=useState<LiveSession[]>([]);
  const [handoffs,setHandoffs]=useState<LiveSession[]>([]);
  const [sourceErrors,setSourceErrors]=useState<Record<string,string>>({});
  const [loading,setLoading]=useState(true);
  const [refresh,setRefresh]=useState(0);
  const [search,setSearch]=useState('');
  const [filter,setFilter]=useState<string>('all');
  const [onlyNode,setOnlyNode]=useState(false);
  const [selectedKey,setSelectedKey]=useState('');
  const [tab,setTab]=useState(1);
  const [stopFor,setStopFor]=useState('');
  const [busy,setBusy]=useState(false);
  const [actionError,setActionError]=useState('');
  const [exactContext,setExactContext]=useState<unknown>(null);
  const actionGeneration=useRef(0);
  const readVersion=useRef(0);
  const [sourcePending,setSourcePending]=useState({planning:true,handoff:true});
  const {state,readOnly,loading:memoryLoading,error:memoryError,mutate,reload}=useDesktopState(project,workspace);

  // Každý scope má vlastní polling bez překryvu. Chyba jednoho zdroje nemaže druhý.
  useEffect(()=>{
    setPlanning([]);setHandoffs([]);setSourceErrors({});setLoading(true);setSelectedKey('');
    setStopFor('');setActionError('');setBusy(false);setExactContext(null);actionGeneration.current++;
    return()=>{actionGeneration.current++;};
  },[project,workspace]);
  useEffect(()=>{
    let alive=true;
    const timers=new Set<ReturnType<typeof setTimeout>>();
    const controllers=new Set<AbortController>();
    setLoading(true);
    setSourcePending({planning:true,handoff:true});
    const schedule=(kind:'planning'|'handoff')=>{
      const timer=setTimeout(()=>{timers.delete(timer);void load(kind);},4000);timers.add(timer);
    };
    const load=async(kind:'planning'|'handoff')=>{
      if(!alive)return;
      if(document.hidden){schedule(kind);return;}
      const version=readVersion.current;
      const controller=new AbortController();controllers.add(controller);
      const deadline=setTimeout(()=>controller.abort(),8000);
      try{
        const rows=await fetchLiveRuns(kind,project,workspace,controller.signal);
        if(!alive||version!==readVersion.current)return;
        (kind==='planning'?setPlanning:setHandoffs)(rows);
        setSourceErrors(errors=>{const next={...errors};delete next[kind];return next;});
      }catch(e){if(alive&&version===readVersion.current)setSourceErrors(errors=>({...errors,[kind]:controller.signal.aborted?'Zdroj neodpověděl do 8 s':errorMessage(e)}));}
      finally{
        clearTimeout(deadline);controllers.delete(controller);
        if(alive){setLoading(false);setSourcePending(p=>({...p,[kind]:false}));schedule(kind);}
      }
    };
    void load('planning');void load('handoff');
    return()=>{alive=false;timers.forEach(clearTimeout);controllers.forEach(c=>c.abort());};
  },[project,workspace,refresh]);

  const sessions=[...planning,...handoffs].sort((a,b)=>b.at.localeCompare(a.at));
  const selected=sessions.find(r=>r.key===selectedKey)||(!selectedKey?sessions[0]:undefined);
  const visible=sessions.filter(r=>{
    if(onlyNode&&nodeId&&r.nodeId!==nodeId)return false;
    if(filter==='active'&&!ACTIVE_RUNS.has(r.status))return false;
    if(filter==='completed'&&r.status!=='completed')return false;
    if(filter==='failed'&&!['failed','interrupted','cancelled'].includes(r.status))return false;
    const text=[r.id,r.title,r.status,r.output,r.nodeId,...r.events.map(e=>e.kind),...state.tickets.filter(t=>t.sessionId===r.id).map(t=>t.title)].join(' ').toLocaleLowerCase();
    return text.includes(search.toLocaleLowerCase());
  });
  useEffect(()=>{setStopFor('');setBusy(false);setActionError('');setExactContext(null);actionGeneration.current++;},[selected?.key]);
  const decisions=state.decisions.filter(d=>!selected?.nodeId||!d.nodeId||d.nodeId===selected.nodeId);
  const timeline=[...decisions.map(d=>({at:d.createdAt,kind:'Rozhodnutí',text:d.text})),
    ...(selected?.events||[]).filter(e=>e.observedAt).map(e=>({at:e.observedAt!,kind:e.kind,text:'Událost dokumentačního běhu'})),
    ...(selected?.at?[{at:selected.at,kind:'Stav zdroje',text:selected.label}]:[])]
    .sort((a,b)=>a.at.localeCompare(b.at));
  const canStop=!!selected&&ACTIVE_RUNS.has(selected.status)&&selected.status!=='stopping'&&workspace!=='main'&&!sourceErrors[selected.kind];

  async function readContext(){
    if(!selected?.handoff)return;
    const run=selected;const generation=actionGeneration.current;setActionError('');
    try{const value=await exportHandoff(run.id);
      if(value.id!==run.id||value.digest!==run.digest)throw new Error('Export neodpovídá vybranému běhu.');
      if(generation===actionGeneration.current)setExactContext(value);
    }catch(e){if(generation===actionGeneration.current)setActionError(errorMessage(e));}
  }
  async function confirmStop(){
    if(!selected||stopFor!==selected.key||!canStop||busy)return;
    const run=selected;const generation=actionGeneration.current;setBusy(true);setActionError('');
    readVersion.current++;
    try{
      let value:unknown;
      if(run.kind==='planning'){
        await api('/api/llm/stop',{project,runId:run.id,confirmed:true});
        const readback=await fetchPlanningRuns(project);
        value=readback.runs.find(r=>r.id===run.id&&r.workspace===workspace&&r.project_id===project);
        if(!value)throw new Error('Stav zastavovaného běhu nebyl nalezen.');
      }else{
        const endpoint=`/api/task-handoffs/${encodeURIComponent(run.id)}`;
        await api(`${endpoint}/stop`,{confirmed:true});
        value=await api<unknown>(endpoint);
      }
      if(generation!==actionGeneration.current)return;
      if(run.kind==='planning'){
        const fresh=value as NonNullable<LiveSession['planning']>;
        if(fresh.id!==run.id||fresh.project_id!==project||fresh.workspace!==workspace)throw new Error('Cizí odpověď běhu.');
        setPlanning(rows=>rows.map(r=>r.id===run.id?planningSession(fresh):r));
      }else{
        const fresh=value as NonNullable<LiveSession['handoff']>;
        if(fresh.id!==run.id||fresh.scope.project!==project||fresh.scope.workspace!==workspace)throw new Error('Cizí odpověď běhu.');
        setHandoffs(rows=>rows.map(r=>r.id===run.id?handoffSession(fresh):r));
      }
      setStopFor('');
    }catch(e){if(generation===actionGeneration.current)setActionError(`Zastavení není potvrzeno: ${errorMessage(e)}`);}
    finally{readVersion.current++;if(generation===actionGeneration.current)setBusy(false);}
  }
  const control=<div className="live-controls">
    <button disabled={!canStop||busy} onClick={()=>setStopFor(selected!.key)}>Zastavit tento běh</button>
    {selected?.status==='stopping'&&<p role="status">Zastavení vyžádáno; čekám na potvrzení serveru.</p>}
    {!canStop&&<p className="live-note">{workspace==='main'?'Main je pouze pro čtení.':'Zastavení je dostupné jen pro aktivní běh s dostupným zdrojem.'}</p>}
    {stopFor&&stopFor===selected?.key&&<div role="group" aria-label="Potvrzení zastavení"><p>Zastavit pouze session <code>{selected.id}</code>? Aktuální výstup zůstane v historii.</p><button disabled={busy} onClick={()=>void confirmStop()}>Potvrdit zastavení</button><button disabled={busy} onClick={()=>setStopFor('')}>Nezastavovat</button></div>}
    <p className="live-note">Nový model se spouští pouze schválením zadání v Editoru. Otevření ani obnovení Live Run jej nespustí.</p>
    <div className="live-controls-disabled"><button disabled title="Zdroj nemá transport pro změnu zadání.">Upravit pokyn</button><button disabled title="Zdroj nemá transport resume.">Pokračovat</button><button disabled title="Zdroj nemá transport compact.">Compact nyní</button></div>
  </div>;

  return <section className="live-desktop" aria-label="Live workspace">
    <header className="live-toolbar">
      <div className="live-filter-group"><span className="live-eyebrow">Stav</span>{stateFilters.map(([value,label])=><button key={value} aria-pressed={filter===value} onClick={()=>setFilter(value)}>{label}</button>)}</div>
      <div className="live-source-health" aria-label="Dostupnost zdrojů"><span className={sourceErrors.planning?'is-error':''}>Návrhy · {sourceErrors.planning?'nedostupné':sourcePending.planning?'načítání':'připojeno'}</span><span className={sourceErrors.handoff?'is-error':''}>Hermes úkoly · {sourceErrors.handoff?'nedostupné':sourcePending.handoff?'načítání':'připojeno'}</span></div>
      <button onClick={()=>setRefresh(x=>x+1)} disabled={loading}>Obnovit (jen čtení)</button>
    </header>
    <div className="live-columns">
      <aside className="live-shelf" aria-label="Sessions projektu">
        <header className="live-pane-head"><span className="live-eyebrow">Live Run · historie</span><h2>Sessions projektu <span>{visible.length}</span></h2><p className="live-note">Skutečné návrhy a dokumentační úkoly · {workspace}</p></header>
        <div className="live-search"><input type="search" aria-label="Hledat v bězích a ticketech" placeholder="ID, zadání, výstup, ticket…" value={search} onChange={e=>setSearch(e.target.value)}/>{nodeId&&<label><input type="checkbox" checked={onlyNode} onChange={e=>setOnlyNode(e.target.checked)}/>Jen vybraný uzel</label>}</div>
        {Object.entries(sourceErrors).map(([source,error])=><p className="live-source-error" role="alert" key={source}>{source==='planning'?'Návrhové běhy':'Handoff běhy'}: {error}. Zachované položky mohou být neaktuální.</p>)}
        {loading&&<p role="status">Načítám skutečné běhy…</p>}
        <div className="live-session-list">{visible.map(run=><button className="live-session-card" key={run.key} aria-pressed={run.key===selected?.key} onClick={()=>{setSelectedKey(run.key);setTab(1);}}>
          <span className="live-card-top"><span>{run.kind==='planning'?'LLM návrh':'Hermes · dokument'}</span><span className={`live-status status-${run.status}`}>{run.label}</span></span>
          <strong>{run.title}</strong><code>{run.id}</code><span className="live-card-meta">{run.at||'Čas nedostupný'}{run.model!=='nedostupné'?` · ${run.model}`:''}</span>
        </button>)}</div>
        {!loading&&!visible.length&&<p className="live-empty">Žádná session neodpovídá filtru ani hledání.</p>}
        <footer className="live-shelf-foot"><span>Návrhové běhy: {planning.length} · Handoff běhy: {handoffs.length}</span><p>API poskytuje nejvýše 20 návrhových a 20 dokumentačních běhů. Nejde o úplný archiv.</p></footer>
      </aside>
      <section className="live-detail" aria-label="Detail session">
        <header className="live-detail-head"><div className="live-card-top"><span className="live-eyebrow">{selected?selected.kind==='planning'?'Návrhový běh':'Dokumentační běh':'Vyberte session'}</span>{selected&&<span className={`live-status status-${selected.status}`}>{selected.label}</span>}</div>
          <h2>{selected?.title||'Průběh, výsledek a ověření'}</h2>
          {selected&&<><code className="live-run-id">{selected.id}</code><dl className="live-kv"><dt>Provider / model</dt><dd>{selected.provider} / {selected.model}</dd><dt>Uzel / prostředí</dt><dd>{selected.nodeId||'Projektový rozsah'} · {workspace}</dd><dt>Poslední stav zdroje</dt><dd>{selected.at||'nedostupné'}</dd><dt>Git větev / worktree</dt><dd>{selected.handoff?.branch||'nedostupné'} · {selected.handoff?.worktree||'nedostupné'}</dd></dl></>}
        </header>
        <nav className="live-detail-tabs" role="tablist" aria-label="Detail běhu">{tabs.map((label,i)=><button type="button" role="tab" id={`live-tab-${i}`} aria-controls="live-tab-content" aria-selected={tab===i} key={label} onClick={()=>setTab(i)}>{label}</button>)}</nav>
        <div id="live-tab-content" className="live-tab-content" role="tabpanel" aria-labelledby={`live-tab-${tab}`}>
          {actionError&&<p role="alert">{actionError}</p>}
          {tab===0&&<><h3>Události</h3>{selected?.events.length?<ol className="live-timeline">{selected.events.map((e,i)=><li key={i}><time>{e.observedAt||'Čas nedostupný'}</time><strong>{e.kind}</strong></li>)}</ol>:<p className="live-note">Zdroj neposkytuje detailní proud událostí pro tento běh.</p>}{selected&&<p>Poslední doložený stav: {selected.at||'nedostupné'} · {selected.label}</p>}<p className="live-note">Pouze zdrojové události; žádné interní uvažování modelu.</p></>}
          {tab===1&&<><h3>Výsledek a důkazy</h3>{selected?.kind==='planning'&&<div className="live-notice"><strong>Návrh není implementace</strong><p>Tento běh vytvořil textový návrh. Neprokazuje změnu zdrojového kódu ani úspěšné testy.</p></div>}{selected?.handoff&&<div className="live-notice"><strong>{selected.verified===true?'Dokument nezávisle ověřen':selected.verified===false?'Ověření selhalo':'Ověření zatím nedoloženo'}</strong><p>Dokumentační úkol; není to obecné programování aplikace.</p></div>}
            {selected?.error&&<p role="alert">{selected.error}</p>}
            {selected?.output?<><div className="live-output-head"><span>Uložený výstup ze zdroje</span><button onClick={()=>downloadLiveText(`opora-${selected.id}.md`,selected.output,'text/markdown;charset=utf-8')}>Stáhnout výstup</button></div><pre className="live-output" data-testid="live-run-output">{selected.output}</pre>{selected.handoff?.result?.sha256&&<p className="live-note">SHA-256: <code>{selected.handoff.result.sha256}</code></p>}</>:<p className="live-empty">{selected?'Běh zatím nemá uložený výstup.':'Vyberte běh vlevo. Pokud žádný není, připravte zadání v Editoru.'}</p>}
          </>}
          {tab===2&&<><h3>Náklady a výkon</h3><div className="live-metrics">{[['USD · skutečné náklady',selected?.cost!=null?String(selected.cost):'nedostupné'],['Tokeny vstup / výstup','nedostupné'],['Cache / reasoning','nedostupné'],['API volání','nedostupné'],['Zahájeno',selected?.createdAt||'nedostupné'],['Poslední stav',selected?.at||'nedostupné']].map(([label,value])=><div key={label}><strong>{value}</strong><span>{label}</span></div>)}</div><p className="live-note">Neznámá hodnota není nula. Nezobrazujeme vymyšlené skóre ani procenta pokroku.</p></>}
          {tab===3&&<><h3>Paměť a přesný kontext</h3><p className="live-note">Dnešní paměť projektu není důkazem toho, co dostal dřívější běh.</p>{selected?.handoff?<><button onClick={()=>void readContext()}>Načíst přesné předané zadání</button><p>Otisk: <code>{selected.digest}</code></p>{exactContext!==null&&<><button onClick={()=>downloadLiveText(`opora-context-${selected.id}.json`,JSON.stringify(exactContext,null,2),'application/json')}>Stáhnout přesný kontext</button><pre className="live-output">{JSON.stringify(exactContext,null,2)}</pre></>}</>:<p>Historický kontext návrhu: nedostupné v tomto API. Jeho přítomnost si nedomýšlíme.</p>}</>}
          {tab===4&&<><h3>Ovládání session</h3>{control}</>}
          {tab===5&&<>{memoryError&&<p role="alert">{memoryError} <button onClick={reload}>Znovu načíst paměť</button></p>}<LiveTickets key={selected?.key||'project'} state={state} readOnly={readOnly||memoryLoading||!!memoryError} nodeId={selected?.nodeId||nodeId} sessionId={selected?.id||''} mutate={mutate}/></>}
          {tab===6&&<><h3>Kontext a osa</h3><div className="live-notice"><strong>Kontextové okno: nedostupné</strong><p>Průběh kompaktace: nedostupné — tento zdroj telemetrii nehlásí.</p></div><h4>Časová osa · session a rozhodnutí projektu</h4><ol className="live-timeline">{timeline.map((e,i)=><li key={i}><time>{e.at}</time><strong>{e.kind}</strong><span>{e.kind==='Rozhodnutí'?`Rozhodnutí: ${e.text}`:e.text}</span></li>)}</ol>{!timeline.length&&<p className="live-empty">Zatím žádné skutečné události v ose.</p>}</>}
        </div>
      </section>
      <aside className="live-side" aria-label="Boční vlákno a ovládání">
        <header className="live-pane-head"><span className="live-eyebrow">Session · vedlejší komunikace</span><h2>Boční vlákno · /btw</h2><p className="live-note">Hlavní zadání zůstává beze změny.</p></header>
        <div className="live-side-body"><div className="live-message"><strong>Transport není připojený</strong><p>Canvas API zatím nepodporuje boční dotazy. Žádný dotaz se neodešle a nevytváříme falešnou odpověď agenta.</p></div><label>Boční dotaz<textarea disabled rows={3} placeholder="/btw Proč jsi zvolil tento postup?"/></label><button disabled>Odeslat boční dotaz</button><h3>Rychlé ovládání</h3>{tab!==4?control:<p className="live-note">Potvrzení je na kartě Ovládání.</p>}<div className="live-source-note"><strong>Zdroj dat</strong><code>{selected?.kind==='handoff'?'/api/task-handoffs':'/api/llm/runs'}</code><p>Čtení každé 4 s při viditelném okně. Žádný automatický restart.</p></div></div>
      </aside>
    </div>
  </section>;
}
