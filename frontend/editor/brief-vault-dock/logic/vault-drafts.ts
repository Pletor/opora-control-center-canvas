// Rozepsaný text ve Schránce (revize, rozdělení, nový kořen, odpověď, zpětná vazba, výzkum) se nesmí
// tiše ztratit, když člověk panel zavře nebo přepne sekci menu. Schránka si proto pamatuje pole, do
// kterých psal, a dokud je v některém neodeslaný text, hlásí rodiči `dirty`; rodič ji pak nechá
// namountovanou, jen skrytou, a po návratu je text na místě. Bez Reactu a bez DOM typů (test vedle).

/** Jen to z pole, na čem pravidlo stojí; `isConnected` = pole je pořád ve stránce. */
export type DraftField = { isConnected: boolean; value: string };
type FieldLike = { tagName?: string; type?: string };

const NOT_DRAFT = new Set(["search", "checkbox", "radio", "button", "submit", "reset", "range", "color", "file", "hidden"]);

/** Psaní do textového pole (ne hledání, ne přepínače) je rozepsaný text. */
export function isDraftField(target: unknown): boolean {
  const field = target as FieldLike | null;
  if (!field || typeof field.tagName !== "string") return false;
  const tag = field.tagName.toUpperCase();
  if (tag === "TEXTAREA") return true;
  return tag === "INPUT" && !NOT_DRAFT.has((field.type ?? "text").toLowerCase());
}

/** Pole, do kterého člověk psal, je pořád ve Schránce a není prázdné (odeslaný formulář zmizí nebo se vyprázdní). */
export function hasUnsavedDraft(fields: Iterable<DraftField>): boolean {
  for (const field of fields) if (field.isConnected && field.value.trim()) return true;
  return false;
}

/** Odeslaná nebo zmizelá pole se zapomenou, aby sada nerostla. */
export function pruneDrafts<T extends DraftField>(fields: Set<T>): void {
  for (const field of [...fields]) if (!field.isConnected || !field.value.trim()) fields.delete(field);
}

/** Schránka zůstane namountovaná, když je otevřená, nebo když v ní čeká rozepsaný text. */
export function keepVaultMounted(open: boolean, dirty: boolean): boolean {
  return open || dirty;
}
