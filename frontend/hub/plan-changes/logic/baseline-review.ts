/** Native receipt JSON sorts object keys; equality must preserve values, not key insertion order. */
export function samePinnedDocuments(left: unknown, right: unknown): boolean {
  const normalize = (value: unknown): unknown => Array.isArray(value) ? value.map(normalize)
    : value !== null && typeof value === "object"
      ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, normalize(item)]))
      : value;
  return JSON.stringify(normalize(left)) === JSON.stringify(normalize(right));
}
