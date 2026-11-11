// Zvýraznění JSON pro rub karty bez innerHTML: text se rozdělí na tokeny (klíč, řetězec, číslo/literál, zbytek)
// a React je vykreslí jako <span>. Tvar dat se nepředpokládá, rub ukáže cokoli, co node-brief vrátí.
export type JsonToken = { text: string; kind: "key" | "str" | "num" | "plain" };

const TOKEN = /("(?:\\.|[^"\\])*")(\s*:)?|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\btrue\b|\bfalse\b|\bnull\b)/g;

export function jsonTokens(value: unknown): JsonToken[] {
  const text = JSON.stringify(value, null, 2) ?? "null";
  const tokens: JsonToken[] = [];
  let last = 0;
  for (const match of text.matchAll(TOKEN)) {
    const at = match.index ?? 0;
    if (at > last) tokens.push({ text: text.slice(last, at), kind: "plain" });
    if (match[1] && match[2]) tokens.push({ text: match[1], kind: "key" }, { text: match[2], kind: "plain" });
    else if (match[1]) tokens.push({ text: match[1], kind: "str" });
    else tokens.push({ text: match[3], kind: "num" });
    last = at + match[0].length;
  }
  if (last < text.length) tokens.push({ text: text.slice(last), kind: "plain" });
  return tokens;
}
