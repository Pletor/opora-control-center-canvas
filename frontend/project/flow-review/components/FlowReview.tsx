import {useCallback, useEffect, useRef, useState} from 'react';
import {api} from '@/shared/types/logic/types';
import FlowEditor from '@/shared/flow-editor/components/FlowEditor';
import type {NodeTypeSpec} from '@/shared/flow-editor/logic/flow-types';
import {graphDiff, diffSummary} from '@/shared/flow-editor/logic/graph-diff';
import {actionable, actionRequest, displayGraph, selection, titles, type Review} from '../logic/flow-review';
import '../styles/flow-review.css';

export default function FlowReview({project, workspace, onBack}: {project: string; workspace: string; onBack: () => void}) {
  const [review, setReview] = useState<Review | null>(null), [error, setError] = useState('');
  const [types, setTypes] = useState<NodeTypeSpec[]>([]), [node, setNode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false), [reason, setReason] = useState(''), [notice, setNotice] = useState('');
  const generation = useRef(0);
  const picked = selection(location.search, project, workspace);
  const operation = picked?.operation, identifier = picked?.identifier;
  const reload = useCallback(async () => {
    const current = ++generation.current;
    setReview(null); setTypes([]); setError('');
    if (!operation || !identifier) {setError('Vybraný podklad v tomto projektu a prostoru neexistuje.'); return;}
    try {
      const q = new URLSearchParams({project, workspace, operation, identifier});
      const result = await api<Review>('/api/flow/review?' + q);
      const catalog = await api<{node_types: NodeTypeSpec[]}>('/api/flow/node-types?kind=' + result.workflow.kind);
      if (current === generation.current) {setReview(result); setTypes(catalog.node_types); setNode(result.nodeRun?.node_id ?? null);}
    } catch (caught) {if (current === generation.current) setError(String(caught));}
  }, [project, workspace, operation, identifier]);
  useEffect(() => {void reload(); return () => {generation.current++;};}, [reload]);
  const decide = async (decision?: string) => {
    if (!review || busy || !actionable(review)) return;
    const current = generation.current;
    setBusy(true); setError('');
    try {
      const request = actionRequest(review, reason, decision);
      await api(request.url, request.body);
      if (current === generation.current) {setNotice('Vaše rozhodnutí bylo uloženo.'); await reload();}
    } catch (caught) {if (current === generation.current) {setError(String(caught)); setReview(null);}}
    finally {setBusy(false);}
  };
  const diff = review?.selected ? graphDiff(review.active?.graph ?? {nodes: [], edges: []}, review.selected.graph) : null;
  return <section className="flow-review" aria-label="Posouzení workflow">
    <header><button onClick={onBack}>← Zpět</button><h2>{operation ? titles[operation] : 'Posouzení workflow'}</h2><button disabled={busy} onClick={() => void reload()}>Obnovit podklady</button></header>
    {error && <p role="alert">{error} Obnovte podklady a znovu zkontrolujte vybranou verzi.</p>}
    {notice && <p role="status">{notice}</p>}
    {review && <>
      <h3>{review.workflow.name}</h3>
      <p>Aktuálně aktivní: {review.active ? `v${review.active.n}` : 'žádná verze'} · Vybraná: {review.selected ? `v${review.selected.n} (${review.selected.status})` : 'není dostupná'}</p>
      {diff && <p>{diffSummary(diff)}</p>}
      {review.nodeRun && <><p>Čekající krok: {review.nodeRun.node_id} · stav {review.nodeRun.status}</p><details open><summary>Vstup čekajícího kroku</summary><pre>{review.nodeRun.input_ref || 'Bez vstupu'}</pre></details></>}
      {review.selected && <div className="flow-review__graph"><FlowEditor graph={displayGraph(review.selected.graph)} types={types} readOnly selected={node} onSelect={setNode} onChange={() => {}} diff={diff}/></div>}
      <details><summary>Identifikátory</summary><p>Workflow: {review.workflow.id}</p><p>Vybraná verze: {review.selected?.id ?? '—'}</p><p>Aktivní verze: {review.active?.id ?? '—'}</p>{review.nodeRun && <p>Běh: {review.nodeRun.run_id} · krok: {review.nodeRun.id}</p>}</details>
      {actionable(review) ? <footer>
        <p>Čeká na vaše rozhodnutí. Samotné otevření podkladů nic nemění.</p>
        {review.operation === 'version_reject' && <label>Důvod zamítnutí<textarea value={reason} onChange={e => setReason(e.target.value)} maxLength={2000}/></label>}
        {review.operation === 'approval_decision' ? <><button disabled={busy} onClick={() => void decide('approved')}>Schválit krok a pokračovat</button><button disabled={busy} onClick={() => void decide('rejected')}>Zamítnout krok</button></> : <button disabled={busy || (review.operation === 'version_reject' && !reason.trim())} onClick={() => void decide()}>{titles[review.operation]}</button>}
      </footer> : <p>Tento podklad už nečeká na tuto změnu nebo ji v daném stavu nepodporuje.</p>}
    </>}
  </section>;
}
