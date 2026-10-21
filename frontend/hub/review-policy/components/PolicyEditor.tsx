import type { ReviewPolicyView } from "../logic/use-review-policy";
import type { PolicyRules as Rules } from "../logic/review-policy";
import PolicyRules from "./PolicyRules";

export default function PolicyEditor({ model }: { model: ReviewPolicyView }) {
  const { draft, edit, evidence } = model;
  const candidates = evidence.items.filter(item => item.snapshot.complete && item.snapshot.repository?.id);
  const selected = candidates.find(item => item.snapshot.id === draft.identityEvidenceId)?.snapshot;
  const detail = evidence.selected?.snapshot.id === draft.identityEvidenceId && !evidence.detailBusy && !evidence.detailError ? evidence.selected.snapshot : null;
  return <>
    <fieldset disabled={model.disabled} className="review-policy__editor"><legend>Nastavit novou revizi pravidel</legend>
      <label className="review-policy__field">Serverové pozorování pro identitu repozitáře
        <select aria-label="Serverové pozorování pro identitu repozitáře" value={draft.identityEvidenceId} onChange={event => edit({ identityEvidenceId: event.target.value })}>
          <option value="">Vyberte úplné pozorování z historie GitHub důkazů</option>
          {draft.identityEvidenceId && !candidates.some(item => item.snapshot.id === draft.identityEvidenceId) && <option value={draft.identityEvidenceId}>Dříve připnuté pozorování · {draft.identityEvidenceId}</option>}
          {candidates.map(item => <option key={item.snapshot.id} value={item.snapshot.id}>{item.snapshot.repository?.fullName} · PR #{item.snapshot.pr?.number ?? item.snapshot.prNumber} · {item.snapshot.id}</option>)}
        </select>
      </label>
      {selected && <p>Repozitář <strong>{selected.repository?.fullName}</strong> · ID {selected.repository?.id} · cílová větev <code>{selected.pr?.baseRef}</code>.</p>}
      {!candidates.length && <p>Nejprve v části GitHub důkazy načtěte úplné serverové pozorování PR.</p>}
      <h4>Povinné kontroly podle aplikace a přesného názvu</h4>
      {draft.checks.map((check, index) => <div className="review-policy__row" key={index}>
        <label className="review-policy__field">ID aplikace kontroly {index + 1}<input inputMode="numeric" value={check.appId} onChange={event => edit({ checks: draft.checks.map((item, i) => i === index ? { ...item, appId: event.target.value } : item) })} /></label>
        <label className="review-policy__field">Přesný název kontroly {index + 1}<input value={check.name} maxLength={255} onChange={event => edit({ checks: draft.checks.map((item, i) => i === index ? { ...item, name: event.target.value } : item) })} /></label>
        <button type="button" onClick={() => edit({ checks: draft.checks.filter((_, i) => i !== index) })}>Odebrat kontrolu {index + 1}</button>
      </div>)}
      <button type="button" disabled={draft.checks.length >= 32} onClick={() => edit({ checks: [...draft.checks, { appId: "", name: "" }] })}>Přidat povinnou kontrolu</button>
      {!!detail?.checks?.length && <label className="review-policy__field">Přidat kontrolu z vybraného pozorování<select aria-label="Přidat kontrolu z vybraného pozorování" value="" disabled={draft.checks.length >= 32} onChange={event => {
        const check = detail.checks?.[Number(event.target.value)]; if (check) edit({ checks: [...draft.checks.filter(item => item.appId || item.name), { appId: String(check.appId), name: check.name }] });
      }}><option value="">Vyberte přesnou dvojici</option>{detail.checks.map((check, index) => <option key={check.id} value={index}>{check.name} · aplikace {check.appId}</option>)}</select></label>}
      <p>ID aplikace a název kontroly nejsou důkazem identity workflow. Commit statusy se do povinných kontrol nezapočítávají.</p>
      <label className="review-policy__field">Povolená číselná ID účtů reviewerů<textarea value={draft.reviewerIds} onChange={event => edit({ reviewerIds: event.target.value })} placeholder="Například 12345, 67890" /></label>
      {!!detail?.reviews?.length && <details><summary>Účty v pozorovaných review</summary><ul>{detail.reviews.map(review => <li key={review.id}>{review.login} · ID <code>{review.userId}</code> · {review.userType}</li>)}</ul></details>}
      <div className="review-policy__row">
        <label className="review-policy__field">Minimum schválení kódu<input inputMode="numeric" value={draft.codeMinimum} onChange={event => edit({ codeMinimum: event.target.value })} /></label>
        <label className="review-policy__field">Minimum schválení zadání<input inputMode="numeric" value={draft.planMinimum} onChange={event => edit({ planMinimum: event.target.value })} /></label>
        <label className="review-policy__field">Platnost pozorování v sekundách<input inputMode="numeric" value={draft.age} onChange={event => edit({ age: event.target.value })} /></label>
      </div>
      <p>ID označují GitHub účty, nikoli nezávislé osoby. Jedno platné review může splnit schválení kódu i zadání; zadání vyžaduje přesný řádek Opora-Plan. Oprávněný požadavek změn blokuje splnění i od účtu mimo tento seznam.</p>
      <button type="button" onClick={() => model.prepare("activate")}>Zkontrolovat nové nastavení</button>
      {model.context?.policy?.enabled && <button type="button" onClick={() => model.prepare("disable")}>Připravit vypnutí pravidel</button>}
    </fieldset>
    {model.pending && <section className="review-policy__confirmation" aria-label="Potvrzení revize pravidel">
      <h3>{model.pending.action === "disable" ? "Vypnout pravidla novou historickou revizí" : "Aktivovat novou neměnnou revizi pravidel"}</h3>
      <p>Výchozí revize pro zápis: <code>{model.context?.policyHead ?? "první nastavení"}</code></p>
      {model.pending.action === "activate" ? <><p>Zdroj identity: <code>{draft.identityEvidenceId}</code> · {selected?.repository?.fullName ?? model.context?.policy?.repository.fullName} · ID {selected?.repository?.id ?? model.context?.policy?.repository.id} · větev {selected?.pr?.baseRef ?? model.context?.policy?.repository.baseBranch}</p>
        <PolicyRules rules={(model.pending.payload as { rules: Rules }).rules} /><p>Po aktivaci bude nutné načíst nové pozorování GitHubu. Dřívější důkazy nezískají aktuální platnost zpětně.</p></>
        : <p>Vypnutí zachová historii i dosavadní pravidla. Vypnutá pravidla nejsou splněná pravidla.</p>}
      <label className="review-policy__ack"><input type="checkbox" checked={model.confirmed} disabled={model.disabled} onChange={event => model.confirm(event.target.checked)} />Výslovně potvrzuji toto nastavení a uvedenou výchozí revizi.</label>
      <button type="button" disabled={model.disabled || !model.confirmed} onClick={model.save}>{model.pending.action === "disable" ? "Potvrdit vypnutí pravidel" : "Potvrdit aktivaci pravidel"}</button>
      <button type="button" disabled={model.busy} onClick={model.cancel}>Zrušit potvrzení</button>
    </section>}
  </>;
}
