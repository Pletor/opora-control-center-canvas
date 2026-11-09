import { useEffect, useRef, useState } from "react";
import type { ResearchScope } from "../logic/research-types";
import type { DecisionReview } from "../logic/research-decision";
import { useReviewProposals, type ReviewPreparation } from "../logic/use-review-proposals";
import { reviewRoute } from "../logic/review-route";

export function PreparedReviewContent({ item }: { item: ReviewPreparation }) {
  const snapshot = item.snapshot;
  return <><dl><dt>Proč tato varianta</dt><dd>{snapshot.rationale}</dd><dt>Předpoklady</dt><dd>{snapshot.assumptions || "Neuvedeny"}</dd>
    <dt>Omezení</dt><dd>{snapshot.constraints || "Neuvedena"}</dd></dl>
    {[snapshot.problem, snapshot.decision, ...snapshot.evidence].map((card, index) => <details key={`${index}:${card.id}`} open={index < 2}>
      <summary>{index === 0 ? "Otázka" : index === 1 ? "Rozhodnutí" : "Podklad"}: {card.title} · revize {card.revision}</summary>
      <p>{card.summary}</p><pre style={{ whiteSpace: "pre-wrap" }}>{card.content}</pre>
      {card.sources.map((source, n) => <blockquote key={n}><p>{source.quote}</p><cite>{source.title} · {source.ref}</cite>
        <p>{source.location} {source.revision} · {source.verification?.status ?? card.verification.status}</p></blockquote>)}
    </details>)}</>;
}

export default function ResearchReviewProposals({ scope, decisionId, readOnly, onReviewed }: {
  scope: ResearchScope; decisionId: string; readOnly: boolean; onReviewed: (value: DecisionReview) => void;
}) {
  const model = useReviewProposals(scope, decisionId, onReviewed);
  const [checked, setChecked] = useState("");
  const requested = reviewRoute(window.location.search, scope);
  const linked = requested?.card === decisionId ? requested : null;
  const target = linked ? model.items.find(item => item.id === linked.id && item.digest === linked.digest) : null;
  const targetElement = useRef<HTMLElement | null>(null);
  useEffect(() => { targetElement.current?.scrollIntoView({ block: "nearest" }); }, [target?.id]);
  return <section aria-label="Návrhy posouzení rešerše"><h4>Připravená posouzení</h4>
    <p>Agent připravil podklady. Potvrzení člověkem zaznamená rozhodovací cestu; nepřijímá realizační plán ani nespouští práci.</p>
    <button type="button" disabled={model.busy} onClick={model.refresh}>Obnovit připravená posouzení</button>
    {model.error && <p role="alert">{model.error}</p>}
    {linked && !model.busy && !target && <p role="alert">Přesný odkazovaný návrh nebo jeho otisk není dostupný. Jiný návrh ho nenahrazuje.</p>}
    {model.busy && <p role="status">Načítám posouzení…</p>}
    {!model.busy && !model.items.length && <p>Žádné připravené posouzení.</p>}
    {model.items.map(item => <article key={item.id} data-review-id={item.id} ref={item === target ? targetElement : undefined}>
      {item === target && <p role="status">Odkazované posouzení · přesný otisk ověřen</p>}
      <h5>{item.snapshot.decision.title} · {item.status === "pending" ? "Čeká na člověka" : item.status === "accepted" ? "Člověk potvrdil" : "Zamítnuto"}</h5>
      <p>Navrhl {item.by.name || item.by.kind} · <code>{item.id}</code></p><PreparedReviewContent item={item} />
      {item.status === "pending" && <><label><input type="checkbox" disabled={readOnly || model.busy} checked={checked === item.id}
        onChange={event => setChecked(event.target.checked ? item.id : "")} />Zkontroloval/a jsem přesné znění rozhodnutí a podklady tohoto návrhu.</label>
        <button type="button" disabled={readOnly || model.busy || checked !== item.id} onClick={() => void model.decide(item, "accept")}>Potvrdit připravené posouzení</button>
        <button type="button" disabled={readOnly || model.busy} onClick={() => void model.decide(item, "reject")}>Zamítnout připravené posouzení</button></>}
    </article>)}
  </section>;
}
