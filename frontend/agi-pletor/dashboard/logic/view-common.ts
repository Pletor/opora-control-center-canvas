export type Raw = Record<string, unknown>;
export const rec = (value: unknown): Raw => (value && typeof value === "object" && !Array.isArray(value) ? (value as Raw) : {});
export const list = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
export const str = (value: unknown): string => (typeof value === "string" ? value : typeof value === "number" ? String(value) : "");
/** `{error}` sekce → text „nedostupné: …“, jinak prázdný řetězec. */
export const unavailable = (value: unknown): string => {
  const error = rec(value).error;
  return error === undefined ? "" : `nedostupné: ${typeof error === "string" ? error : JSON.stringify(error)}`;
};
