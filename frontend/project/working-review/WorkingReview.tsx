import {useCallback, useEffect, useRef, useState} from 'react';
import {api} from '@/shared/types/logic/types';
import {EvidenceValue} from '@/hub/graph-proposals/components/GraphChangeReview';
import ReviewImpact from './ReviewImpact';
import {ReviewMutations} from './review-requests';
import './working-review.css';

type Review = {project: string; workspace: string; operation: string; requestId: string; status: string;
  preparation: {state: string; review?: {acceptedHead: string | null; before: unknown; after: unknown;
    input: unknown; preview?: {label?: string; nodeCount?: number; edgeCount?: number}}};
  application: null | {status: string; result: {result?: {recoveryId?: string}}}};
export function selected(search: string, project: string, workspace: string) {
  const q = new URLSearchParams(search), operation = q.get('workingOperation'), identifier = q.get('workingReview');
  return q.get('project') === project && q.get('workspace') === workspace && identifier
    && ['remove_item', 'restore_removed', 'graph'].includes(operation ?? '') ? {operation: operation!, identifier} : null;
}

export default function WorkingReview({project, workspace, onBack}: {project: string; workspace: string; onBack: () => void}) {
  const [saved, setSaved] = useState<Review | null>(null), [error, setError] = useState('');
  const [busy, setBusy] = useState(false), [checked, setChecked] = useState(false);
  const generation = useRef(0), picked = selected(location.search, project, workspace);
  const operation = picked?.operation, identifier = picked?.identifier;
  const path = operation && identifier ? `/api/working-reviews/${operation}/${encodeURIComponent(identifier)}` : null;
  const scopeKey = JSON.stringify([project, workspace, path]);
  const activeScope = useRef(scopeKey), mutations = useRef(new ReviewMutations());
  if (activeScope.current !== scopeKey) {activeScope.current = scopeKey; generation.current++; mutations.current.invalidate();}
  const reload = useCallback(async () => {
    const current = ++generation.current;
    setSaved(null); setChecked(false); setError('');
    if (!path) {setError('Vybraný návrh v tomto projektu a prostoru neexistuje.'); return;}
    try {
      const result = await api<Review>(path + '?' + new URLSearchParams({project, workspace}));
      if (current === generation.current) setSaved(result);
    } catch (caught) {if (current === generation.current) setError(String(caught));}
  }, [path, project, workspace]);
  useEffect(() => {setBusy(false); void reload(); return () => {generation.current++; mutations.current.invalidate();};}, [reload]);
  const review = saved?.preparation.review;
  const actionable = saved?.status === 'complete' && saved.preparation.state === 'awaiting_human' && !saved.application && !!review;
  const apply = async () => {
    if (!path || !actionable || !checked || busy) return;
    const token = mutations.current.begin();
    if (token === null) return;
    const current = generation.current;
    setBusy(true); setError('');
    try {
      await api(path + '/apply', {project, workspace});
      if (current === generation.current) await reload();
    } catch (caught) {if (current === generation.current) {setError(String(caught)); setSaved(null); setChecked(false);}}
    finally {if (mutations.current.finish(token)) setBusy(false);}
  };
  return <section className="graph-proposals__details working-review" aria-label="Kontrola změny pracovního plátna">
    <button onClick={onBack}>Zpět</button><h2>Kontrola změny pracovního plátna</h2>
    <p>Projekt <code>{project}</code> · prostor <code>{workspace}</code> · podklad <code>{identifier ?? 'chybí'}</code></p>
    <button disabled={busy} onClick={() => void reload()}>Obnovit podklad</button>
    {error && <p role="alert">{error}</p>}
    {saved?.application && <p role="status">{saved.application.status === 'complete' ? 'Změna byla provedena a ověřena.' : 'Zápis není dokončený. Nejprve je nutné ověřit skutečný stav; operace se automaticky neopakuje.'}
      {saved.application.result?.result?.recoveryId && <> Obnova: <code>{saved.application.result.result.recoveryId}</code>.</>}</p>}
    {review && <>
      <p role="status">{actionable ? 'Návrh – čeká na lidské potvrzení' : 'Uložený podklad změny'}</p>
      <h3>{operation === 'remove_item' ? 'Odstranění' : operation === 'restore_removed' ? 'Obnova odstraněného obsahu' : 'Změna grafu'} · {review.preview?.label}</h3>
      <p>Přijatá revize plánu <code>{review.acceptedHead ?? 'žádná'}</code> zůstává beze změny. Mění se pracovní plátno; přijatý plán tím není automaticky změněn ani práce potvrzena.</p>
      <ReviewImpact before={review.before} after={review.after} input={review.input} operation={operation}/>
      <details><summary>Přesný požadavek</summary><EvidenceValue value={review.input}/></details>
      {actionable && <><label><input type="checkbox" checked={checked} disabled={busy} onChange={event => setChecked(event.target.checked)}/> Zkontroloval/a jsem rozsah, změny obsahu a dopad na pracovní plátno.</label>
        <button disabled={busy || !checked} onClick={() => void apply()}>Potvrdit pracovní změnu</button></>}
    </>}
  </section>;
}
