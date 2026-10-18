// „Další čekající“ (docs/kancelar.md §2): první klik vybere nejstarší čekající relaci, každý další
// tu za právě vybranou; za poslední se vrací na začátek. Vybraná relace, která už nečeká, začne znovu.
export function nextWaiting(waiting: readonly { id: string }[], currentId: string | null): string | null {
  if (!waiting.length) return null;
  const index = currentId ? waiting.findIndex((w) => w.id === currentId) : -1;
  return waiting[(index + 1) % waiting.length].id;
}
