import { useState } from "react";
import { useDraftTransition } from "../logic/draft-transition";
import type { CanvasNode } from "@/shared/types/logic/types";
import type { NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import ChecksEditor from "@/editor/node-detail/card-fields/components/ChecksEditor";
import EvidenceEditor from "@/editor/canvas/node-card/components/EvidenceEditor";
import CardChecks from "@/editor/canvas/node-card/components/CardChecks";
import { safeDesignUrl } from "@/editor/canvas/node-card/components/CardDesign";

const PAGE_SIZE = 50;
/** Velké seznamy mají čtecí tabulku po stránkách; plný editor člověk vědomě zapne až tlačítkem. */
export default function CardDnaEvidence({ node, data, onSaveNode }: {
  node: CanvasNode; data: NodeCardData; onSaveNode?: (node: CanvasNode) => void;
}) {
  const [editing, setEditing] = useState(false);
  const transition = useDraftTransition();
  const [page, setPage] = useState(0);
  const runs = data.evidence?.checksRun ?? [];
  const pages = Math.max(1, Math.ceil(runs.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  return <>
    <h3>Důkazy a kontroly</h3>
    {onSaveNode && <ChecksEditor node={node} onSave={onSaveNode} disabled={data.blocks.disabled} />}
    <CardChecks checks={data.view.checks} goal_mode={data.view.goal_mode} evidence={data.evidence} />
    {data.autonomous && <p>✓ Uzavřel agent v autonomním režimu.</p>}
    <p>Deklarované důkazy; server běhy nespouští ani obsah odkazů neověřuje.</p>
    <ul>{(["tests", "review", "merge"] as const).map(kind => {
      const proof = data.evidence?.[kind];
      return <li key={kind}>{kind}: {proof?.status ?? "nedoloženo"} · {proof?.note}
        {proof && safeDesignUrl(proof.url) && <> · <a href={proof.url} target="_blank" rel="noopener noreferrer">Důkaz</a></>}
      </li>;
    })}</ul>
    <div className="card-dna__table-scroll"><table className="card-dna__table">
      <caption>Běhy kontrol · {runs.length}</caption>
      <thead><tr><th>Kontrola</th><th>Příkaz</th><th>Exit</th><th>Čas</th><th>Log</th></tr></thead>
      <tbody>{runs.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE).map((run, index) => <tr key={`${run.checkId}:${index}`}>
        <td>{run.checkId}</td><td><code>{run.command}</code></td><td>{run.exitCode}</td><td>{run.at}</td>
        <td>{safeDesignUrl(run.logUrl) && <a href={run.logUrl} target="_blank" rel="noopener noreferrer">Log</a>}</td>
      </tr>)}</tbody>
    </table></div>
    {pages > 1 && <nav aria-label="Stránky běhů kontrol"><button type="button" disabled={current === 0} onClick={() => setPage(current - 1)}>Předchozí</button> {current + 1}/{pages} <button type="button" disabled={current + 1 === pages} onClick={() => setPage(current + 1)}>Další</button></nav>}
    {data.saveEvidence && <button type="button" disabled={data.blocks.disabled} onClick={() => { if (editing) void transition(() => setEditing(false)); else setEditing(true); }}>{editing ? "Skrýt editor důkazů" : "Upravit důkazy"}</button>}
    {editing && data.saveEvidence && <EvidenceEditor nodeId={node.id} evidence={data.evidence} disabled={data.blocks.disabled} save={data.saveEvidence} />}
  </>;
}
