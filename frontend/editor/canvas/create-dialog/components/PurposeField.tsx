// Jediné pole „Popis“ (podstata karty, ukládá se do `purpose` vždy). Co do něj patří, napoví
// placeholder podle původu: u myšlenky co má část umět, u návrhu jeho podstata (sektor nejméně 12
// znaků), u existujícího zdroje a projektu bez volby původu je popis nepovinný. Jen zobrazení;
// změnu textu hlásí nahoru přes onChange.
import { MIN_SECTOR_PURPOSE, type CreateForm, type CreateRules } from "@/editor/canvas/create-dialog/logic/create-form";

function hint(form: CreateForm, rules: CreateRules): { placeholder: string; required: boolean } {
  if (rules.concept) return { placeholder: "Co má tato část umět? Vlastními slovy, bez souboru.", required: true };
  if (form.origin === "planned" && rules.requiresModeChoice)
    return form.kind === "sector"
      ? { placeholder: `Podstata návrhu sektoru, nejméně ${MIN_SECTOR_PURPOSE} znaků.`, required: true }
      : { placeholder: "Co má navrhovaný zdroj dělat.", required: true };
  return { placeholder: "Proč karta existuje.", required: false };
}

export default function PurposeField({
  form,
  rules,
  onChange,
}: {
  form: CreateForm;
  rules: CreateRules;
  onChange: (purpose: string) => void;
}) {
  const { placeholder, required } = hint(form, rules);
  return (
    <label className="field">
      <span>Popis {!required && <span className="create-dialog__optional">(nepovinné)</span>}</span>
      <textarea aria-label="Popis" rows={3} maxLength={2000} required={required} placeholder={placeholder}
        value={form.purpose} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}
