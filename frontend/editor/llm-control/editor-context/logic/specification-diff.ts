export type SpecificationChange = { path: string; before: unknown; after: unknown; kind: "added" | "removed" | "changed" };

/** Compare captured JSON, with an explicit overflow signal rather than silently hiding changes. */
export function specificationDiff(before: unknown, after: unknown, limit = 100) {
  const changes: SpecificationChange[] = [];
  let truncated = false;
  const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
  function walk(old: unknown, next: unknown, path: string) {
    if (Object.is(old, next)) return;
    if (object(old) && object(next)) {
      for (const key of [...new Set([...Object.keys(old), ...Object.keys(next)])].sort()) {
        walk(old[key], next[key], `${path}/${key.replace(/~/g, "~0").replace(/\//g, "~1")}`);
      }
    } else if (Array.isArray(old) && Array.isArray(next)) {
      for (let index = 0; index < Math.max(old.length, next.length); index++) walk(old[index], next[index], `${path}/${index}`);
    } else {
      if (changes.length >= limit) { truncated = true; return; }
      changes.push({ path: path || "/", before: old, after: next, kind: old === undefined ? "added" : next === undefined ? "removed" : "changed" });
    }
  }
  walk(before, after, "");
  return { changes, truncated };
}
