import type { JourneyAction, JourneyVia, PageSection } from "@/shared/types/logic/types";
import { VIA_TEXT_MAX, viaActions } from "../logic/journey-via";

/** „Jak sem přijde“ v kartě kroku: akce zákazníka (první krok jen otevření stránky), u kliku a odeslání sekce stránky
 * předchozího kroku (výběr z jejích `site.sections`, sekci, kterou stránka nemá, nechá jako „chybí sekce …“) a text
 * tlačítka. Každou změnu hlásí celým novým signálem nahoru (`undefined` = signál neurčen). */
export default function JourneyStepVia({ index, via, sections, disabled, testId, onChange }: {
  index: number; via: JourneyVia | undefined; sections: PageSection[]; disabled: boolean;
  testId: (part: string) => string; onChange: (via: JourneyVia | undefined) => void;
}) {
  const action = (value: string) => onChange(value ? { ...(via ?? {}), do: value as JourneyAction } : undefined);
  const known = !via?.section || sections.some((section) => section.id === via.section);
  return <fieldset className="domain-map__step-via" disabled={disabled}>
    <legend className="domain-map__step-via-title">Jak sem přijde</legend>
    <select aria-label="Akce zákazníka" data-testid={testId("via-do")} value={via?.do ?? ""} onChange={(event) => action(event.target.value)}>
      <option value="">neurčeno</option>
      {viaActions(index).map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
    </select>
    {via && via.do !== "open" && <>
      <select aria-label="Sekce předchozí stránky" data-testid={testId("via-section")} value={via.section ?? ""}
        onChange={(event) => onChange({ ...via, section: event.target.value || undefined })}>
        <option value="">kdekoli na předchozí stránce</option>
        {sections.map((section) => <option key={section.id} value={section.id}>v sekci {section.name}</option>)}
        {!known && <option value={via.section}>chybí sekce {via.section}</option>}
      </select>
      <input maxLength={VIA_TEXT_MAX} aria-label="Text tlačítka nebo odkazu" placeholder={via.do === "submit" ? "Text tlačítka, např. Odeslat poptávku" : "Text odkazu, např. Chci video zdarma"}
        data-testid={testId("via-text")} value={via.text ?? ""} onChange={(event) => onChange({ ...via, text: event.target.value || undefined })}/>
    </>}
  </fieldset>;
}
