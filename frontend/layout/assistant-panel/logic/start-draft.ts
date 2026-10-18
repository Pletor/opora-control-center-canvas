// Předvyplněná zpráva u úkolu založeného zvenku: do prázdného pole se vloží, rozepsaný text člověka
// se nikdy nepřepíše. Zpráva se neposílá, model běží jen na zprávu člověka (docs/asistent.md).
export function applyStartDraft(current: string | undefined, draft: string | undefined): string {
  const existing = current ?? "";
  if (existing.trim() !== "") return existing;
  return draft && draft.trim() !== "" ? draft : existing;
}
