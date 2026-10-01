/** Jak blok vypadá, ne co je zač: nadpis, značka na začátku řádku a odkazy [[…]].
 *  Čistý pohled na text — text bloku se tu nikdy nemění, jen se čte, aby ho řádek uměl nakreslit. */
import { linkParts } from "@/editor/node-detail/content/logic/block-commands";

export type LinkTarget = { id: string; name: string; kind: string };
export type BlockMark = "todo" | "done" | "decision" | "evidence" | null;
export type BlockLook = { heading: 0 | 1 | 2 | 3; mark: BlockMark };

/** Značky, které píše paleta příkazů (`SLASH_COMMANDS`) nebo ruka; „hotovo“ paleta zatím nepíše. */
const MARKS: { prefix: string; mark: Exclude<BlockMark, null> }[] = [
  { prefix: "TODO ", mark: "todo" },
  { prefix: "DONE ", mark: "done" },
  { prefix: "HOTOVO ", mark: "done" },
  { prefix: "ROZHODNUTÍ:", mark: "decision" },
  { prefix: "DŮKAZ:", mark: "evidence" },
];

/** `# ` až `### ` na začátku dělá z bloku nadpis; značka se hledá až za ním. */
export function blockLook(text: string): BlockLook {
  const value = text.trimStart();
  const heading = value.startsWith("### ") ? 3 : value.startsWith("## ") ? 2 : value.startsWith("# ") ? 1 : 0;
  const body = heading ? value.slice(heading + 1) : value;
  const found = MARKS.find((item) => body.startsWith(item.prefix));
  return { heading, mark: found ? found.mark : null };
}

/** Odkaz míří na existující uzel: hledá se podle ID i podle jména, jinak zůstane nevyřešený. */
export function resolveTarget(name: string, targets: LinkTarget[]): LinkTarget | null {
  const key = name.trim().toLocaleLowerCase();
  return (
    targets.find((t) => t.id === name.trim()) ??
    targets.find((t) => t.name.trim().toLocaleLowerCase() === key) ??
    null
  );
}

/** Odkazy z jednoho bloku v pořadí, jak je uživatel napsal; nevyřešený si nechá napsané jméno. */
export function linkChips(text: string, targets: LinkTarget[]): { name: string; id: string | null }[] {
  return linkParts(text)
    .filter((part) => part.link)
    .map((part) => {
      const target = resolveTarget(part.text, targets);
      return target ? { name: target.name, id: target.id } : { name: part.text, id: null };
    });
}
