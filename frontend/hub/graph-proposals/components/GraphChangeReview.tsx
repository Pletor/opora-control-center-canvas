import type { GraphProposal } from "../logic/graph-proposals";
import { carriesChange, type Change } from "../logic/graph-edits";
import type { GraphEdge } from "@/shared/types/logic/types";

/** All evidence values remain React text, including arbitrary state keys and stored strings. */
export function EvidenceValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span>∅ (není)</span>;
  if (Array.isArray(value)) return value.length ? <ul>{value.map((item, index) => <li key={index}><EvidenceValue value={item} /></li>)}</ul> : <span>Prázdný seznam</span>;
  if (typeof value === "object") return <dl className="graph-proposals__evidence">{Object.entries(value).map(([key, item]) => <div key={key}><dt>{key}</dt><dd><EvidenceValue value={item} /></dd></div>)}</dl>;
  return <span className="graph-proposals__value">{String(value) || "(prázdné)"}</span>;
}
const columns = [ ["acceptedBefore", "Přijatý plán před změnou"], ["workingBefore", "Pracovní Canvas před změnou"],
  ["proposedAccepted", "Navržený přijatý plán"], ["proposedWorking", "Navržený pracovní Canvas"] ] as const;
const effectNames: Record<string, string> = { removedNodes: "Odstraněné aktuální stavy karet", removedEdges: "Odstraněné aktuální reporty vazeb",
  clearedEdgeReports: "Zneplatněné reporty přepojených vazeb", removedRules: "Odstraněná pravidla", removedDecisions: "Odstraněná rozhodnutí",
  removedAutonomy: "Odstraněné granty autonomie", unassignedTickets: "Zachované tickety s odebraným přiřazením", areaMembershipChanges: "Změny příslušnosti k oblastem" };
export default function GraphChangeReview({ proposal }: { proposal: GraphProposal }) {
  if (proposal.schemaVersion !== 2) return null;
  if (!proposal.changes || !proposal.stateEffects) return <p role="alert">Návrh neobsahuje úplné podklady pro kontrolu změn. Nelze jej přijmout.</p>;
  const removed = proposal.changes.nodes.filter(item => item.operation === "remove").length;
  const removedEdges = proposal.changes.edges.filter(item => item.operation === "remove").length;
  return <section aria-label="Kontrola úprav a odstranění" className="graph-proposals__change-review">
    <h4>Kontrola změn přijatého i pracovního grafu</h4>
    <p>Každé vybrané pole se mění v obou grafech. Nepřijaté pracovní odlišnosti ostatních polí zůstávají jen v pracovním Canvasu.</p>
    {proposal.changes.architectureContext && <section className="graph-proposals__adoption"><h4>Výslovné převzetí kontextu sdílené architektury</h4>
      <p>Mění se přijatý kontext závislostí; sdílená architektura se nepřepisuje.</p>
      <div className="graph-proposals__comparison">{columns.map(([key, title]) => <section key={key}><h5>{title}</h5><EvidenceValue value={proposal.changes!.architectureContext![key]} /></section>)}</div>
    </section>}
    {(removed > 0 || removedEdges > 0) && <p className="graph-proposals__warning"><strong>Odstranění: {removed} prvků a {removedEdges} vazeb.</strong> Zkontrolujte všechny níže uvedené dopady. Historická zadání, výsledky agentů a důkazy zůstávají zachované.</p>}
    {([ ["nodes", "Prvek"], ["edges", "Vazba"] ] as const).map(([collection, label]) => proposal.changes![collection].map(change => <article key={`${collection}-${change.id}`} className="graph-proposals__edit-row">
      <h4>{label} <code>{change.id}</code> · {change.operation === "remove" ? "Odstranění" : change.operation === "add" ? "Přidání" : "Úprava"}</h4>
      <p>Vybraná pole: {change.fields.join(", ") || "celý prvek"}</p>
      {collection === "edges" && (() => { const flow = carriesChange(change as Change<GraphEdge>); return flow && <p>Co po vazbě teče: {flow.before} → {flow.after}</p>; })()}
      <div className="graph-proposals__comparison">{columns.map(([key, title]) => <section key={key}><h5>{title}</h5><EvidenceValue value={change[key]} /></section>)}</div>
    </article>))}
    {proposal.changes.areaMembership.length > 0 && <section><h4>Příslušnost prvků k oblastem</h4>{proposal.changes.areaMembership.map(change => <article key={change.id}>
      <h5>{change.id}</h5><div className="graph-proposals__comparison">{columns.map(([key, title]) => <section key={key}><strong>{title}</strong><EvidenceValue value={change[key]} /></section>)}</div>
    </article>)}</section>}
    <h4>Dopady na aktuální stav a související záznamy</h4>
    <p>Revize stavu: {proposal.stateEffects.revision} · otisk kontrolovaných dopadů: <code>{proposal.stateEffects.affectedDigest}</code></p>
    {Object.entries(proposal.stateEffects.effects).map(([key, value]) => <section className="graph-proposals__effect" key={key}>
      <h5>{effectNames[key] ?? key}</h5><EvidenceValue value={value} /></section>)}
    <details><summary>Úplný stav před změnou a po změně</summary><h5>Před změnou</h5><EvidenceValue value={proposal.stateEffects.before} /><h5>Po změně</h5><EvidenceValue value={proposal.stateEffects.after} /></details>
  </section>;
}
