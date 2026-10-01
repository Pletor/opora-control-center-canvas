// Stav pohledu kapitol v módu Text, bez Reactu: které kapitoly jsou rozbalené a které už mají
// připojený editor. Připojený editor se po sbalení neodpojí, jen skryje — `NodeTextEditor` při
// odpojení neuloží rozepsaný text. Proto `mounted` jen roste (`withMounted`), dokud se nezmění vrstva.
// Množiny jsou neměnné: každá změna vrací novou `ReadonlySet`, vstup zůstává, jak byl.

export type ChapterView = { expanded: ReadonlySet<string>; mounted: ReadonlySet<string> };

const EMPTY: ReadonlySet<string> = new Set<string>();

/** Výchozí pohled vrstvy: vše sbalené, nic připojené. */
export const EMPTY_CHAPTER_VIEW: ChapterView = { expanded: EMPTY, mounted: EMPTY };

export function toggleChapter(set: ReadonlySet<string>, id: string): ReadonlySet<string> {
  const next = new Set(set);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

export function expandAll(ids: Iterable<string>): ReadonlySet<string> {
  return new Set(ids);
}

export function collapseAll(): ReadonlySet<string> {
  return new Set<string>();
}

/** Sjednocení: co je rozbalené, je i připojené. Bez nového id vrátí původní `mounted`. */
export function withMounted(mounted: ReadonlySet<string>, expanded: ReadonlySet<string>): ReadonlySet<string> {
  let next: Set<string> | null = null;
  for (const id of expanded) {
    if (mounted.has(id)) continue;
    next ??= new Set(mounted);
    next.add(id);
  }
  return next ?? mounted;
}

/** Nový pohled po změně rozbalení; připojené editory zůstávají. */
export function viewWithExpanded(view: ChapterView, expanded: ReadonlySet<string>): ChapterView {
  return { expanded, mounted: withMounted(view.mounted, expanded) };
}

/** Kolik z daných kapitol je rozbalených (pro „rozbaleno X z Y“). */
export function expandedCount(ids: readonly string[], expanded: ReadonlySet<string>): number {
  return ids.filter((id) => expanded.has(id)).length;
}
