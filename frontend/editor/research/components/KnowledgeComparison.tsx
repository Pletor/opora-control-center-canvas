import { sourceRoute, solutionVerificationLabel, type KnowledgeSolution, type SearchRetrieval, type SolutionComparison } from "../logic/knowledge-types";

export function RetrievalInfo({ value }: { value: SearchRetrieval | null }) {
 if (!value) return null;
 return <div aria-live="polite"><p>{value.used === "hybrid" ? "Hybridní hledání: význam, slova a skutečné vazby." : "Hledání podle slov; sémantické pořadí nebylo použito."}</p>
  <small>{value.candidatesRanked} z {value.candidates} kandidátů. Relevance není důkaz funkčního ověření.</small>
  {(value.truncated || value.candidatePassagesTruncated) && <p>Výběr nebo textové pasáže byly zkráceny. Zužte rozsah.</p>}
  <details><summary>Podrobnosti hledání</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>
 </div>;
}

export function SolutionFacts({ solution }: { solution: KnowledgeSolution }) {
 if (!solution.facts) return null;
 return <details><summary>Specifikace a vstupy řešení</summary>
  {solution.match && <p>Relevance: {solution.match.score.toFixed(3)} · slova {solution.match.lexical.toFixed(3)} · význam {solution.match.semantic?.toFixed(3) ?? "nepoužit"} · vazby {solution.match.graph.toFixed(3)}</p>}
  {solution.facts.specification ? <><p>Přijaté zadání {solution.facts.specification.acceptedRevision}, revize dokumentu {solution.facts.specification.revision}.</p><pre>{JSON.stringify(solution.facts.specification.fields, null, 2)}</pre>
   {!!solution.facts.specification.fieldsTruncated?.length && <p>Dlouhá pole jsou zkrácena; úplné zadání je u původního prvku.</p>}</> : <p>Přijatá specifikace není doložena.</p>}
  <ul>{solution.facts.inputs.map((input,index) => <li key={index}>{input.sourceName ? input.sourceName + " → " : ""}{input.name} · {input.relation}{input.requirement ? <pre>{JSON.stringify(input.requirement,null,2)}</pre> : null}</li>)}</ul>
  {(solution.snapshots?.length ?? 0)>1 && <ul>{solution.snapshots?.map(snapshot => <li key={snapshot.workspaceId}>{snapshot.workspaceId} · {solutionVerificationLabel(snapshot.verification)}</li>)}</ul>}
  {solution.facts.inputsTruncated && <p>Vstupy jsou zkráceny.</p>}
 </details>;
}

export default function KnowledgeComparison({ value }: { value: SolutionComparison | null }) {
 if (!value || (!value.differences.length && !value.commonSources.length)) return null;
 return <details><summary>Porovnat doložené rozdíly a společné zdroje</summary><p>Porovnání uložených hodnot; bez domýšlení architektury.</p>
  <ul>{value.commonSources.map(source => <li key={JSON.stringify(source)}><a href={sourceRoute(source)}>Společný zdroj {source.id} · revize {source.revision}</a></li>)}</ul>
  {value.differences.map(field => <details key={field.field}><summary>{field.field}</summary>{field.values.map(item => <div key={JSON.stringify(item.solutionRef)}><p>{item.solutionRef.projectId}/{item.solutionRef.nodeId} · {item.workspaceId}</p><pre>{JSON.stringify(item.value,null,2)}</pre></div>)}</details>)}
 </details>;
}
