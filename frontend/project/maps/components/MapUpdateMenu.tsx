import {useEffect,useId,useRef,useState} from 'react';
import '@/project/maps/styles/map-update-menu.css';

type Tool='graphify'|'archify';
type Status={project:string;enabled:boolean;status:string;phase?:string;error?:string|null;automatic:Record<Tool,boolean>;versions:Record<Tool,string|null>};
export default function MapUpdateMenu({project,tool,busy=false,onUpdate,onReload}:{project:string;tool:Tool;busy?:boolean;onUpdate?:()=>Promise<void>;onReload:()=>Promise<void>}){
  const [open,setOpen]=useState(false),[saving,setSaving]=useState(false),[state,setState]=useState<Status|null>(null),[error,setError]=useState('');
  const root=useRef<HTMLDivElement>(null),callbacks=useRef({onReload}),version=useRef<string|null>(null),alive=useRef(false);
  callbacks.current={onReload};const id=useId();
  async function read(signal?:AbortSignal){
    const response=await fetch('/api/map-refresh/status?project='+encodeURIComponent(project),{cache:'no-store',signal});
    const data=await response.json();
    if(!response.ok||data.project!==project)throw new Error(data.error??'Nastavení aktualizace není dostupné.');
    if(alive.current&&!signal?.aborted){
      setState(data);
      const next=data.versions?.[tool]??null;
      if(next&&next!==version.current){version.current=next;void callbacks.current.onReload()}
    }
  }
  useEffect(()=>{
    alive.current=true;version.current=null;const abort=new AbortController();
    const refresh=()=>void read(abort.signal).catch(()=>{});refresh();const timer=setInterval(refresh,5000);
    return()=>{alive.current=false;abort.abort();clearInterval(timer)};
  },[project,tool]);
  useEffect(()=>{
    if(!open)return;
    function outside(event:PointerEvent){if(!root.current?.contains(event.target as Node))setOpen(false)}
    function key(event:KeyboardEvent){if(event.key==='Escape'){setOpen(false);root.current?.querySelector('button')?.focus()}}
    document.addEventListener('pointerdown',outside);document.addEventListener('keydown',key);
    return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',key)};
  },[open]);
  async function setting(automatic:boolean){
    setSaving(true);setError('');
    try{
      const response=await fetch('/api/map-refresh/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project,tool,automatic})});
      const data=await response.json();if(!response.ok)throw new Error(data.error??'Nastavení se neuložilo.');
      await read();
    }catch(e){if(alive.current)setError(e instanceof Error?e.message:'Nastavení se neuložilo.')}
    finally{if(alive.current)setSaving(false)}
  }
  async function now(){
    setOpen(false);setError('');setSaving(true);
    try{
      if(onUpdate)await onUpdate();
      else{
        const response=await fetch('/api/map-refresh/retry?project='+encodeURIComponent(project)+'&tool='+tool,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
        const data=await response.json();if(!response.ok)throw new Error(data.error??'Aktualizaci se nepodařilo spustit.');
        await read();
      }
    }catch(e){if(alive.current)setError(e instanceof Error?e.message:'Aktualizace se nepodařila.')}
    finally{if(alive.current)setSaving(false)}
  }
  const running=state?.status==='running'||state?.status==='queued';
  return <div className="map-update-control" ref={root}>
    <button type="button" aria-expanded={open} aria-controls={id} onClick={()=>setOpen(!open)}>Aktualizovat graf <span aria-hidden="true">▾</span></button>
    {open&&<div className="map-update-menu" id={id} role="group" aria-label={'Aktualizace '+(tool==='graphify'?'Graphify':'Archify')}>
      <button type="button" disabled={busy||saving||running} onClick={()=>void now()}>Aktualizovat teď</button>
      <button type="button" disabled={busy||saving} onClick={()=>{setOpen(false);void onReload()}}>Načíst uložený výstup</button>
      <fieldset disabled={saving||!state||state.status==='unavailable'}><legend>Automatická aktualizace</legend>
        <label><input type="radio" name={id} checked={state?.automatic?.[tool]===true} onChange={()=>void setting(true)}/>Po mergi do main</label>
        <label><input type="radio" name={id} checked={state?.automatic?.[tool]===false} onChange={()=>void setting(false)}/>Pouze ručně</label>
      </fieldset>
      <small>Jen tento projekt · {tool==='archify'?'Sonnet: nejvýše 10 minut / 10 tahů':'lokální Graphify bez modelu'}</small>
      {!state?.enabled&&<small>Automatika na serveru není zapnutá.</small>}
    </div>}
    {running&&<span className="map-update-state" role="status">{state?.status==='queued'?'Čeká na aktualizaci':`Aktualizuji · ${state?.phase??tool}`}</span>}
    {(error||state?.error)&&<span className="map-update-error" role="alert">{error||state?.error}</span>}
  </div>;
}
