import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { knowledgeIdentity, sourceRoute, solutionVerificationLabel, solutionVerificationDetail, type KnowledgeRecord, type KnowledgeSolution, type SearchRetrieval, type SolutionComparison } from "../logic/knowledge-types";
import { VERIFICATION_LABELS } from "../logic/research-model";
import KnowledgeDetails from "./KnowledgeDetails";
import KnowledgeComparison, { RetrievalInfo, SolutionFacts } from "./KnowledgeComparison";

type ProjectOption = { id: string; name: string };
export default function KnowledgePanel({ project, workspace, nodeId, projects }: { project: string; workspace: string; nodeId: string | null; projects: ProjectOption[] }) {
 const [records, setRecords] = useState<KnowledgeRecord[]>([]);
 const [results, setResults] = useState<KnowledgeRecord[]>([]);
 const [solutions, setSolutions] = useState<KnowledgeSolution[]>([]);
 const [retrieval, setRetrieval] = useState<SearchRetrieval | null>(null);
 const [comparison, setComparison] = useState<SolutionComparison | null>(null);
 const [resultType, setResultType] = useState("solution");
 const [bounds, setBounds] = useState("project");
 const [contextTruncated, setContextTruncated] = useState(false);
 const [searchTruncated, setSearchTruncated] = useState(false);
 const [error, setError] = useState(""); const [query, setQuery] = useState(""); const [busy, setBusy] = useState(false);
 const [selected, setSelected] = useState<string[]>([project]);
 const [verification, setVerification] = useState("");
 const [workspaces, setWorkspaces] = useState<Record<string,string>>({ [project]: workspace });
 const scope = { project, workspace, scopeNodeId: nodeId ?? "" };
 const generation = useRef(0);
 useEffect(() => { generation.current++; setRecords([]); setResults([]); setSolutions([]); setRetrieval(null); setComparison(null); setError(""); return () => { generation.current++; }; }, [project, workspace, nodeId]);
 usePolling(async () => {
   const ticket = generation.current;
   try { const data = await api<{records: KnowledgeRecord[]; truncated: boolean}>("/api/research/context?" + new URLSearchParams(scope)); if (ticket === generation.current) { setRecords(data.records); setContextTruncated(data.truncated); } }
   catch (reason) { if (ticket === generation.current) setError(String(reason)); }
 }, { intervalMs: 10000, refreshKeys: [project, workspace, nodeId] });
 async function search() {
  setBusy(true); setError("");
  const ticket = generation.current;
  try { const value = await api<{results?: KnowledgeRecord[]; solutions?: KnowledgeSolution[]; truncated: boolean; retrieval?: SearchRetrieval; comparison?: SolutionComparison}>("/api/research/knowledge-search", { project, workspace, query, resultType,
    scopes: selected.map(id => ({ project: id, workspace: workspaces[id] || "main", ...(id === project && bounds !== "project" ? { scopeNodeId: nodeId ?? "", includeDescendants: bounds === "subtree" } : {}) })), kinds: [], verification: resultType === "research" && verification ? [verification] : [], limit: 30 }); if (ticket === generation.current) { setResults(value.results ?? []); setSolutions(value.solutions ?? []); setSearchTruncated(value.truncated); setRetrieval(value.retrieval ?? null); setComparison(value.comparison ?? null); } }
  catch (reason) { setError(String(reason)); } finally { setBusy(false); }
 }
 async function attach(record: KnowledgeRecord) {
  setBusy(true); setError("");
  try { await api("/api/research/bindings", { ...scope, source: record.canonicalRef, expectedRevision: 0, archived: false });
   const value = await api<{records: KnowledgeRecord[]}>("/api/research/context?" + new URLSearchParams(scope)); setRecords(value.records); }
  catch (reason) { setError(String(reason)); } finally { setBusy(false); }
 }
 const row = (record: KnowledgeRecord, canAttach: boolean) => <li key={knowledgeIdentity(record.canonicalRef)}>
  <a href={sourceRoute(record.canonicalRef)}>{record.card.title}</a>{" · "}{record.canonicalRef.projectId}/{record.canonicalRef.workspaceId}{" · r"}{record.canonicalRef.revision}
  <p>{record.card.summary}</p>
  <KnowledgeDetails source={record.canonicalRef} />
  <small>{record.contexts.map(context => context.relation === "parent" ? "Kontext rodiče" : context.relation === "shared" ? "Sdílený podklad" : "Lokální podklad").join(", ")}{" · Podklad: "}{VERIFICATION_LABELS[record.verification.status]}{record.verification.method ? " · " + record.verification.method : ""}</small>
  {canAttach && <button type="button" disabled={busy || records.some(item => knowledgeIdentity(item.canonicalRef) === knowledgeIdentity(record.canonicalRef))} onClick={() => void attach(record)}>Připojit ke kontextu</button>}
 </li>;
 return <details className="research-knowledge" open><summary>Paměť projektu a sdílené podklady</summary>
  {records.length > 0 && <ul>{records.map(record => row(record, false))}</ul>}
  <fieldset><legend>Hledat řešení v dostupných projektech</legend>
   <select aria-label="Druh výsledků" value={resultType} onChange={event => setResultType(event.target.value)}><option value="solution">Řešení podle prvků</option><option value="research">Podklady</option></select>
   <select aria-label="Rozsah hledání" value={bounds} onChange={event => setBounds(event.target.value)}><option value="project">Celý projekt</option><option value="scope">Aktuální kontext</option><option value="subtree">Kontext a podstrom</option></select>
   {projects.map(option => <label key={option.id}><input type="checkbox" checked={selected.includes(option.id)} onChange={event => setSelected(ids => event.target.checked ? [...ids, option.id] : ids.filter(id => id !== option.id))} />{option.name}
    {selected.includes(option.id) && <input aria-label={"Pracovní prostor " + option.name} value={workspaces[option.id] || "main"} onChange={event => setWorkspaces(old => ({...old, [option.id]: event.target.value}))} />}</label>)}
   <input type="search" aria-label="Hledat řešení" value={query} onChange={event => setQuery(event.target.value)} placeholder="Přihlášení, organizace, rozhodnutí…" />
   <select aria-label="Ověření podkladu" value={verification} onChange={event => setVerification(event.target.value)}><option value="">Všechny stavy ověření</option>{Object.entries(VERIFICATION_LABELS).map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select>
   <button type="button" disabled={busy || !query.trim() || !selected.length} onClick={() => void search()}>Hledat</button>
  </fieldset>
  {error && <p role="alert">{error}</p>}
  {(contextTruncated || searchTruncated) && <p>Výběr je zkrácený. Zúžte rozsah nebo dotaz.</p>}
  <RetrievalInfo value={retrieval} />
  <KnowledgeComparison value={comparison} />
  <ul>{results.map(record => row(record, true))}</ul>
  <ul>{solutions.map(solution => <li key={JSON.stringify(solution.solutionRef)}>
   <a href={"/?" + new URLSearchParams({screen: "canvas", mode: "structure", project: solution.solutionRef.projectId, workspace: solution.snapshot.workspaceId, layer: solution.solutionRef.nodeId})}>{solution.title}</a> · {solution.solutionRef.projectId}
   <p>{solution.purpose}</p><small title={solutionVerificationDetail(solution.verification)}>Funkční ověření: {solutionVerificationLabel(solution.verification)} · {solution.evidence.length} souvisejících podkladů</small>
   <SolutionFacts solution={solution} />
   <ul>{solution.evidence.map(record => row(record, true))}</ul>
  </li>)}</ul>
 </details>;
}
