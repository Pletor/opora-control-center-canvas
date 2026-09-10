import { useState } from 'react';
import type { DesktopState, Ticket, TicketPriority, TicketStatus } from './types';

type Props = {state:DesktopState; readOnly:boolean; nodeId?:string; sessionId:string;
  mutate:(fn:(state:DesktopState)=>DesktopState)=>Promise<boolean>};
export function LiveTickets({state,readOnly,nodeId,sessionId,mutate}:Props) {
  const [title,setTitle]=useState('');
  const [priority,setPriority]=useState<TicketPriority>('normal');
  const [session,setSession]=useState(sessionId);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const tickets=state.tickets.filter(t=>(!sessionId || t.sessionId===sessionId)&&(!nodeId || t.nodeId===nodeId));
  async function save(change:(s:DesktopState)=>DesktopState) {
    setBusy(true);setError('');
    const ok=await mutate(change);setBusy(false);
    if(!ok)setError('Ticket se nepodařilo uložit. Stav nebyl potvrzen.');
    return ok;
  }
  async function add(){
    if(!title.trim()||busy||readOnly)return;
    const ticket:Ticket={id:crypto.randomUUID(),title:title.trim(),priority,status:'open',nodeId:nodeId||'',sessionId:session.trim(),createdBy:'human'};
    if(await save(s=>({...s,tickets:[...s.tickets,ticket]})))setTitle('');
  }
  return <section className="live-ticket-panel" aria-label="Tickety">
    <h3>Tickety · {tickets.length}</h3>
    <p className="live-note">{sessionId?'Pracovní deník vybrané session.':'Projektové tickety; session lze zadat ručně.'} Autor nového ticketu: člověk.</p>
    {readOnly&&<p role="status">Main je pouze pro čtení.</p>}
    {error&&<p role="alert">{error}</p>}
    <ul className="v3-ticket-list">{tickets.map(t=><li className="v3-ticket" key={t.id}>
      <strong>{t.title}</strong><span className="v3-chip">{t.priority}</span><span>{t.createdBy==='agent'?'agent':'člověk'}</span><code>{t.sessionId}</code>
      <select aria-label={`Stav ticketu ${t.title}`} value={t.status} disabled={readOnly||busy} onChange={e=>{const status=e.target.value as TicketStatus;void save(s=>({...s,tickets:s.tickets.map(x=>x.id===t.id?{...x,status}:x)}));}}>
        <option value="open">otevřeno</option><option value="doing">probíhá</option><option value="done">hotovo</option>
      </select></li>)}</ul>
    {!tickets.length&&<p className="live-note">Žádné tickety v tomto rozsahu.</p>}
    <form className="live-ticket-form" onSubmit={e=>{e.preventDefault();void add();}}>
      <label>Název nového ticketu<input aria-label="Název nového ticketu" value={title} onChange={e=>setTitle(e.target.value)} disabled={readOnly||busy} maxLength={1000}/></label>
      <label>Priorita<select aria-label="Priorita nového ticketu" value={priority} onChange={e=>setPriority(e.target.value as TicketPriority)} disabled={readOnly||busy}><option value="low">nízká</option><option value="normal">normální</option><option value="high">vysoká</option></select></label>
      <label>Session<input aria-label="Session ID nového ticketu" value={session} onChange={e=>setSession(e.target.value)} disabled={readOnly||busy||!!sessionId}/></label>
      <button className="primary" disabled={readOnly||busy||!title.trim()}>Založit ticket</button>
    </form>
  </section>;
}
