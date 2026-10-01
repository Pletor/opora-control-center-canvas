// Překlad položky katalogu na to, co po puštění stojí na plátně. Položka je know-how (pravidla, rozpad,
// šablona); karta je uzel grafu a bloky s pravidly jsou stav uzlu. Tady se ty dva světy potkávají —
// čisté funkce bez Reactu, bez API a bez React Flow: Board jen hlásí, kam se pustilo, App volá save a mutate.
// Čísla bloků dělá `renumber` z modelu stromu obsahu, aby vložená karta vypadala stejně jako ručně psaná.
import type { CanvasNode } from "@/shared/types/logic/types";
import type { Block, DesktopState, NodeRule, NodeWorkflowFull } from "@/shared/desktop-state/logic/types";
import { emptyNodeWorkflow, nodeWorkflowOf } from "@/shared/desktop-state/logic/types";
import { addBlock, emptyBlock, newId, renumber, updateBlock } from "@/editor/node-detail/tree/logic/tree-model";
import type { CatalogItem } from "@/editor/component-library/library-catalog/logic/library-catalog";

/** Poslední blok vložené karty: kostra kódu z položky, aby byla po ruce hned u rozpadu. */
export const TEMPLATE_BLOCK_TITLE = "Šablona";

/** Značky řádkového komentáře, kterými šablony začínají; v odkazu na místo kódu jen překážejí. */
const COMMENT_MARK = /^\s*(\/\/+|#+|--+|<!--)\s*/;

/**
 * První řádek šablony je v katalogu odkaz na místo, kam kód patří (`// logic/form-model.ts`).
 * Do účelu karty jde bez značky komentáře; prázdná šablona nevrací nic.
 */
export function templateReference(template: string): string {
  const line = template.split("\n").find((raw) => raw.trim().length > 0) ?? "";
  return line.replace(COMMENT_MARK, "").trim();
}

/** Účel karty: nápověda položky a za ní odkaz na místo, kam kód ze šablony patří. */
export function purposeFromItem(item: CatalogItem): string {
  return [item.hint.trim(), templateReference(item.template)].filter(Boolean).join(" · ");
}

/**
 * Karta z položky: uzel grafu na místě puštění. Jméno je popisek položky, účel nese nápovědu i odkaz
 * na šablonu. Pozice je surové místo puštění — o dosednutí mezi pevná tělesa se stará `settleCard`.
 */
export function cardFromItem(item: CatalogItem, parentId: string | null, x: number, y: number): CanvasNode {
  return {
    id: newId(),
    parentId,
    kind: "node",
    name: item.label,
    purpose: purposeFromItem(item),
    x: Math.round(x),
    y: Math.round(y),
  };
}

/** Jeden krok rozpadu jako blok obsahu; číslo doplní `renumber` až nad celým seznamem. */
const blockOf = (title: string, text: string, tags: string[] = []): Block => ({ ...emptyBlock(), title, text, tags });

/**
 * Stav uzlu pro vloženou kartu: rozpad položky jako očíslované bloky, na konci blok „Šablona“ s kostrou
 * kódu, a pravidla položky jako pravidla uzlu (`must` / `must_not`). Ostatní pole zůstávají prázdná —
 * fázi, kritéria ani podklady knihovna nevymýšlí.
 */
export function workflowFromItem(item: CatalogItem): NodeWorkflowFull {
  const blocks = renumber([
    ...item.decomposition.map((step) => blockOf(step.title, step.text)),
    blockOf(TEMPLATE_BLOCK_TITLE, item.template),
  ]);
  const rules: NodeRule[] = [
    ...item.rules.must.map((text) => ({ id: newId(), text, kind: "must" as const })),
    ...item.rules.mustNot.map((text) => ({ id: newId(), text, kind: "must_not" as const })),
  ];
  return { ...emptyNodeWorkflow(), blocks, rules };
}

/**
 * Položka `kind: "block"` jako jeden blok obsahu: popisek je nadpis, šablona je text a kategorie zůstane
 * štítkem, aby se blok dal na plátně najít filtrem štítků.
 */
export function blockFromItem(item: CatalogItem): Block {
  return blockOf(item.label, item.template, [item.category]);
}

/**
 * Vložení bloku z položky do vybrané karty. Jde přes `addBlock` a `updateBlock` z modelu stromu, takže
 * blok dostane číslo i pořadí stejně jako ručně přidaný; nový blok se pozná podle toho, že před mutací
 * neexistoval.
 */
export const insertBlockFromItem =
  (nodeId: string, item: CatalogItem) =>
  (state: DesktopState): DesktopState => {
    const before = new Set(nodeWorkflowOf(state, nodeId).blocks.map((block) => block.id));
    const grown = addBlock(nodeId)(state);
    const created = nodeWorkflowOf(grown, nodeId).blocks.find((block) => !before.has(block.id));
    if (!created) return grown;
    const { title, text, tags } = blockFromItem(item);
    return updateBlock(nodeId, created.id, { title, text, tags })(grown);
  };
