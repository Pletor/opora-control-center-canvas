// Výzva nad prázdným plátnem: kdy se ukáže, co odešle Enter a příklady zadání. Čisté funkce bez Reactu.

export const EXAMPLES = [
  "Formulář s výškou a váhou, kontrola, výpočet BMI, uložení do DB a notifikace",
  "Přihlášení uživatele: formulář, ověření hesla, vytvoření relace",
  "Nahrání dokumentu a jeho zařazení do RAG",
] as const;

/** Výzva stojí uprostřed jen u plátna bez uzlu, mimo přehrávání a když srdce právě nekreslí. */
export const showsEmptyPrompt = (nodeCount: number, playing: boolean, drawing: boolean): boolean => nodeCount === 0 && !playing && !drawing;

/** Text k odeslání (oříznutý), nebo null, když je pole prázdné nebo se už odesílá. */
export const promptText = (text: string, busy: boolean): string | null => (busy || !text.trim() ? null : text.trim());

/** Enter odešle, Shift+Enter dělá nový řádek (a Enter uprostřed psaní diakritiky přes IME nic neodešle). */
export const enterSubmits = (event: { key: string; shiftKey: boolean; isComposing?: boolean }): boolean => event.key === "Enter" && !event.shiftKey && !event.isComposing;
