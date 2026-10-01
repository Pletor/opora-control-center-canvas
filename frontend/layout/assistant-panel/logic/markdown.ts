/**
 * Bezpečný základní Markdown odpovědi asistenta: text → struktura bloků a inline uzlů. Žádné HTML:
 * značky jako `<b>` zůstávají textem, protože dílek `Markdown.tsx` skládá jen React prvky.
 * Parser snese rozepsaný text během streamování: neuzavřený `**`, `` ` `` nebo blok kódu se
 * ukáže jako obyčejný text (resp. kód do konce), nikdy nerozbije rozvržení.
 */

export type Inline =
  | { type: "text"; text: string }
  | { type: "strong"; children: Inline[] }
  | { type: "em"; children: Inline[] }
  | { type: "code"; text: string }
  | { type: "link"; text: string; href: string }
  | { type: "break" };

export type ListItem = { depth: number; children: Inline[] };

export type Block =
  | { type: "heading"; level: 1 | 2 | 3 | 4; children: Inline[] }
  | { type: "paragraph"; children: Inline[] }
  | { type: "code"; lang: string; text: string }
  | { type: "list"; ordered: boolean; start: number; items: ListItem[] }
  | { type: "quote"; children: Inline[] }
  | { type: "rule" };

const FENCE = /^\s*(```|~~~)\s*([\w+-]*)\s*$/;
const HEADING = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
const RULE = /^\s*([-*_])(\s*\1){2,}\s*$/;
const BULLET = /^(\s*)[-*+]\s+(.*)$/;
const ORDERED = /^(\s*)(\d{1,9})[.)]\s+(.*)$/;
const QUOTE = /^\s*>\s?(.*)$/;

function pushText(out: Inline[], text: string) {
  if (!text) return;
  const last = out[out.length - 1];
  if (last && last.type === "text") last.text += text;
  else out.push({ type: "text", text });
}

/** Najde uzavírací značku, která není hned za mezerou a nezačíná prázdným obsahem. */
function closing(source: string, marker: string, from: number): number {
  if (source[from] === " " || source.startsWith(marker, from)) return -1;
  let at = source.indexOf(marker, from);
  while (at >= 0 && source[at - 1] === " ") at = source.indexOf(marker, at + 1);
  return at;
}

/** Inline uzly jednoho řádku textu (řádky odstavce spojí `break`). */
export function parseInline(source: string): Inline[] {
  const out: Inline[] = [];
  let i = 0;
  while (i < source.length) {
    const ch = source[i];
    if (ch === "\\" && i + 1 < source.length && /[\\`*_[\]#>-]/.test(source[i + 1])) {
      pushText(out, source[i + 1]);
      i += 2;
      continue;
    }
    if (ch === "`") {
      const end = source.indexOf("`", i + 1);
      if (end > i + 1) {
        out.push({ type: "code", text: source.slice(i + 1, end) });
        i = end + 1;
        continue;
      }
    }
    if (source.startsWith("**", i) || source.startsWith("__", i)) {
      const marker = source.slice(i, i + 2);
      const end = closing(source, marker, i + 2);
      if (end > i + 2) {
        out.push({ type: "strong", children: parseInline(source.slice(i + 2, end)) });
        i = end + 2;
        continue;
      }
      pushText(out, marker);
      i += 2;
      continue;
    }
    if (ch === "*" || (ch === "_" && !/\w/.test(source[i - 1] ?? ""))) {
      const end = closing(source, ch, i + 1);
      if (end > i + 1 && !(ch === "_" && /\w/.test(source[end + 1] ?? ""))) {
        out.push({ type: "em", children: parseInline(source.slice(i + 1, end)) });
        i = end + 1;
        continue;
      }
    }
    if (ch === "[") {
      const link = /^\[([^\]]+)\]\(([^)\s]+)\)/.exec(source.slice(i));
      if (link) {
        out.push({ type: "link", text: link[1], href: link[2] });
        i += link[0].length;
        continue;
      }
    }
    pushText(out, ch);
    i += 1;
  }
  return out;
}

function lines(texts: string[]): Inline[] {
  const out: Inline[] = [];
  texts.forEach((text, index) => {
    if (index > 0) out.push({ type: "break" });
    out.push(...parseInline(text.trim()));
  });
  return out;
}

function listMarker(line: string): { ordered: boolean; indent: number; number: number; text: string } | null {
  const bullet = BULLET.exec(line);
  if (bullet) return { ordered: false, indent: bullet[1].length, number: 1, text: bullet[2] };
  const ordered = ORDERED.exec(line);
  if (ordered) return { ordered: true, indent: ordered[1].length, number: Number(ordered[2]), text: ordered[3] };
  return null;
}

const startsBlock = (line: string) =>
  FENCE.test(line) || HEADING.test(line) || RULE.test(line) || QUOTE.test(line) || listMarker(line) !== null;

/** Celý text odpovědi → bloky. */
export function parseMarkdown(source: string): Block[] {
  const rows = source.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;
  while (i < rows.length) {
    const line = rows[i];
    if (!line.trim()) { i++; continue; }

    const fence = FENCE.exec(line);
    if (fence) {
      const body: string[] = [];
      i++;
      // Neuzavřený blok (streamování) běží do konce textu.
      while (i < rows.length && !(rows[i].trim() === fence[1])) body.push(rows[i++]);
      i++;
      blocks.push({ type: "code", lang: fence[2], text: body.join("\n") });
      continue;
    }
    const heading = HEADING.exec(line);
    if (heading) {
      const level = Math.min(heading[1].length, 4) as 1 | 2 | 3 | 4;
      blocks.push({ type: "heading", level, children: parseInline(heading[2]) });
      i++;
      continue;
    }
    if (RULE.test(line)) { blocks.push({ type: "rule" }); i++; continue; }

    if (QUOTE.test(line)) {
      const body: string[] = [];
      while (i < rows.length && QUOTE.test(rows[i])) body.push(QUOTE.exec(rows[i++])![1]);
      blocks.push({ type: "quote", children: lines(body) });
      continue;
    }

    const first = listMarker(line);
    if (first) {
      const base = first.indent;
      const items: { depth: number; texts: string[] }[] = [];
      while (i < rows.length) {
        const row = rows[i];
        const marker = listMarker(row);
        if (marker && (marker.indent > base || marker.ordered === first.ordered)) {
          items.push({ depth: marker.indent > base ? 1 : 0, texts: [marker.text] });
          i++;
          continue;
        }
        // Pokračovací řádek položky: odsazený nebo navazující text bez prázdného řádku.
        if (row.trim() && !marker && items.length && !startsBlock(row)) {
          items[items.length - 1].texts.push(row);
          i++;
          continue;
        }
        if (!row.trim() && i + 1 < rows.length) {
          const next = listMarker(rows[i + 1]);
          if (next && next.ordered === first.ordered) { i++; continue; }
        }
        break;
      }
      blocks.push({
        type: "list",
        ordered: first.ordered,
        start: first.number,
        items: items.map((item) => ({ depth: item.depth, children: lines(item.texts) })),
      });
      continue;
    }

    const body: string[] = [];
    while (i < rows.length && rows[i].trim() && (body.length === 0 || !startsBlock(rows[i]))) body.push(rows[i++]);
    blocks.push({ type: "paragraph", children: lines(body) });
  }
  return blocks;
}
