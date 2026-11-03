// Malý převod markdownu brand booku na strom bloků pro náhled. Bez HTML: náhled skládá React prvky, takže text
// z README se nikdy nevykoná. Umí to, co brand book potřebuje: nadpisy, odstavce, odrážky a číslované seznamy,
// citace, bloky kódu, oddělovač a v řádku tučné, kurzívu, kód a odkazy (jen http(s), mailto, relativní a #).

export type Inline = { kind: "text" | "code" | "strong" | "em"; text: string } | { kind: "link"; text: string; href: string };
export type Block =
  | { kind: "heading"; level: number; inline: Inline[] }
  | { kind: "paragraph"; inline: Inline[] }
  | { kind: "quote"; inline: Inline[] }
  | { kind: "list"; ordered: boolean; items: Inline[][] }
  | { kind: "code"; text: string }
  | { kind: "rule" };

const INLINE = /(`[^`]+`)|(\*\*[^*]+\*\*|__[^_]+__)|(\*[^*\s][^*]*\*|_[^_\s][^_]*_)|(\[[^\]]+\]\([^)\s]+\))/;

export function safeHref(href: string): string | null {
  return /^(https?:\/\/|mailto:|#|\/|\.{0,2}\/)/i.test(href) || /^[\w.-]+(\/|$)/.test(href) && !/^[a-z][a-z0-9+.-]*:/i.test(href) ? href : null;
}

export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  let rest = text;
  while (rest) {
    const match = rest.match(INLINE);
    if (!match || match.index === undefined) { out.push({ kind: "text", text: rest }); break; }
    if (match.index) out.push({ kind: "text", text: rest.slice(0, match.index) });
    const token = match[0];
    if (match[1]) out.push({ kind: "code", text: token.slice(1, -1) });
    else if (match[2]) out.push({ kind: "strong", text: token.slice(2, -2) });
    else if (match[3]) out.push({ kind: "em", text: token.slice(1, -1) });
    else {
      const [, label, href] = token.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/)!;
      const safe = safeHref(href);
      out.push(safe ? { kind: "link", text: label, href: safe } : { kind: "text", text: label });
    }
    rest = rest.slice(match.index + token.length);
  }
  return out;
}

const LIST = /^\s*([-*+]|\d+[.)])\s+(.*)$/;

export function parseMarkdown(source: string): Block[] {
  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) { index++; continue; }
    if (line.startsWith("```")) {
      const body: string[] = [];
      for (index++; index < lines.length && !lines[index].startsWith("```"); index++) body.push(lines[index]);
      blocks.push({ kind: "code", text: body.join("\n") }); index++; continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) { blocks.push({ kind: "heading", level: heading[1].length, inline: parseInline(heading[2].trim()) }); index++; continue; }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { blocks.push({ kind: "rule" }); index++; continue; }
    if (line.startsWith(">")) {
      const body: string[] = [];
      for (; index < lines.length && lines[index].startsWith(">"); index++) body.push(lines[index].replace(/^>\s?/, ""));
      blocks.push({ kind: "quote", inline: parseInline(body.join(" ")) }); continue;
    }
    const item = line.match(LIST);
    if (item) {
      const ordered = /\d/.test(item[1]);
      const items: Inline[][] = [];
      for (; index < lines.length && LIST.test(lines[index]); index++) items.push(parseInline(lines[index].match(LIST)![2]));
      blocks.push({ kind: "list", ordered, items }); continue;
    }
    const body: string[] = [];
    for (; index < lines.length && lines[index].trim() && !/^(#{1,6}\s|```|>)/.test(lines[index]) && !LIST.test(lines[index]); index++) body.push(lines[index].trim());
    blocks.push({ kind: "paragraph", inline: parseInline(body.join(" ")) });
  }
  return blocks;
}
