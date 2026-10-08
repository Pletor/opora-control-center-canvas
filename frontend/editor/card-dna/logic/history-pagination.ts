/** Stránkuje lokálním kurzorem až do konce, nikoli zastaralou React closure.
 * Chyba se předá rodiči; již přijaté stránky zůstávají a neúplnost nezmizí.
 */
export async function drainHistoryPages<C, P extends { next: C | null }>(
  first: C | null, read: (cursor: C) => Promise<P | null>, append: (page: P) => void, active: () => boolean,
) {
  let cursor = first;
  const seen = new Set<string>();
  while (cursor !== null && active()) {
    const key = JSON.stringify(cursor);
    if (seen.has(key)) throw new Error("Kurzor historie se opakuje.");
    seen.add(key);
    const page = await read(cursor);
    if (!page || !active()) return;
    append(page); cursor = page.next;
  }
}
