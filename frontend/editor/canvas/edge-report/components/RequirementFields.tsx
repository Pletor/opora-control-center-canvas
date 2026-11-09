import type { InputRequirement, RequirementTestCase } from "@/shared/types/logic/types";

const emptyCase = (): RequirementTestCase => ({ stepId: "", check: "", command: "" });
export default function RequirementFields({ value, disabled, onChange }: {
  value?: InputRequirement; disabled: boolean; onChange: (value: InputRequirement) => void;
}) {
  const draft = value ?? { readiness: "design", revision: 0 };
  const updateCase = (role: "positive" | "negative", field: keyof RequirementTestCase, text: string) => {
    const verification = draft.verification ?? { positive: emptyCase(), negative: emptyCase() };
    onChange({ ...draft, verification: { ...verification, [role]: { ...verification[role], [field]: text } } });
  };
  return <fieldset disabled={disabled}>
    <legend>Požadovaná připravenost vstupu</legend>
    {!value && <p>Požadavek zatím není určený. Spuštění zdrojové karty bude blokované.</p>}
    <label className="field">Úroveň vstupu
      <select aria-label="Úroveň vstupu" value={value?.readiness ?? ""} onChange={event => {
        const readiness = event.target.value as InputRequirement["readiness"];
        onChange({ readiness, revision: draft.revision,
          ...(readiness === "verified" ? { verification: draft.verification ?? { positive: emptyCase(), negative: emptyCase() } } : {}) });
      }}>
        <option value="" disabled>Vyberte úroveň</option>
        <option value="design">Přijatý návrh</option><option value="implemented">Začleněná realizace</option>
        <option value="verified">Ověřená realizace</option>
      </select>
    </label>
    <label className="field">Přijatá revize zadání cílové karty
      <input aria-label="Přijatá revize vstupu" type="number" min={0} step={1} value={draft.revision}
        onChange={event => onChange({ ...draft, revision: Number(event.target.value) })} />
    </label>
    {draft.readiness === "verified" && (["positive", "negative"] as const).map(role => <fieldset key={role}>
      <legend>{role === "positive" ? "Kladný integrační scénář" : "Záporný integrační scénář"}</legend>
      {(["stepId", "check", "command"] as const).map(field => <label className="field" key={field}>
        {field === "stepId" ? "ID přijatého testovacího kroku" : field === "check" ? "Název kontroly" : "Přesný příkaz"}
        <input value={draft.verification?.[role][field] ?? ""} maxLength={field === "command" ? 1000 : 160}
          onChange={event => updateCase(role, field, event.target.value)} />
      </label>)}
    </fieldset>)}
  </fieldset>;
}
