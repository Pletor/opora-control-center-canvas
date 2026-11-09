import { useState } from "react";
import type { ResearchCard, ResearchHeader, ResearchScope } from "../logic/research-types";
import { decisionEvidence, decisionHubUrl, newResearchTask } from "../logic/research-decision";
import { useResearchDecision } from "../logic/use-research-decision";
import ResearchDecisionTasks from "./ResearchDecisionTasks";
import ResearchReviewProposals from "./ResearchReviewProposals";
import "../styles/research-decision.css";

type Props = { scope: ResearchScope; card: ResearchCard; cards: ResearchHeader[]; nodeNames: Map<string, string>; readOnly: boolean; onOpenNode: (id: string) => void };
export default function ResearchDecision({ scope, card, cards, nodeNames, readOnly, onOpenNode }: Props) {
  const state = useResearchDecision(scope, card.id);
  const [problemId, setProblemId] = useState(""); const [evidenceIds, setEvidenceIds] = useState<string[]>([]);
  const [rationale, setRationale] = useState(""); const [assumptions, setAssumptions] = useState(""); const [constraints, setConstraints] = useState("");
  const [tasks, setTasks] = useState(() => [newResearchTask()]); const [existing, setExisting] = useState(card.refs.nodeIds.length > 0);
  const review = state.reviews.find(item => item.id === state.selected);
  const evidence = decisionEvidence(cards);
  const disabled = readOnly || card.archived || state.busy;
  const currentReviewed = state.reviews.some(item => item.decision.revision === card.revision);
  const selectedEvidence = evidence.filter(item => evidenceIds.includes(item.id));
  return <section className="research-decision" aria-label="Rozhodnutí a realizační úkoly">
    <h3>Od rozhodnutí k úkolům</h3>
    <p>Nejprve člověk potvrdí podloženou rozhodovací cestu. Návrh úkolů následně projde samostatným přijetím v OporaHubu.</p>
    {state.busy && <p role="status">Načítám nebo ukládám rozhodovací cestu…</p>}
    {state.error && <p role="alert">{state.error}</p>}
    {readOnly && <p>Tento pohled je pouze ke čtení.</p>}
    <ResearchReviewProposals key={JSON.stringify([scope.project, scope.workspace, card.id])} scope={scope} decisionId={card.id} readOnly={readOnly || card.archived} onReviewed={state.receivedReview} />
    {!!state.reviews.length && <label>Zaznamenané posouzení<select value={state.selected} disabled={state.busy} onChange={event => void state.select(event.target.value)}>
      {state.reviews.map(item => <option key={item.id} value={item.id}>Revize {item.decision.revision} · {new Date(item.reviewedAt).toLocaleString("cs-CZ")}</option>)}
      {!currentReviewed && !readOnly && <option value="">Posoudit aktuální revizi {card.revision}</option>}
    </select></label>}
    {review ? <>
      <p className="research-decision__status">Člověk posoudil rozhodnutí · revize {review.decision.revision}</p>
      <dl><dt>Původní problém</dt><dd>{review.problem.title} · revize {review.problem.revision}</dd>
        <dt>Proč tato varianta</dt><dd>{review.rationale}</dd>
        <dt>Předpoklady</dt><dd>{review.assumptions || "Neuvedeny"}</dd>
        <dt>Omezení</dt><dd>{review.constraints || "Neuvedena"}</dd>
        <dt>Ověřené podklady</dt><dd>{review.evidence.map(item => <div key={item.id}>{item.title} · revize {item.revision}</div>)}</dd>
      </dl>
      {state.proposal ? <div className="research-decision__proposal">
        <h4>{state.proposal.accepted ? "Úkoly přijaty v OporaHubu" : state.proposal.pending ? "Příprava návrhu čeká na dokončení" : "Návrh úkolů čeká na přijetí v OporaHubu"}</h4>
        <p>{state.proposal.accepted ? `Přijatá revize zadání: ${state.proposal.acceptedRevision}` : "Záznam posouzení ani tento návrh dosud nemění přijatý plán."}</p>
        {state.proposal.tasks.map(task => <article key={task.ref}><strong>{task.title}</strong><p>{task.goal}</p><p>Dokončeno, když: {task.acceptance}</p>
          {state.proposal?.accepted && state.proposal.nodeIds?.[task.ref] && <button type="button" onClick={() => onOpenNode(state.proposal!.nodeIds![task.ref])}>Otevřít úkol ve Struktuře</button>}
        </article>)}
        <a href={decisionHubUrl(scope)}>Otevřít OporaHub k posouzení návrhu</a>
        <button type="button" disabled={state.busy} onClick={() => void state.refresh()}>Ověřit stav přijetí</button>
        {state.proposal.accepted && <button type="button" disabled={disabled} onClick={() => void state.reconcile()}>Propojit podklady s přijatými úkoly</button>}
        {state.proposal.pending && <button type="button" disabled={disabled} onClick={() => void state.propose(state.proposal!.tasks)}>Dokončit přípravu stejného návrhu</button>}
      </div> : <ResearchDecisionTasks tasks={tasks} existing={existing} nodeNames={nodeNames} disabled={disabled || !!state.error}
        allowNew={!review.decision.refs.nodeIds.length} onChange={setTasks} onMode={value => { setExisting(value); setTasks(items => items.map(item => ({ ...item, nodeId: undefined, parentId: undefined, dependsOn: [] }))); }}
        onSubmit={() => void state.propose(tasks)} />}
    </> : !state.busy && !state.error && <form className="research-decision__form" onSubmit={event => {
      event.preventDefault(); if (disabled || !selectedEvidence.length) return;
      void state.review({ decisionId: card.id, decisionRevision: card.revision, problemId,
        evidence: selectedEvidence.map(item => ({ id: item.id, revision: item.revision })), rationale, assumptions, constraints });
    }}><fieldset disabled={disabled}><legend>Potvrdit podloženou cestu · revize {card.revision}</legend>
      <label>Původní otázka<select required value={problemId} onChange={event => setProblemId(event.target.value)}>
        <option value="">Vyberte řešený problém</option>{cards.filter(item => item.kind === "question" && !item.archived).map(item => <option key={item.id} value={item.id}>{item.title}</option>)}
      </select></label>
      <fieldset><legend>Podklady, které rozhodnutí dokládají</legend>
        {!evidence.length && <p>Nejdříve připojte ověřené zjištění nebo doložené pozorování se zdrojem.</p>}
        {evidence.map(item => <label className="research-decision__check" key={item.id}><input type="checkbox" checked={evidenceIds.includes(item.id)} onChange={event => setEvidenceIds(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))} />{item.title} · revize {item.revision}</label>)}
      </fieldset>
      <label>Proč volíme tuto variantu<textarea required maxLength={8000} value={rationale} onChange={event => setRationale(event.target.value)} /></label>
      <label>Známé předpoklady<textarea maxLength={8000} value={assumptions} onChange={event => setAssumptions(event.target.value)} /></label>
      <label>Omezení a co návrh neřeší<textarea maxLength={8000} value={constraints} onChange={event => setConstraints(event.target.value)} /></label>
      <p>Potvrzení uloží přesné verze rozhodnutí, problému a podkladů. Přijetí realizačního plánu zůstává v OporaHubu.</p>
      <button type="submit" disabled={!problemId || !selectedEvidence.length || !rationale.trim()}>Potvrzuji podloženou rozhodovací cestu</button>
    </fieldset></form>}
  </section>;
}
