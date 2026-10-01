// Čistý model knihovny uzlu (levá strana Editoru): stav vysouvacího panelu, druhy bloků k vložení
// a kontrola, zda má uzel kontext, se kterým může model pracovat. Bez Reactu; testuje se samostatně.
import type { CanvasNode, GraphEdge } from "@/shared/types/logic/types";
import { isBlockEdge } from "@/shared/types/logic/types";
import type { DesktopState, NodeWorkflowFull } from "@/shared/desktop-state/logic/types";
import { blockPorts, nodeWorkflowOf } from "@/shared/desktop-state/logic/types";
import { addBlock, updateBlock } from "@/editor/node-detail/tree/logic/tree-model";

export type LibrarySection = "context" | "blocks" | "actions" | "materials";
export const LIBRARY_SECTIONS: { id: LibrarySection; label: string; icon: string; hint: string }[] = [
  { id: "blocks", label: "Bloky", icon: "☰", hint: "Vložit blok obsahu do karty" },
  { id: "actions", label: "Akce", icon: "⚡", hint: "Pipeline z knihovny v pořadí výrobní linky" },
  { id: "materials", label: "Podklady", icon: "▣", hint: "Obrázky, cesty a odkazy pro agenta" },
  { id: "context", label: "Kontext", icon: "◎", hint: "Co model dostane a co ještě chybí" },
];

export type LibraryState = { open: boolean; section: LibrarySection };

export const initialLibrary = (): LibraryState => ({ open: false, section: "blocks" });
/** Panel vyjede s výběrem karty a zajede, když výběr zmizí; poslední sekce zůstává. */
export const openLibrary = (state: LibraryState): LibraryState => (state.open ? state : { ...state, open: true });
export const closeLibrary = (state: LibraryState): LibraryState => (state.open ? { ...state, open: false } : state);
/** Záložka v hlavě panelu přepne sekci; panel při tom zůstává otevřený. */
export const showSection = (state: LibraryState, section: LibrarySection): LibraryState => ({ open: true, section });

/** Druhy bloků k vložení do karty. Blok je vždy stejná datová struktura; druh jen předvyplní, k čemu slouží. */
export type BlockKind = "text" | "image" | "checklist" | "condition";
export const BLOCK_KINDS: { kind: BlockKind; label: string; hint: string; icon: string }[] = [
  { kind: "text", label: "Text", hint: "Popis, zadání nebo poznámka pro agenta", icon: "≡" },
  { kind: "image", label: "Obrázek", hint: "Inspirace nebo předloha; obrázky se přidají ve stromu bloku", icon: "▣" },
  { kind: "checklist", label: "Checklist", hint: "Kroky k odškrtnutí s přiřazením", icon: "☑" },
  { kind: "condition", label: "Podmínka", hint: "Kdy je blok splněný a kam se jde dál", icon: "⑂" },
];
const KIND_TITLE: Record<BlockKind, string> = { text: "Nový text", image: "Obrázek jako předloha", checklist: "Checklist", condition: "Podmínka" };

export const addBlockOfKind = (nodeId: string, kind: BlockKind) => (state: DesktopState): DesktopState => {
  const added = addBlock(nodeId)(state);
  const last = nodeWorkflowOf(added, nodeId).blocks.at(-1);
  if (!last) return added;
  const patch = kind === "condition"
    ? { title: KIND_TITLE[kind], state: { ...last.state, condition: "Splněno, když…" } }
    : kind === "checklist"
      ? { title: KIND_TITLE[kind], todos: [{ id: `${last.id}-1`, text: "První krok", done: false, assignee: "" }] }
      : { title: KIND_TITLE[kind] };
  return updateBlock(nodeId, last.id, patch)(added);
};

/** Kontrola kontextu pro model: cíl, hranice, podklady, kritéria, postup. Každá položka říká, co ještě chybí. */
export type ContextCheck = { id: string; label: string; ok: boolean; hint: string };

/** Porty bloků uzlu, ze kterých skutečně vede vazba na jinou kartu; graf si model nese s sebou. */
export function linkedBlockPorts(
  node: Pick<CanvasNode, "id">,
  workflow: Pick<NodeWorkflowFull, "blocks">,
  edges: GraphEdge[],
): string[] {
  const known = new Set(workflow.blocks.flatMap((b) => blockPorts(b).map((p) => `${b.id}:${p.id}`)));
  const linked = edges
    .filter((e) => isBlockEdge(e) && e.source === node.id)
    .map((e) => `${e.sourceBlockId}:${e.sourcePortId}`)
    .filter((key) => known.has(key));
  return Array.from(new Set(linked));
}

export function contextChecks(
  node: Pick<CanvasNode, "id" | "purpose" | "name">,
  workflow: NodeWorkflowFull,
  edges: GraphEdge[] = [],
): ContextCheck[] {
  const withText = workflow.blocks.filter((b) => b.text.trim() || b.todos.length || b.images.length);
  const withCondition = workflow.blocks.filter((b) => b.state.condition.trim());
  return [
    { id: "goal", label: "Cíl", ok: node.purpose.trim().length > 0, hint: "Podstata uzlu říká, co má vzniknout a proč. Bez cíle model hádá." },
    { id: "blocks", label: "Zadání v blocích", ok: withText.length > 0, hint: "Aspoň jeden blok s textem, kroky nebo obrázkem; bloky jsou tělo úkolu." },
    { id: "rules", label: "Hranice (musí / nesmí)", ok: workflow.rules.length > 0, hint: "Pravidla vymezují, co model nesmí změnit a co musí dodržet." },
    { id: "acceptance", label: "Kritéria splnění", ok: withCondition.length > 0 || workflow.criteria.length > 0, hint: "Podmínka bloku nebo kritérium: podle čeho se pozná hotovo." },
    { id: "materials", label: "Podklady", ok: workflow.materials.length > 0, hint: "Obrázek, cesta ve zdroji nebo odkaz; model vidí jen to, co mu dáte." },
    { id: "actions", label: "Postup (akce)", ok: workflow.actions.length > 0, hint: "Pipeline v pořadí říká, jak se úkol vykoná a ověří." },
    { id: "ports", label: "Porty a vazby", ok: linkedBlockPorts(node, workflow, edges).length > 0, hint: "Aspoň jeden port bloku vede vazbou na další kartu; jinak model neví, kam po splnění pokračovat." },
  ];
}

export function contextScore(checks: ContextCheck[]): { done: number; total: number } {
  return { done: checks.filter((c) => c.ok).length, total: checks.length };
}
