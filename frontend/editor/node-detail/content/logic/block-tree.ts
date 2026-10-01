/** Strom osnovy se jen čte z plochého seznamu bloků (`block-commands`), druhý model nevzniká.
 *  Dítě = blok hned za rodičem s větší hloubkou. Sbalení je pohled, ne obsah: do textu uzlu
 *  se neukládá a po přepsání osnovy zvenku se zahodí. */
import type { Block } from "@/editor/node-detail/content/logic/block-commands";

/** Kolik bloků tvoří podstrom hned za `index`: souvislá řada s větší hloubkou. */
export function subtreeSize(blocks: Block[], index: number): number {
  let end = index + 1;
  while (end < blocks.length && blocks[end].depth > blocks[index].depth) end += 1;
  return end - index - 1;
}

export function hasChildren(blocks: Block[], index: number): boolean {
  return subtreeSize(blocks, index) > 0;
}

/** Indexy bloků k vykreslení: podstrom sbaleného rodiče se přeskočí, rodič zůstane vidět. */
export function visibleIndexes(blocks: Block[], collapsed: ReadonlySet<string>): number[] {
  const shown: number[] = [];
  for (let i = 0; i < blocks.length; i += 1) {
    shown.push(i);
    if (collapsed.has(blocks[i].id)) i += subtreeSize(blocks, i);
  }
  return shown;
}

/** Sbalení přežije jen tam, kde pořád jsou děti: po vynoření dítěte značka tiše zmizí. */
export function prunedCollapsed(blocks: Block[], collapsed: ReadonlySet<string>): Set<string> {
  const kept = new Set<string>();
  blocks.forEach((block, index) => {
    if (collapsed.has(block.id) && hasChildren(blocks, index)) kept.add(block.id);
  });
  return kept;
}
