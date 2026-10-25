/** Accepted specification extensions remain intact through editors of the text fields. */
export function harnessOf(fields: object | null | undefined): unknown {
  return (fields as { harness?: unknown } | null | undefined)?.harness ?? null;
}
function canonical(value: unknown): string {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)
    .map(([key, item]) => JSON.stringify(key) + ':' + canonical(item)).join(',') + '}';
  return JSON.stringify(value) ?? 'null';
}
export function harnessChanged(before: object | null | undefined, after: object | null | undefined): boolean {
  return canonical(harnessOf(before)) !== canonical(harnessOf(after));
}
