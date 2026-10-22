// Payload kroku toku nese ukázku po změně (`sample`) a volitelně stejnou ukázku před ní (`before`).
// Rozdíl se ukazuje po listech JSON cesty: přidané zeleně, odebrané červeně, změněné obojím.
export type DiffStatus = "added" | "removed" | "changed" | "same";
export type DiffRow = { path: string; status: DiffStatus; before?: string; after?: string };

const MAX_ROWS = 200;
const isPlain = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);

/** Listy JSON hodnoty jako `cesta → text` (`a.b[0].c`); prázdný objekt či pole je list sám. */
export function flatten(value: unknown, path = "", out = new Map<string, string>(), depth = 0): Map<string, string> {
  if (out.size >= MAX_ROWS) return out;
  const children = Array.isArray(value) ? value.map((item, index) => [`${path}[${index}]`, item] as const)
    : isPlain(value) ? Object.entries(value).map(([key, item]) => [path ? `${path}.${key}` : key, item] as const) : null;
  if (!children || !children.length || depth >= 8) { out.set(path || "$", JSON.stringify(value) ?? "null"); return out; }
  for (const [child, item] of children) flatten(item, child, out, depth + 1);
  return out;
}

/** Řádky rozdílu v pořadí ukázky po změně, odebrané listy na konci. Bez `before` je vše `same`. */
export function payloadDiff(sample: unknown, before?: unknown): DiffRow[] {
  const after = flatten(sample);
  if (before === undefined) return [...after].map(([path, value]) => ({ path, status: "same", after: value }));
  const old = flatten(before), rows: DiffRow[] = [];
  for (const [path, value] of after) {
    const previous = old.get(path);
    rows.push(previous === undefined ? { path, status: "added", after: value }
      : previous === value ? { path, status: "same", before: previous, after: value } : { path, status: "changed", before: previous, after: value });
  }
  for (const [path, value] of old) if (!after.has(path)) rows.push({ path, status: "removed", before: value });
  return rows;
}
