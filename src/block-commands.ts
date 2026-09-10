/** Bloky jsou pohled na text uzlu, ne druhé úložiště: parse a serialize jsou inverzní. */
export type Block = { id: string; depth: number; text: string };
export const MAX_DEPTH = 8;

let counter = 0;
function nextId() {
  counter += 1;
  return "b" + counter;
}

function lineDepth(line: string) {
  let depth = 0;
  let rest = line;
  for (;;) {
    if (rest.startsWith("\t")) {
      rest = rest.slice(1);
      depth += 1;
    } else if (rest.startsWith("  ")) {
      rest = rest.slice(2);
      depth += 1;
    } else break;
  }
  if (rest.startsWith("- ")) rest = rest.slice(2);
  else if (rest === "-") rest = "";
  return { depth, text: rest };
}

/** Text uzlu → bloky. Skok o víc než jednu úroveň se srovná, aby strom zůstal platný. */
export function parseBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  for (const line of (text ?? "").split("\n")) {
    const { depth, text: content } = lineDepth(line);
    const limit = Math.min(depth, MAX_DEPTH, blocks.length ? blocks[blocks.length - 1].depth + 1 : 0);
    blocks.push({ id: nextId(), depth: limit, text: content });
  }
  return blocks.length ? blocks : [{ id: nextId(), depth: 0, text: "" }];
}

export function serializeBlocks(blocks: Block[]): string {
  return blocks.map((b) => "\t".repeat(b.depth) + "- " + b.text).join("\n");
}

/** Nový sourozenec pod blokem; text za kurzorem se přenese do nového bloku. */
export function insertSibling(blocks: Block[], index: number, caret: number) {
  const current = blocks[index];
  const head = current.text.slice(0, caret);
  const tail = current.text.slice(caret);
  const created: Block = { id: nextId(), depth: current.depth, text: tail };
  const next = [...blocks];
  next[index] = { ...current, text: head };
  next.splice(index + 1, 0, created);
  return { blocks: next, focus: created.id, caret: 0 };
}

/** Zanoření jen pod existujícího předchůdce: kořen ani cyklus nevznikne. */
export function indentBlock(blocks: Block[], index: number) {
  if (index === 0) return null;
  const limit = Math.min(blocks[index - 1].depth + 1, MAX_DEPTH);
  if (blocks[index].depth >= limit) return null;
  const delta = limit - blocks[index].depth;
  return shift(blocks, index, delta);
}

export function outdentBlock(blocks: Block[], index: number) {
  if (blocks[index].depth === 0) return null;
  return shift(blocks, index, -1);
}

/** Podstrom se posune s rodičem, aby zůstala zachovaná hierarchie. */
function shift(blocks: Block[], index: number, delta: number) {
  const depth = blocks[index].depth;
  const next = [...blocks];
  next[index] = { ...next[index], depth: depth + delta };
  for (let i = index + 1; i < next.length && next[i].depth > depth; i += 1)
    next[i] = { ...next[i], depth: Math.max(0, Math.min(MAX_DEPTH, next[i].depth + delta)) };
  return next;
}

export function removeBlock(blocks: Block[], index: number) {
  if (blocks.length <= 1 || index === 0) return null;
  const next = blocks.filter((_, i) => i !== index);
  return { blocks: next, focus: next[index - 1].id, caret: next[index - 1].text.length };
}

export type SlashCommand = {
  id: string;
  label: string;
  hint: string;
  /** Vrací nový text bloku, nebo null u příkazů řešených mimo text. */
  apply: (text: string) => string | null;
};

/** Malá lokální paleta: každý příkaz má viditelnou klávesovou zkratku. */
export const SLASH_COMMANDS: SlashCommand[] = [
  { id: "sibling", label: "Nový blok", hint: "Enter", apply: (t) => t },
  { id: "indent", label: "Zanořit blok", hint: "Tab", apply: () => null },
  { id: "outdent", label: "Vynořit blok", hint: "Shift+Tab", apply: () => null },
  { id: "link", label: "Odkaz na uzel", hint: "[[", apply: (t) => t + "[[" },
  { id: "task", label: "Úkol", hint: "TODO", apply: (t) => "TODO " + t },
  { id: "decision", label: "Rozhodnutí", hint: "ROZHODNUTÍ", apply: (t) => "ROZHODNUTÍ: " + t },
  { id: "evidence", label: "Důkaz / odkaz na zdroj", hint: "DŮKAZ", apply: (t) => "DŮKAZ: " + t },
  { id: "agent", label: "Připravit úkol pro agenta", hint: "Ctrl+Enter", apply: () => null },
];

/** Text mezi posledním "[[" a kurzorem; null když se odkaz zrovna nepíše. */
export function linkQuery(text: string, caret: number): string | null {
  const head = text.slice(0, caret);
  const open = head.lastIndexOf("[[");
  if (open < 0) return null;
  const query = head.slice(open + 2);
  if (query.includes("]]") || query.includes("\n")) return null;
  return query;
}

export function completeLink(text: string, caret: number, name: string) {
  const open = text.slice(0, caret).lastIndexOf("[[");
  if (open < 0) return { text, caret };
  const inserted = "[[" + name + "]]";
  const value = text.slice(0, open) + inserted + text.slice(caret);
  return { text: value, caret: open + inserted.length };
}

/** Rozdělení bloku na text a odkazy pro bezpečné vykreslení (bez HTML). */
export function linkParts(text: string): { text: string; link: boolean }[] {
  const parts: { text: string; link: boolean }[] = [];
  const pattern = /\[\[([^[\]\n]{1,160})\]\]/g;
  let last = 0;
  for (let match = pattern.exec(text); match; match = pattern.exec(text)) {
    if (match.index > last) parts.push({ text: text.slice(last, match.index), link: false });
    parts.push({ text: match[1], link: true });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last), link: false });
  return parts;
}
