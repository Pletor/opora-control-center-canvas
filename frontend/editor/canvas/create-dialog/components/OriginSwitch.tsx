// Původ nové karty jako kompaktní segmentový přepínač na jeden řádek: Myšlenka · Existující zdroj ·
// Nový návrh. Zakázaná varianta zůstává vidět, jen zhasnutá, a v title řekne proč. Dílek drží jen
// zobrazení; volbu ohlásí nahoru přes onChoose a pravidla dostává hotová v `rules`.
import { useId } from "react";
import type { CreateForm, CreateOrigin, CreateRules } from "@/editor/canvas/create-dialog/logic/create-form";

type Origin = Exclude<CreateOrigin, null>;

export default function OriginSwitch({
  form,
  rules,
  onChoose,
}: {
  form: CreateForm;
  rules: CreateRules;
  onChoose: (origin: Origin) => void;
}) {
  const options: { origin: Origin; label: string; title: string; disabled?: string }[] = [
    { origin: "concept", label: "Myšlenka", title: "Jen funkce nebo myšlenka, bez souboru" },
    {
      origin: "existing",
      label: "Existující zdroj",
      title: "Navázat na složku nebo soubor v projektu",
      disabled: rules.existingAllowed ? undefined : "Sektor zatím nemá napojený existující zdroj.",
    },
    { origin: "planned", label: "Nový návrh", title: "Navrhnout nový zdroj; na disku se nic nevytváří" },
  ];
  const labelId = useId();
  return (
    <div className="create-dialog__group">
      <span className="create-dialog__label" id={labelId}>Původ</span>
      <div className="create-dialog__segment" role="radiogroup" aria-labelledby={labelId}>
        {options.map((option) => {
          const on = form.origin === option.origin;
          return (
            <button
              key={option.origin}
              type="button"
              role="radio"
              aria-checked={on}
              disabled={!!option.disabled}
              title={option.disabled ?? option.title}
              className={"create-dialog__segment-option" + (on ? " create-dialog__segment-option--on" : "")}
              onClick={() => onChoose(option.origin)}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
