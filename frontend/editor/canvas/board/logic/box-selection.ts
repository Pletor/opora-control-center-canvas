// Výběr tažením a mazání klávesou na plátně. Čistá pravidla bez Reactu a bez DOM: která klávesa maže,
// kdy se nesmí chytit a co z výběru React Flow smí jít do potvrzovacího dialogu. Board kolem nich jen
// drží posluchač a bublá výsledek nahoru; mazání samo (náhled, potvrzení, krok zpět) řídí App.
import { isBlockId } from "@/editor/workflow/blocks/logic/block-model";
import { isTypingTarget, type ShortcutKey } from "@/editor/canvas/history/logic/undo-shortcut";

/**
 * Maže klávesa? `Delete` i `Backspace` bez modifikátoru — Ctrl/⌘/Alt patří jiným zkratkám (Ctrl+Backspace
 * maže slovo, Alt+… přepíná prostředí). Psaní do polí a textů má vlastní mazání písmen a plátno mu ho
 * nesmí vzít (`isTypingTarget`, stejné pravidlo jako u Ctrl+Z).
 */
export function isDeleteKey(event: ShortcutKey, target: unknown): boolean {
  if (event.key !== "Delete" && event.key !== "Backspace") return false;
  if (event.ctrlKey || event.metaKey || event.altKey) return false;
  return !isTypingTarget(target);
}

/**
 * Co z výběru React Flow patří do výběru plátna: uzly grafu (karty, sektory, oblasti, komentáře).
 * Boční bloky (Akce / Pravidla / Podklady) jsou jen pohled na kartu, ne její položka — vypadnou,
 * pořadí zůstane a každé id jen jednou.
 */
export function selectionIds(nodes: readonly { id: string; selected?: boolean }[]): string[] {
  const seen = new Set<string>();
  for (const node of nodes) if (node.selected && !isBlockId(node.id)) seen.add(node.id);
  return [...seen];
}

/** Jen ta část změny uzlu z React Flow, na které záleží výběru. */
export type SelectChange = { type: string; id?: string; selected?: boolean };

/**
 * Má se po těchto změnách hlásit výběr nahoru? Jen když se výběr opravdu měnil (`select`), a ne když
 * uživatel klikl na boční blok — ten si React Flow vybere sám pro sebe, ale výběr plátna (karta,
 * blok v ní, vazba) má zůstat, jak byl.
 */
export function reportsSelection(changes: readonly SelectChange[]): boolean {
  const selects = changes.filter((change) => change.type === "select");
  if (!selects.length) return false;
  return !selects.some((change) => change.selected && typeof change.id === "string" && isBlockId(change.id));
}

/**
 * Jak výběr z plátna promítnout do App: dvě a víc položek je hromadný výběr (jednotlivý uzel se
 * zruší, aby nezůstal zvýrazněný mimo to, co smaže Delete), jedna položka je obyčejný výběr uzlu
 * a prázdný výběr ruší obojí.
 */
export function selectionPlan(ids: readonly string[]): { multi: string[]; single: string | null } {
  if (ids.length > 1) return { multi: [...ids], single: null };
  return { multi: [], single: ids[0] ?? null };
}

/**
 * Co smaže Delete: hromadný výběr, a když žádný není, jediný vybraný uzel. Jen id, která na plátně
 * opravdu jsou (`present`) — výběr z vrstvy, ze které uživatel mezitím odešel, nic nesmaže.
 */
export function deletableSelection(
  multiSelected: readonly string[],
  selected: string | null,
  present: ReadonlySet<string>,
): string[] {
  const picked = multiSelected.length ? multiSelected : selected ? [selected] : [];
  return [...new Set(picked)].filter((id) => present.has(id) && !isBlockId(id));
}

/** Jsou to tytéž výběry? Pořadí nehraje roli; slouží k tomu, aby stejný výběr nebublal nahoru znovu. */
export function sameSelection(a: readonly string[], b: readonly string[]): boolean {
  if (a.length !== b.length) return false;
  const set = new Set(a);
  return b.every((id) => set.has(id));
}
