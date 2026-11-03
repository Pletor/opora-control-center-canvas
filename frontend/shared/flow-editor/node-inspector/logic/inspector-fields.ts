// Pole inspektoru z parametrů uzlu. Registr zatím nenese schéma parametrů, proto druh pole určuje hodnota:
// číslo → číselné pole, logická hodnota → zaškrtávátko, text → text, ostatní (null, seznam, objekt) → JSON.
// Zápis se ověří tady, takže chybné číslo ani rozbitý JSON se do grafu nedostanou. Zobecněno ze Studia MODEL
// (`parameterRows` / `parseParameter`).
export type FieldKind = "number" | "boolean" | "text" | "json";
export type FieldRow = { key: string; kind: FieldKind; raw: string };
export type Parsed = { value: unknown } | { error: string };

export function kindOf(value: unknown): FieldKind {
  if (typeof value === "number") return "number";
  if (typeof value === "boolean") return "boolean";
  if (typeof value === "string") return "text";
  return "json";
}

export function fieldRows(params: Record<string, unknown> | undefined): FieldRow[] {
  return Object.entries(params ?? {}).sort(([a], [b]) => a.localeCompare(b)).map(([key, value]) => {
    const kind = kindOf(value);
    return { key, kind, raw: kind === "json" ? JSON.stringify(value) : String(value) };
  });
}

export function parseField(kind: FieldKind, raw: string): Parsed {
  if (kind === "text") return { value: raw };
  if (kind === "boolean") return { value: raw === "true" };
  if (kind === "number") {
    const value = Number(raw.trim().replace(",", "."));
    return raw.trim() && Number.isFinite(value) ? { value } : { error: "Zadejte číslo." };
  }
  try { return { value: JSON.parse(raw) }; } catch { return { error: "Neplatný JSON." }; }
}

/** Nový parametr: klíč bez mezer, hodnota jako JSON, jinak jako text. */
export function parseNewParam(key: string, raw: string, existing: Record<string, unknown> | undefined): { key: string; value: unknown } | { error: string } {
  const name = key.trim();
  if (!/^[A-Za-z_][\w-]*$/.test(name)) return { error: "Klíč: písmena, číslice, _ a -." };
  if (existing && name in existing) return { error: "Parametr už existuje." };
  try { return { key: name, value: JSON.parse(raw) }; } catch { return { key: name, value: raw }; }
}

/** `input_ref` / `output_ref` je JSON text; ukáže se odsazený, nečitelný se ukáže doslova. */
export function prettyRef(ref: string | null | undefined): string {
  if (ref === null || ref === undefined || ref === "") return "";
  try { return JSON.stringify(JSON.parse(ref), null, 2); } catch { return ref; }
}
