import { useEffect, useRef, useState } from 'react';
import { api } from '@/shared/types/types';

export type TaskHandoff = {
  id: string; digest: string; scope: { project: string; workspace: string; node: string };
  task: string; status: string; allowedFiles?: string[]; readableNodeIds?: string[];
  provider?: string; model?: string; budgetSeconds?: number; contextSummary?: unknown;
  events?: { kind: string; observedAt?: string }[]; error?: string | null;
  verification?: { passed: boolean | null }; result?: { content: string; sha256: string } | null;
};
type Capability = { available: boolean; reason: string | null; provider: string | null; model: string | null; budgetSeconds: number | null };
const ACTIVE = new Set(['starting', 'running', 'stopping', 'verifying']);
const LABELS: Record<string, string> = { prepared: 'Připraveno — model neběží', starting: 'Spouští se', running: 'Běží', stopping: 'Zastavuje se', verifying: 'Ověřuje se výsledek', completed: 'Dokončeno', failed: 'Selhalo', cancelled: 'Zastaveno', interrupted: 'Přerušeno' };

function download(name: string, value: string, mime: string) {
  const url = URL.createObjectURL(new Blob([value], { type: mime }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

export default function TaskHandoffPanel({ project, workspace, nodeId, packetId, enabled }: {
  project: string; workspace: string; nodeId: string; packetId?: string; enabled: boolean;
}) {
  const [capability, setCapability] = useState<Capability | null>(null);
  const [task, setTask] = useState('');
  const [run, setRun] = useState<TaskHandoff | null>(null);
  const [approved, setApproved] = useState(false);
  const [stopRequested, setStopRequested] = useState(false);
  const [exactContext, setExactContext] = useState<{ id: string; digest: string; context: unknown } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const generation = useRef(0);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; generation.current++; }; }, []);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    api<Capability>(`/api/task-handoffs/capabilities?project=${encodeURIComponent(project)}`)
      .then(value => { if (!cancelled) setCapability(value); })
      .catch(() => { if (!cancelled) setCapability({ available: false, reason: 'Služba předání úkolu není dostupná.', provider: null, model: null, budgetSeconds: null }); });
    return () => { cancelled = true; };
  }, [project, enabled]);
  useEffect(() => {
    if (!enabled || !nodeId || run) return;
    let cancelled = false;
    const ticket = generation.current;
    api<{ runs: TaskHandoff[] }>(`/api/task-handoffs?project=${encodeURIComponent(project)}&workspace=${encodeURIComponent(workspace)}`)
      .then(async value => {
        const latest = value.runs.find(item => item.scope?.project === project && item.scope?.workspace === workspace && item.scope?.node === nodeId);
        if (!latest) return;
        const detail = await api<TaskHandoff>(`/api/task-handoffs/${encodeURIComponent(latest.id)}`);
        if (!cancelled && ticket === generation.current && detail.scope.project === project && detail.scope.workspace === workspace && detail.scope.node === nodeId) { setRun(detail); setTask(detail.task); }
      }).catch(() => { if (!cancelled && ticket === generation.current) setError('Historii úkolů se nepodařilo načíst.'); });
    return () => { cancelled = true; };
  }, [project, workspace, nodeId, enabled]);
  useEffect(() => {
    if (!enabled || !run || !ACTIVE.has(run.status)) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const value = await api<TaskHandoff>(`/api/task-handoffs/${encodeURIComponent(run.id)}`);
        if (value.id !== run.id || value.scope?.project !== project || value.scope?.workspace !== workspace || value.scope?.node !== nodeId) throw new Error('Cizí odpověď běhu.');
        if (!cancelled) { setRun(value); setError(''); if (ACTIVE.has(value.status)) timer = setTimeout(poll, 1200); }
      } catch { if (!cancelled) { setError('Stav běhu se nepodařilo ověřit. Nejde o potvrzení zastavení.'); timer = setTimeout(poll, 2500); } }
    };
    timer = setTimeout(poll, 700);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [enabled, run?.id, run?.status]);
  useEffect(() => {
    if (!enabled || run?.status !== 'prepared') return;
    let cancelled = false;
    setExactContext(null); setApproved(false);
    api<{ id: string; digest: string; context: unknown }>(`/api/task-handoffs/${encodeURIComponent(run.id)}/export`)
      .then(value => {
        if (value.id !== run.id || value.digest !== run.digest || !value.context || typeof value.context !== 'object') throw new Error('Kontext neodpovídá připravenému zadání.');
        if (!cancelled) setExactContext(value);
      }).catch(() => { if (!cancelled) setError('Přesný kontext nebyl ověřen; spuštění je zablokované.'); });
    return () => { cancelled = true; };
  }, [enabled, run?.id, run?.digest, run?.status]);
  const exactContextReady = Boolean(run && exactContext?.id === run.id && exactContext?.digest === run.digest);
  const validTask = task.trim().length >= 10 && task.length <= 4000;
  async function perform(action: () => Promise<TaskHandoff>) {
    if (busy || !enabled) return;
    const ticket = ++generation.current;
    setBusy(true); setError('');
    try {
      const value = await action();
      if (mounted.current && generation.current === ticket) {
        if (value.scope.project !== project || value.scope.workspace !== workspace || value.scope.node !== nodeId) throw new Error('Odpověď patří jinému kontextu.');
        setRun(value); setApproved(false);
        if (value.status === 'stopping' || !ACTIVE.has(value.status)) setStopRequested(false);
      }
    } catch (e) { if (mounted.current && generation.current === ticket) { setError(String(e)); setApproved(false); } }
    finally { if (mounted.current && generation.current === ticket) setBusy(false); }
  }
  const active = Boolean(run && ACTIVE.has(run.status));
  const stopPending = run?.status === 'stopping' && !run.error;
  return <section className="workbench-body task-handoff" aria-label="Izolovaný dokumentační úkol">
    <h2>Dokumentační úkol přes Hermes</h2>
    <p>První podporovaný typ: skutečné vytvoření <code>result.md</code> v odděleném Git prostoru. Žádná změna zdrojového projektu ani obecné programování.</p>
    <p>Kontext: <code>{project}/{workspace}/{nodeId || 'nevybrán'}</code></p>
    {workspace === 'main' && <p role="status">V main se úkol nespouští. Zvolte pracovní větev nebo návrh.</p>}
    {!packetId && <p role="status">Nejdřív v záložce Kontext sestavte aktuální paket vybraného uzlu.</p>}
    {!capability?.available && <p role="status">{capability?.reason || 'Ověřuji dostupnost služby…'}</p>}
    <label className="field">Zadání dokumentačního úkolu<textarea aria-label="Zadání dokumentačního úkolu" value={task} maxLength={4000} rows={5} disabled={active || busy} onChange={event => { generation.current++; setTask(event.target.value); setRun(null); setApproved(false); setError(''); }} /></label>
    <button type="button" disabled={!enabled || busy || active || !packetId || !validTask || !capability?.available || workspace === 'main'} onClick={() => perform(() => api('/api/task-handoffs/prepare', { packetId, task: task.trim() }))}>Připravit zadání</button>
    {error && <p role="alert">{error}</p>}
    {run && <><h3>{LABELS[run.status] || `Neznámý stav: ${run.status}`}</h3><p>Běh: <code>{run.id}</code></p>
      {run.status === 'prepared' && <>
        <p>Potvrzení spustí providerové volání přes Hermes. Časový limit není cenový strop. Běh se sám nerestartuje.</p>
        <p>Model: {run.provider} / {run.model} · nejvýše {run.budgetSeconds} s</p>
        <p>Povolený zápis: {(run.allowedFiles || []).join(', ')}</p>
        <p>Kontext lze dočítat jen pro: {(run.readableNodeIds || []).join(', ')}</p>
        <pre>{typeof run.contextSummary === 'string' ? run.contextSummary : JSON.stringify(run.contextSummary, null, 2)}</pre>
        <code className="task-digest">{run.digest}</code>
        {exactContextReady ? <details open><summary>Přesný schvalovaný kontext pro agenta</summary><pre data-testid="task-exact-context">{JSON.stringify(exactContext, null, 2)}</pre></details> : <p>Čekám na ověřený kontext; potvrzení není dostupné.</p>}
        <label className="check"><input type="checkbox" disabled={busy || !exactContextReady} checked={approved} onChange={event => setApproved(event.target.checked)} />Schvaluji tento kontext, rozsah a spuštění modelu</label>
        <button className="primary" type="button" disabled={!enabled || !approved || !exactContextReady || busy || !capability?.available} onClick={() => { if (approved && exactContextReady) perform(() => api(`/api/task-handoffs/${encodeURIComponent(run.id)}/start`, { digest: run.digest, confirmed: true })); }}>Potvrdit a spustit agenta</button>
      </>}
      {active && <>
        <button type="button" disabled={busy || stopPending} onClick={() => setStopRequested(true)}>Zastavit tento běh</button>
        {stopPending && <p>Zastavení už bylo vyžádáno; čekám na ověření serverem.</p>}
        {stopRequested && <div role="group" aria-label="Potvrzení zastavení"><p>Zastaví se pouze tento izolovaný běh. Za zastavený jej označíme až po ověření serverem.</p><button type="button" disabled={busy} onClick={() => perform(() => api(`/api/task-handoffs/${encodeURIComponent(run.id)}/stop`, { confirmed: true }))}>Potvrdit zastavení</button><button type="button" disabled={busy} onClick={() => setStopRequested(false)}>Nezastavovat</button></div>}
      </>}
      {busy && <p role="status">Zpracovávám a ověřuji operaci…</p>}
      <button type="button" disabled={busy} onClick={async () => {
        const ticket = generation.current;
        try { const value = await api<{ id: string; digest: string }>(`/api/task-handoffs/${encodeURIComponent(run.id)}/export`); if (value.id !== run.id || value.digest !== run.digest) throw new Error('Export neodpovídá běhu.'); if (mounted.current && ticket === generation.current) download(`opora-task-${run.id}.json`, JSON.stringify(value, null, 2), 'application/json'); }
        catch (e) { if (mounted.current && ticket === generation.current) setError(String(e)); }
      }}>Exportovat přesné zadání</button>
      {run.result && run.verification?.passed === true && <><pre data-testid="task-result-content">{run.result.content}</pre><p>SHA-256: <code>{run.result.sha256}</code></p><button type="button" onClick={() => download('result.md', run.result!.content, 'text/markdown;charset=utf-8')}>Stáhnout dokument</button></>}
      {run.error && <p role="alert">{run.error}</p>}
      {run.verification?.passed === true && <p>Soubor byl nezávisle ověřen.</p>}
      {!!run.events?.length && <details><summary>Skutečné události běhu</summary><ol>{run.events.map((event, index) => <li key={index}>{event.observedAt} {event.kind}</li>)}</ol></details>}
    </>}
  </section>;
}
