// Markdown sticky poznámky do bloků pro React (bez vkládání HTML, text se nikdy nevykoná). Poznámka na plátně potřebuje
// málo: nadpisy `#`–`###` (rámec „# Workflow 1 — Ingest“, krok „## Titulek“), odrážky, odstavce a v řádku **tučně**
// a `kód`. Ostatní syntaxe zůstane doslova.
export type NoteInline = { text: string; strong?: boolean; code?: boolean };
export type NoteBlock = { kind: "heading"; level: 1 | 2 | 3; inline: NoteInline[] } | { kind: "item"; inline: NoteInline[] } | { kind: "paragraph"; inline: NoteInline[] };

export function noteInline(text: string): NoteInline[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/).filter(Boolean).map((part) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4 ? { text: part.slice(2, -2), strong: true }
      : part.startsWith("`") && part.endsWith("`") && part.length > 2 ? { text: part.slice(1, -1), code: true } : { text: part });
}

export function noteBlocks(source: string): NoteBlock[] {
  return source.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line): NoteBlock => {
    const heading = line.match(/^(#{1,3})\s+(.*)$/);
    if (heading) return { kind: "heading", level: heading[1].length as 1 | 2 | 3, inline: noteInline(heading[2]) };
    const item = line.match(/^[-*]\s+(.*)$/);
    return item ? { kind: "item", inline: noteInline(item[1]) } : { kind: "paragraph", inline: noteInline(line) };
  });
}
