import type { GraphProposal, ProposedDocument } from "../logic/graph-proposals";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { fieldKeys, fieldLabels } from "@/hub/plan-changes/logic/plan-changes";
import { EvidenceValue } from "./GraphChangeReview";

function DocumentValue({ document, before }: { document: ProposedDocument; before?: boolean }) {
  if (document.kind === "text") return <pre>{(before ? document.before : document.value) || "(prázdný text)"}</pre>;
  const value = before ? document.before : document.value;
  return <>{fieldKeys.map(field => <div key={field}><strong>{fieldLabels[field]}</strong><pre>{value[field] || "(prázdné)"}</pre></div>)}
    {"steps" in value && <section><strong>Kroky zadání</strong><EvidenceValue value={value.steps} /></section>}</>;
}

/** Immutable review only. No editor, mutations, executable HTML or client-side reconstruction. */
export default function GraphProposalContent({ proposal, nodeId }: { proposal: GraphProposal; nodeId?: string }) {
  if (proposal.schemaVersion !== 3) return null;
  const content = proposal.contentEffects;
  if (!content) return <p role="alert">Úplný navržený obsah chybí. Návrh nelze bezpečně posoudit.</p>;
  const before = proposal.stateEffects?.before as DesktopState | undefined;
  const ids = new Set(content.documents.map(document => document.nodeId));
  for (const [id, state] of Object.entries(content.after.nodes)) {
    if (JSON.stringify(state) !== JSON.stringify(before?.nodes[id])) ids.add(id);
  }
  const addedRules = content.after.rules.filter(rule => !before?.rules.some(old => JSON.stringify(old) === JSON.stringify(rule)));
  for (const rule of addedRules) if (rule.scope === "node") ids.add(rule.target);
  const shown = nodeId ? [...ids].filter(id => id === nodeId) : [...ids];
  if (!shown.length) return nodeId ? <p>Obsah této karty se v návrhu nemění.</p> : null;
  return <section className="graph-proposals__content" aria-label="Navržený obsah karet">
    <h4>Navržený obsah · pouze náhled</h4>
    <p>{proposal.accepted ? "Obsah byl součástí přijatého návrhu." : "Tento obsah čeká na přijetí. Živý obsah karet se uložením návrhu nezměnil."}
      {proposal.stateEffects && <> Výchozí revize stavu: {proposal.stateEffects.revision}.</>}</p>
    {shown.map(id => {
      const state = content.after.nodes[id] as (DesktopState["nodes"][string] & { briefGroup?: string; briefDiscipline?: string }) | undefined;
      const node = proposal.resultGraph?.nodes.find(item => item.id === id);
      return <article className="graph-proposals__document" key={id}>
        <h5>{node?.name ?? id}</h5>
        {content.documents.filter(document => document.nodeId === id).map(document => <section key={document.kind}>
          <h6>{document.kind === "text" ? "Text karty" : "Zadání karty"} · očekávaná revize {document.expectedRevision}</h6>
          <DocumentValue document={document} />
          <details><summary>Pracovní obsah před návrhem · revize {document.expectedRevision}</summary><DocumentValue document={document} before /></details>
        </section>)}
        {state?.blocks?.map(block => <section className="graph-proposals__content-block" key={block.id}>
          <h6>Blok {block.number} · {block.title}</h6><pre>{block.text}</pre>
          {block.state.condition && <p>Podmínka: {block.state.condition}</p>}
          {!!block.ports?.length && <ul>{block.ports.map(port => <li key={port.id}>Port {port.label || port.id} · <code>{port.id}</code>
            {proposal.resultGraph?.edges.filter(edge => edge.source === id && edge.sourceBlockId === block.id && edge.sourcePortId === port.id)
              .map(edge => <span key={edge.id}> → {proposal.resultGraph?.nodes.find(target => target.id === edge.target)?.name ?? edge.target}</span>)}
          </li>)}</ul>}
          <details><summary>Úplné údaje bloku</summary><EvidenceValue value={block} /></details>
        </section>)}
        {(state?.briefGroup || state?.briefDiscipline) && <p>Schránka: {state.briefGroup ?? state.briefDiscipline}</p>}
        {!!state?.fragmentRefs?.length && <ul>{state.fragmentRefs.map(ref => <li key={ref.fragmentId}>Zdroj ze Schránky <code>{ref.fragmentId}</code> · revize {ref.revision}</li>)}</ul>}
        {addedRules.filter(rule => rule.target === id).map(rule => <p key={rule.id}>Pravidlo ({rule.kind}): {rule.text}</p>)}
        {state && <details><summary>Úplný navržený stav karty</summary><EvidenceValue value={state} /></details>}
      </article>;
    })}
  </section>;
}
