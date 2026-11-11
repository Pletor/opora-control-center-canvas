// „1 prvek“, „3 prvky“, „5 prvků“: počet s českým tvarem [jeden, 2–4, ostatní]. Bez Reactu, test vedle.
export function czechCount(count: number, forms: [string, string, string]): string {
  const form = count === 1 ? forms[0] : count >= 2 && count <= 4 ? forms[1] : forms[2];
  return `${count} ${form}`;
}
