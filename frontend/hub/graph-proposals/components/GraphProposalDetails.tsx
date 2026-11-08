import type { Graph, SpecFields } from "@/shared/types/logic/types";
import { fieldKeys, fieldLabels } from "@/hub/plan-changes/logic/plan-changes";
import type { GraphProposalsView } from "../logic/use-graph-proposals";
import { graphProposalStale } from "../logic/graph-proposals";
import GraphChangeReview from "./GraphChangeReview";
import GraphProposalCanvas from "./GraphProposalCanvas";
import { CARRIES_LABEL } from "@/shared/edge-carries/logic/edge-carries";
import ProposalReview from "@/hub/proposal-review/components/ProposalReview";
import { reviewReady } from "@/hub/proposal-review/logic/proposal-review";
import type { ProposalReviewView } from "@/hub/proposal-review/logic/use-proposal-review";

function GraphContents({ graph }: { graph: Graph }) {
  return <><ul className="graph-proposals__nodes">{graph.nodes.map(node => <li key={node.id}>
    <strong>{node.name}</strong> · {node.kind} · ID <code>{node.id}</code>
    <p>Rodič: <code>{node.parentId ?? "kořen"}</code> · souřadnice {node.x}, {node.y}
      {node.size && <> · rozměry {node.size.w} × {node.size.h}</>}</p>
    {node.purpose && <pre>{node.purpose}</pre>}
    {node.sourceRef && <p>Zdroj: {node.sourceRef.origin} · {node.sourceRef.kind} · <code>{node.sourceRef.path}</code></p>}
  </li>)}</ul>
    <ul>{graph.edges.map(edge => <li key={edge.id}>Vazba <code>{edge.id}</code>: <code>{edge.source}</code> → <code>{edge.target}</code> ({edge.port ?? "next"}{edge.carries ? `, teče: ${CARRIES_LABEL[edge.carries]}` : ""})</li>)}</ul>
    {!graph.edges.length && <p>Bez vazeb.</p>}</>;
}
function Documents({ documents }: { documents: { nodeId: string; fields: SpecFields; revision?: number; ownerWorkspace?: string }[] }) {
  return <>{documents.map(document => <article className="graph-proposals__document" key={document.nodeId}>
    <h4>Zadání <code>{document.nodeId}</code></h4>
    {document.revision !== undefined && <p>Revize {document.revision} · prostor <code>{document.ownerWorkspace}</code></p>}
    {fieldKeys.map(field => <div key={field}>
      <strong>{fieldLabels[field]}</strong><pre>{document.fields[field] || "(prázdné)"}</pre>
    </div>)}
  </article>)}</>;
}
export default function GraphProposalDetails({ model, review }: { model: GraphProposalsView; review?: ProposalReviewView }) {
  const proposal = model.inspected;
  if (!proposal) return null;
  const stale = !model.context || graphProposalStale(model.context, proposal);
  const changes = proposal.schemaVersion === 2;
  const incomplete = changes && (!proposal.changes || !proposal.stateEffects);
  return <section className="graph-proposals__details" aria-label="Obsah návrhu rozšíření">
    <h3>{proposal.subject}</h3>
    <p role="status" className="graph-proposals__preview-status">{proposal.accepted ? "Návrh byl přijat" : "Návrh – čeká na přijetí"}</p>
    <dl className="graph-proposals__identity">
      <dt>Neměnná revize návrhu</dt><dd><code>{proposal.id}</code></dd>
      <dt>Přijatá výchozí revize</dt><dd><code>{proposal.parentRevision ?? "První plán bez přijaté revize"}</code></dd>
      <dt>Aktuální přijatá revize</dt><dd><code>{model.context ? model.context.acceptedHead ?? "Bez přijaté revize" : "Kontext zatím není načtený"}</code></dd>
      <dt>Otisk výchozího grafu</dt><dd><code>{proposal.graphDigest}</code></dd>
      <dt>Autor a čas</dt><dd>{proposal.by.name} ({proposal.by.kind}) · {new Date(proposal.createdAt).toLocaleString("cs-CZ")}</dd>
    </dl>
    <GraphProposalCanvas key={proposal.id} proposal={proposal} />
    {proposal.supersedes && <p>Nový návrh odvozený z <code>{proposal.supersedes}</code>. Původní návrh zůstává v historii.</p>}
    <ul>{Object.entries(proposal.refs).map(([ref, id]) => <li key={ref}>Značka <code>{ref}</code> → ID <code>{id}</code></li>)}</ul>
    <ul>{Object.entries(proposal.inside).map(([id, area]) => <li key={id}>Prvek <code>{id}</code> bude uvnitř oblasti <code>{area}</code>.</li>)}</ul>
    <h4>Přidávaný graf · {proposal.additions.nodes.length} prvků, {proposal.additions.edges.length} vazeb</h4>
    <GraphContents graph={proposal.additions} />
    <Documents documents={proposal.specifications} />
    <GraphChangeReview proposal={proposal} />
    <ProposalReview model={review} proposalKind={changes ? "graph-change" : "graph-addition"} proposalId={proposal.id} acceptedHead={model.context?.acceptedHead ?? null} />
    {!!proposal.architectureDocuments?.length && <section aria-label="Přebíraná zadání architektury"><h4>Přebíraná zadání kontextu architektury</h4>
      <p>Tyto přesné revize a texty budou součástí přijatého kontextu. Sdílená zadání se nepřepisují.</p><Documents documents={proposal.architectureDocuments} /></section>}
    {changes && !proposal.accepted && <label className="graph-proposals__ack"><input type="checkbox" checked={model.acknowledged}
      disabled={model.disabled || stale || incomplete} onChange={event => model.acknowledge(event.target.checked)} />
      Zkontroloval/a jsem všechny úpravy, odstranění a jejich dopady a výslovně přijímám změny návrhu <code>{proposal.id}</code>.
    </label>}
    {proposal.requiresBaseAdoption ? <section className="graph-proposals__adoption" aria-label="Převzetí výchozího grafu">
      <h4>První převzetí existujícího grafu a zadání</h4>
      <p>Přijetí zahrne také následující výchozí graf a uložená zadání. Zkontrolujte celý obsah, nikoli jen nové prvky.</p>
      <GraphContents graph={proposal.baseGraph} />
      <Documents documents={proposal.adoptionDocuments} />
      {!proposal.accepted && <label className="graph-proposals__ack"><input type="checkbox" checked={model.acknowledged}
        disabled={model.disabled || stale} onChange={event => model.acknowledge(event.target.checked)} />
        Zkontroloval/a jsem výchozí graf i zadání a výslovně přebírám otisk <code>{proposal.graphDigest}</code>.
      </label>}
    </section> : <details><summary>Výchozí graf návrhu</summary><GraphContents graph={proposal.baseGraph} /></details>}
    {proposal.accepted ? <p role="status">Tento návrh byl přijat.</p> : <>
      {stale && model.context && <p className="graph-proposals__warning">Návrh vznikl nad jiným kontextem. Převod vytvoří nový neměnný návrh, který je nutné znovu zkontrolovat.</p>}
      <p>{changes ? "Přijetí provede pouze uvedené změny a odstranění v přijatém plánu i pracovním Canvasu." : "Přijetí přidá uvedené prvky, vazby a zadání do Canvasu."} Nepotvrzuje implementaci ani dokončení práce.</p>
      <div className="graph-proposals__actions">
        <button type="button" disabled={model.disabled || (!stale && !changes)} onClick={model.rebase}>Vytvořit návrh nad aktuálním základem</button>
        <button type="button" disabled={model.disabled || stale || incomplete || ((changes || proposal.requiresBaseAdoption) && !model.acknowledged) || !reviewReady(review, { proposalKind: changes ? "graph-change" : "graph-addition", proposalId: proposal.id }, model.context?.acceptedHead ?? null)} onClick={model.accept}>{changes ? "Přijmout úpravy plánu" : "Přijmout rozšíření plánu"}</button>
      </div>
    </>}
  </section>;
}
