type Field = { label: string; text: string };
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown): string => typeof value === "string" ? value : Array.isArray(value) && value.every(item => typeof item === "string") ? value.join("\n") : "";
/** Recognize the importer shapes only; original content always remains available verbatim. */
export function researchContent(content: string): Field[] | null {
  let value: unknown;
  try { value = JSON.parse(content); } catch { return null; }
  if (!object(value)) return null;
  const fields: Field[] = [];
  const add = (label: string, value: unknown) => { const valueText = text(value); if (valueText) fields.push({ label, text: valueText }); };
  if (typeof value.claim === "string" && typeof value.id === "string" && typeof value.kind === "string"
      && ["fact", "practice", "risk", "hypothesis", "inference"].includes(value.kind)) {
    add("Tvrzení", value.claim);
    add("Význam pro projekt", value.relevance);
    add("Důvod a souvislosti", value.reason);
    add("Citovaná pasáž", value.quote);
    add("Původní zdroj", value.source);
    add("Co ověřit", value.check);
    add("Časový úsek", value.timestamp);
    add("Revize zdroje", value.revision);
    return fields;
  }
  if (object(value.option) && typeof value.option.approach === "string") {
    add("Navržený postup", value.option.approach);
    add("Výhody", value.option.pros);
    add("Nevýhody a náklady", value.option.cons);
    add("Doporučení syntézy", value.recommended);
    add("Rizika", value.risks);
    if (Array.isArray(value.hypotheses)) for (const item of value.hypotheses) {
      if (object(item)) { add("Předpoklad k ověření", item.claim); add("Způsob ověření", item.check); }
    }
    add("Stav návrhu", value.approval);
    return fields;
  }
  return null;
}
