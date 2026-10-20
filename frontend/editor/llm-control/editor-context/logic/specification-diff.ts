export type SpecificationChange = { path: string; before: unknown; after: unknown; kind: "added" | "removed" | "changed" };

/** Compare captured JSON, with an explicit overflow signal rather than silently hiding changes. */
export function specificationDiff(before: unknown, after: unknown, limit = 100) {
  const changes: SpecificationChange[] = [];
  let truncated = false;
  const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
  const escape = (key: string) => key.replace(/~/g, "~0").replace(/\//g, "~1");
  function entities(values: unknown[], key: string) {
    const indexed = new Map<string, unknown>();
    for (const value of values) {
      if (!object(value)) return;
      const id = value[key];
      // The empty layer identifies the root drawing; entity IDs must be nonempty.
      if (typeof id !== "string" || (key !== "layer" && !id.trim()) || indexed.has(id)) return;
      indexed.set(id, value);
    }
    return indexed;
  }
  function walk(old: unknown, next: unknown, path: string) {
    if (Object.is(old, next)) return;
    if (object(old) && object(next)) {
      for (const key of [...new Set([...Object.keys(old), ...Object.keys(next)])].sort()) {
        walk(old[key], next[key], `${path}/${escape(key)}`);
      }
    } else if (Array.isArray(old) && Array.isArray(next)) {
      // Only these schema collections are unordered; navigation/pages and scene arrays are ordered.
      const key = path === "/graph/nodes" || path === "/graph/edges" ? "id"
        : path === "/cards" ? "nodeId" : path === "/drawings" ? "layer" : undefined;
      const oldEntities = key && entities(old, key);
      const nextEntities = key && entities(next, key);
      if (oldEntities && nextEntities) {
        for (const id of [...new Set([...oldEntities.keys(), ...nextEntities.keys()])].sort()) {
          walk(oldEntities.get(id), nextEntities.get(id), `${path}/${key}=${escape(id)}`);
        }
        return;
      }
      for (let index = 0; index < Math.max(old.length, next.length); index++) walk(old[index], next[index], `${path}/${index}`);
    } else {
      if (changes.length >= limit) { truncated = true; return; }
      changes.push({ path: path || "/", before: old, after: next, kind: old === undefined ? "added" : next === undefined ? "removed" : "changed" });
    }
  }
  walk(before, after, "");
  return { changes, truncated };
}
