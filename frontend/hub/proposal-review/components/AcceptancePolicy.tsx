import { useState } from "react";
import type { AcceptancePolicyView } from "../logic/use-acceptance-policy";
import type { AcceptancePolicy as Policy } from "../logic/proposal-review";
import "../styles/proposal-review.css";

function PolicyForm({ model }: { model: AcceptancePolicyView }) {
  const context = model.context!;
  const [enabled, setEnabled] = useState(context.policy?.enabled ?? false);
  const [threshold, setThreshold] = useState<Policy["rules"]["requireAcknowledgementFrom"]>(context.policy?.rules.requireAcknowledgementFrom ?? "elevated");
  const [block, setBlock] = useState(context.policy?.rules.blockOpenFindings ?? true);
  const disabled = model.busy || model.pending || !context.canConfigure || context.readOnly;
  return <form className="proposal-review__form" onSubmit={event => { event.preventDefault(); if (!disabled) void model.configure({ enabled, rules: { requireAcknowledgementFrom: threshold, blockOpenFindings: block } }); }}>
    <label><input type="checkbox" checked={enabled} disabled={disabled} onChange={event => setEnabled(event.target.checked)} />Aktivovat pravidla přijetí plánů</label>
    <label>Vyžadovat výslovné potvrzení od rizika<select value={threshold} disabled={disabled} onChange={event => setThreshold(event.target.value as typeof threshold)}>
      <option value="standard">Běžné a vyšší</option><option value="elevated">Zvýšené a kritické</option><option value="critical">Pouze kritické</option><option value="none">Žádné povinné potvrzení</option></select></label>
    <label><input type="checkbox" checked={block} disabled={disabled} onChange={event => setBlock(event.target.checked)} />Otevřené blokující nálezy brání přijetí</label>
    <button type="submit" disabled={disabled}>{model.pending ? "Ukládám pravidla…" : "Uložit novou revizi pravidel přijetí"}</button>
  </form>;
}
export default function AcceptancePolicy({ model }: { model?: AcceptancePolicyView }) {
  if (!model) return <p role="status">Pravidla přijetí plánů nejsou dostupná. Splnění není doloženo.</p>;
  return <section className="proposal-review" aria-label="Pravidla přijetí plánů"><header><h2>Pravidla přijetí plánů</h2><button type="button" disabled={model.pending} onClick={model.refresh}>Obnovit pravidla přijetí</button></header>
    <p>Samostatná pravidla lidského přijetí návrhů Canvasu. Pravidla GitHub PR review a povinných kontrol zůstávají oddělená.</p>
    {model.error && <p role="alert">{model.error}</p>}{model.busy && <p role="status">Načítám pravidla přijetí…</p>}
    {model.context ? <><p>{model.context.policy?.enabled ? "Pravidla přijetí jsou aktivní." : "Pravidla přijetí nejsou aktivní; dosavadní lidské přijetí zůstává zachované."}</p>
      <code>{model.context.policyHead ?? "Žádná uložená revize pravidel"}</code><p>Každá změna pravidel zneplatní stará potvrzení. Lokální jména nejsou počtem nezávislých hlasů.</p>
      <PolicyForm key={model.context.policyHead ?? "absent"} model={model} />
      <section className="proposal-review__bootstrap"><h3>První zadání · výjimka bootstrap</h3><p>{model.context.bootstrapException}</p><p>Jen pokud nikdy neexistovala přijatá historie daného scope. Výjimka uloží vlastní doklad; neopravňuje přijmout pozdější návrh.</p></section>
      {!model.context.canConfigure && <p>Nastavení může změnit pouze člověk v zapisovatelném prostoru.</p>}</>
      : !model.busy && <p>Podklady pravidel nejsou dostupné. Nejde o potvrzení vypnuté politiky.</p>}
  </section>;
}
