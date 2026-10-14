// Konflikty složeného pohledu (docs/domeny-a-worktree.md §4): uzel obsahu prostoru má stejné ID jako
// uzel architektury, ale jinou podobu (`architecture`), nebo ho architektura mezitím odstranila
// (`removed`). Backend ho ve složeném grafu skryje (vyhrává architektura); UI to musí říct nahlas.

export type ViewConflict = { id: string; name: string; reason: string };

const text = (value: unknown) => (typeof value === "string" ? value : "");

/** Odpověď `/api/view` na bezpečný seznam; položky bez ID se zahodí, ID jen jednou. */
export function normalizeConflicts(raw: unknown): ViewConflict[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const items: ViewConflict[] = [];
  for (const value of raw) {
    const item = value && typeof value === "object" ? value as Record<string, unknown> : {};
    const id = text(item.id);
    if (!id || seen.has(id)) continue;
    seen.add(id);
    items.push({ id, name: text(item.name), reason: text(item.reason) || "architecture" });
  }
  return items;
}

const label = (item: ViewConflict) => (item.name ? `„${item.name}“ (${item.id})` : item.id);

/** Jedna věta na konflikt, aby člověk věděl, který uzel a proč. */
export function conflictLine(item: ViewConflict): string {
  if (item.reason === "removed") return `Uzel ${label(item)} byl z architektury projektu odstraněn, v tomto worktree ale zůstal.`;
  return `Uzel ${label(item)} má v tomto worktree jinou podobu než v architektuře projektu.`;
}
