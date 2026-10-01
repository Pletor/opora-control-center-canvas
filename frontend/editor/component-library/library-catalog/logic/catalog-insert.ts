// Překlad prvku Knihovny na to, co po puštění stojí na plátně (docs/menu-a-katalog.md §B4). Prvek nemá
// druh: puštěný na prázdné plátno dá novou kartu, puštěný na kartu dá jeden blok v ní. Obojí nese totéž
// — účel, souvislosti, hotovo, invarianty, kroky a šablonu — jen v jiném tvaru, takže `node-brief`
// vydá modelu stejnou orientaci bez zásahu do backendu. Čisté funkce bez Reactu, API a React Flow:
// Board hlásí, kam se pustilo, App volá save a mutate. Čísla bloků dělá `renumber` z modelu stromu.
import type { CanvasNode } from "@/shared/types/logic/types";
import type { Block, Criterion, DesktopState, NodeRule, NodeWorkflowFull } from "@/shared/desktop-state/logic/types";
import { emptyNodeWorkflow, nodeWorkflowOf } from "@/shared/desktop-state/logic/types";
import { addBlock, emptyBlock, newId, renumber, updateBlock } from "@/editor/node-detail/tree/logic/tree-model";
import { withNode } from "@/editor/workflow/blocks/logic/block-model";
import { relatesLines, type CatalogItem } from "@/editor/component-library/library-catalog/logic/library-catalog";

/** Blok nové karty s kostrou kódu z prvku. */
export const TEMPLATE_BLOCK_TITLE = "Šablona";
/** První blok nové karty: s čím prvek souvisí, aby model věděl, kam se podívat. */
export const RELATES_BLOCK_TITLE = "Souvisí s";

const blockOf = (title: string, text: string, tags: string[] = []): Block => ({ ...emptyBlock(), title, text, tags });

const bullets = (lines: string[]): string => lines.map((line) => "- " + line).join("\n");

/** Karta z prvku: uzel grafu na místě puštění, jméno = `label`, účel = `purpose`. Dosednutí řeší `settleCard`. */
export function cardFromItem(item: CatalogItem, parentId: string | null, x: number, y: number): CanvasNode {
  return {
    id: newId(),
    parentId,
    kind: "node",
    name: item.label,
    purpose: item.purpose,
    x: Math.round(x),
    y: Math.round(y),
  };
}

/** Invarianty prvku jako pravidla uzlu (`must` / `must_not`); obecné rady katalog nenese, takže nic se nefiltruje. */
export function rulesFromItem(item: CatalogItem): NodeRule[] {
  return item.invariants.map((rule) => ({ id: newId(), text: rule.text, kind: rule.kind }));
}

/** Kritéria hotovo prvku jako kritéria karty, nezaškrtnutá. */
export function criteriaFromItem(item: CatalogItem): Criterion[] {
  return item.done.map((text) => ({ id: newId(), text, checked: false }));
}

/**
 * Stav uzlu pro novou kartu: blok „Souvisí s“ (řádky, `@id` přeložené na název a účel), kroky jako
 * bloky a na konci blok „Šablona“. Kritéria hotovo jdou do `criteria`, invarianty do `rules`. Fázi
 * ani podklady katalog nevymýšlí.
 */
export function workflowFromItem(item: CatalogItem): NodeWorkflowFull {
  const relates = relatesLines(item.relates);
  const blocks = renumber([
    ...(relates.length ? [blockOf(RELATES_BLOCK_TITLE, bullets(relates))] : []),
    ...(item.steps ?? []).map((step) => blockOf(step.title, step.text)),
    ...(item.template?.trim() ? [blockOf(TEMPLATE_BLOCK_TITLE, item.template)] : []),
  ]);
  return { ...emptyNodeWorkflow(), blocks, criteria: criteriaFromItem(item), rules: rulesFromItem(item) };
}

/**
 * Text bloku vloženého do existující karty: účel jako první odstavec, pak „Souvisí s:“, „Hotovo, když:“,
 * „Kroky:“ a na konci šablona. Prázdné části se vynechají.
 */
export function blockTextFromItem(item: CatalogItem): string {
  const relates = relatesLines(item.relates);
  const steps = (item.steps ?? []).map((step, index) => `${index + 1}. ${step.title} — ${step.text}`);
  return [
    item.purpose.trim(),
    relates.length ? "Souvisí s:\n" + bullets(relates) : "",
    item.done.length ? "Hotovo, když:\n" + bullets(item.done) : "",
    steps.length ? "Kroky:\n" + steps.join("\n") : "",
    item.template?.trim() ?? "",
  ]
    .filter(Boolean)
    .join("\n\n");
}

/** Prvek jako jeden blok: nadpis = `label`, text podle `blockTextFromItem`, štítek = kategorie. */
export function blockFromItem(item: CatalogItem): Block {
  return blockOf(item.label, blockTextFromItem(item), [item.category]);
}

/**
 * Vložení prvku jako bloku do karty pod ukazatelem. Blok jde přes `addBlock` a `updateBlock` z modelu
 * stromu, takže dostane číslo i pořadí jako ručně přidaný. Invarianty prvku se přidají do pravidel
 * karty; pravidlo se stejným textem, které už karta má, se přeskočí.
 */
export const insertBlockFromItem =
  (nodeId: string, item: CatalogItem) =>
  (state: DesktopState): DesktopState => {
    const before = new Set(nodeWorkflowOf(state, nodeId).blocks.map((block) => block.id));
    const grown = addBlock(nodeId)(state);
    const created = nodeWorkflowOf(grown, nodeId).blocks.find((block) => !before.has(block.id));
    if (!created) return grown;
    const { title, text, tags } = blockFromItem(item);
    const filled = updateBlock(nodeId, created.id, { title, text, tags })(grown);
    const rules = rulesFromItem(item);
    if (!rules.length) return filled;
    return withNode(filled, nodeId, (node) => {
      const known = new Set(node.rules.map((rule) => rule.text));
      const fresh = rules.filter((rule) => !known.has(rule.text));
      return fresh.length ? { ...node, rules: node.rules.concat(fresh) } : node;
    });
  };
