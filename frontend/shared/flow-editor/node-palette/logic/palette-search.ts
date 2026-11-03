// Společné jádro palet: hledání po slovech (každé slovo musí být v textu položky) a seskupení položek do skupin ve
// zvoleném pořadí. Paletu toků (`palette.ts`) i katalog Studia MODEL (`studio-model-palette`) skládá tohle jádro;
// každá z nich dodá jen své položky a svůj text k hledání.
export const searchWords = (query: string): string[] => query.trim().toLowerCase().split(/\s+/).filter(Boolean);

export const matchesWords = (haystack: string, words: readonly string[]): boolean => {
  const text = haystack.toLowerCase();
  return words.every((word) => text.includes(word));
};

/** Skupiny v daném pořadí (`order`), skupiny mimo pořadí za nimi abecedně; prázdné skupiny se vynechají. */
export function groupInOrder<T extends { group: string }>(items: readonly T[], order: readonly string[]): { id: string; items: T[] }[] {
  const extra = [...new Set(items.map((item) => item.group).filter((group) => !order.includes(group)))].sort();
  return [...order, ...extra].map((id) => ({ id, items: items.filter((item) => item.group === id) })).filter((group) => group.items.length > 0);
}
