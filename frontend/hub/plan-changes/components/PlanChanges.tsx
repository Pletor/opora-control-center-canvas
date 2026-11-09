import type { PlanChangesView } from "../logic/use-plan-changes";
import HarnessKit from '@/shared/harness-kit/components/HarnessKit';
import ProposalReview from "@/hub/proposal-review/components/ProposalReview";
import { reviewReady } from "@/hub/proposal-review/logic/proposal-review";
import type { ProposalReviewView } from "@/hub/proposal-review/logic/use-proposal-review";
import type { AcceptancePolicyView } from "@/hub/proposal-review/logic/use-acceptance-policy";
import { changedFields, inspectedFields, fieldKeys, fieldLabels, fieldLimits } from "../logic/plan-changes";
import "../styles/plan-changes.css";

export default function PlanChanges({ model, review, acceptancePolicy }: { model: PlanChangesView; review?: ProposalReviewView; acceptancePolicy?: AcceptancePolicyView }) {
  const disabled = model.busy || model.readOnly || !model.context;
  const accepted = model.context?.acceptedDocuments.find(item => item.nodeId === model.document?.nodeId);
  const changed = !!accepted && !!model.document && !!model.fields && (changedFields(model.document.fields, model.fields).length > 0 || changedFields(accepted.fields, model.fields).length > 0);
  return <section className="plan-changes" aria-label="Změny zadání" aria-busy={model.busy}>
    <header className="plan-changes__head"><div><h2>Změny zadání</h2>
      <p>Návrh mění zadání až po výslovném přijetí do Canvasu.</p></div>
      <button type="button" onClick={model.refresh} disabled={model.busy}>Obnovit a zahodit rozepsané změny</button>
    </header>
    {model.busy && <p role="status">Načítám…</p>}
    {model.error && <p role="alert" className="plan-changes__error">{model.error}</p>}
    {model.notice && <p role="status">{model.notice}</p>}
    {model.readOnly && <p>Prostor je jen pro čtení. Pro návrhy otevřete pracovní prostor.</p>}
    {model.context && <>
      <p>Přijatá revize zadání: <code>{model.context.acceptedHead?.slice(0, 12) ?? "zatím nezaložena"}</code></p>
      <label className="plan-changes__field">Důvod změny nebo založení základu
        <input value={model.subject} maxLength={200} disabled={disabled || !!model.baselineId}
          onChange={event => model.setSubject(event.target.value)} placeholder="Proč má být zadání změněno?" />
      </label>
      {!model.context.acceptedHead ? <div className="plan-changes__baseline">
        {model.baselineId && <p>Uložený návrh základu: <code>{model.baselineId}</code>. Přijetí použije přesně připnuté zadání.</p>}
        {model.baselineId && !model.preparationMatches && <p role="alert">Připnutý základ se neshoduje s aktuálním zadáním. Nelze jej přijmout; připravte nový návrh.</p>}
        {acceptancePolicy?.context?.policy?.enabled && <p>Aktivní pravidla: první základ může použít pouze výslovnou bootstrap výjimku bez dřívější přijaté historie. Uloží vlastní doklad; nejde o schválení pozdějších návrhů.</p>}
        <h3>Výchozí zadání</h3><p>První přijetí zahrne všechna níže uvedená uložená zadání tohoto prostoru. Prohlédněte jejich obsah.</p>
        {!model.context.documents.length && <p>Nejprve vytvořte v Canvasu oblast, sektor nebo uzel. Prázdný základ nelze založit.</p>}
        {(model.baselineId ? model.preparation?.documents ?? [] : model.context.documents).map(document => <details key={document.nodeId} className="plan-changes__document">
          <summary>{model.name(document.nodeId)} · revize {document.revision}</summary>
          {fieldKeys.map(field => <div key={field}><h4>{fieldLabels[field]}</h4><pre>{document.fields[field] || "(prázdné)"}</pre></div>)}
          <HarnessKit after={document.fields} />
        </details>)}
        <button type="button" disabled={disabled || !model.subject.trim() || !model.context.documents.length || !model.preparationMatches}
          onClick={model.baseline}>Přijmout tato uložená zadání jako výchozí základ</button>
      </div> : <>
        {model.context.workingDiffers && <p className="plan-changes__warning">Uložená zadání v Canvasu se liší od přijaté revize. Editor níže ukazuje uložené zadání. Návrh umožní přijmout jednotlivou upravenou kartu; další souběžnou změnu dotčené karty server odmítne. Žádná pracovní změna se zde nepřijímá automaticky.</p>}
        {model.document && model.fields ? <div className="plan-changes__editor">
          <label className="plan-changes__field">Karta (přepnutí zahodí rozepsanou úpravu)
            <select value={model.document.nodeId} disabled={model.busy} onChange={event => model.selectDocument(event.target.value)}>
              {model.documents.map(document => <option key={document.nodeId} value={document.nodeId}>{model.name(document.nodeId)}</option>)}
            </select>
          </label>
          <p>Výchozí revize karty {model.document.revision}. Texty upravujete pouze v návrhu.</p>
          {!accepted && <p className="plan-changes__warning">Tato karta vznikla až po založení základu. Přidávání karet do přijatého plánu vyžaduje další etapu verzování grafu; nyní ji nelze navrhnout.</p>}
          {fieldKeys.map(field => <label className="plan-changes__field" key={field}>{fieldLabels[field]}
            <textarea rows={field === "goal" ? 3 : 4} value={model.fields![field]} maxLength={fieldLimits[field]}
              disabled={disabled} onChange={event => model.edit(field, event.target.value)} />
          </label>)}
          <button type="button" disabled={disabled || !changed || !model.subject.trim()} onClick={model.propose}>Uložit návrh změny</button>
        </div> : model.missingDocument ? <p role="alert" className="plan-changes__warning">Vybraná karta <code>{model.missingDocument}</code> není v načteném kontextu zadání. Obnovte podklady tlačítkem výše; jiná karta se místo ní nevybere.</p> : <p>Tento prostor neobsahuje zadání karet.</p>}
      </>}
    </>}
    <h3>Návrhy změn</h3>
    {!model.items.length && <p>Zatím žádné návrhy změn zadání.</p>}
    <ul className="plan-changes__list">{model.items.map(item => <li key={item.id}>
      <button type="button" disabled={model.busy} onClick={() => model.inspect(item.id)} aria-pressed={model.inspected?.id === item.id}>{item.subject}</button>
      <span>{item.by.name} · {new Date(item.createdAt).toLocaleString("cs-CZ")} · {item.accepted ? "Přijato do zadání" : "Navrženo"}</span>
    </li>)}</ul>
    {model.inspected && <section className="plan-changes__inspection" aria-label="Obsah návrhu změny">
      <h3>{model.inspected.subject}</h3><p>Návrh <code>{model.inspected.id.slice(0, 12)}</code> vychází z <code>{model.inspected.parentRevision.slice(0, 12)}</code>.</p>
      {model.inspected.changes.map(change => <article key={change.nodeId}>
        <h4>{model.name(change.nodeId)} · výchozí revize {change.expectedRevision}</h4>
        <HarnessKit before={change.acceptedBefore.fields} after={change.fields} mode="diff" />
        <HarnessKit after={change.before} />
        {inspectedFields(change).map(field => <div key={field}>
          <h5>{fieldLabels[field]}</h5><div className="plan-changes__comparison">
            <div><strong>Přijaté zadání</strong><pre>{change.acceptedBefore.fields[field] || "(prázdné)"}</pre></div>
            <div><strong>Uložené pracovní zadání</strong><pre>{change.before[field] || "(prázdné)"}</pre></div>
            <div><strong>Navržené zadání</strong><pre>{change.fields[field] || "(prázdné)"}</pre></div>
          </div>
        </div>)}
      </article>)}
      <p>Přijetí zapíše právě tento návrh do zadání Canvasu. Nejde o nezávislé review ani ověření kódu.</p>
      {model.context?.acceptedHead && model.inspected.parentRevision !== model.context.acceptedHead && !model.inspected.accepted && <button type="button" disabled={disabled} onClick={model.rebase}>Vytvořit nový návrh nad aktuální přijatou revizí</button>}
      <ProposalReview model={review} proposalKind="spec" proposalId={model.inspected.id} acceptedHead={model.context?.acceptedHead ?? null} />
      <button type="button" disabled={disabled || !model.context?.acceptedHead || model.inspected.accepted || model.inspected.parentRevision !== model.context.acceptedHead || !reviewReady(review, { proposalKind: "spec", proposalId: model.inspected.id }, model.context?.acceptedHead ?? null)} onClick={model.accept}>Přijmout zobrazený návrh do zadání</button>
    </section>}
  </section>;
}
