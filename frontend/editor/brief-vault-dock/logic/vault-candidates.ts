// Které fragmenty schránky jdou do plánu struktury: „Vložit vybrané jako karty“ a „Rozdistribuovat zbytek plánu“.
// Tady se jen vybírá; jak z fragmentu vznikne oblast → sektor → karta, rozhoduje server (POST /api/brief-vault/plan,
// docs/schranka-neurony.md §4), aby existovalo jediné pravidlo. Uzel jiné stopy je v pohledu jen cesta ke kořeni
// (`offTrack`) a kartou se nestane. Bez Reactu.
import type { VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { flatten } from "./vault-dock-model";

const briefs = (node: VaultNode) => node.children.filter((child) => child.kind === "brief");

function hasInserted(node: VaultNode): boolean {
  return flatten([node]).some((item) => item.node.kind === "brief" && item.node.inserted);
}

/**
 * „Rozdistribuovat zbytek plánu“: nevložené části zadání → kandidáti plánu. Větev bez jediné karty je jeden
 * kandidát; větev, kde už něco vloženo je, se dělí na své děti. Kořen schránky je celé zadání, takže kandidátem
 * se stává až jeho dítě (kořen bez dětí výjimkou).
 */
export function distributeCandidates(roots: VaultNode[]): VaultNode[] {
  const result: VaultNode[] = [];
  const stack: { node: VaultNode; root: boolean }[] = roots.slice().reverse().map((node) => ({ node, root: true }));
  while (stack.length) {
    const { node, root } = stack.pop()!;
    if (node.kind !== "brief" || node.inserted) continue;
    const kids = briefs(node);
    if (!node.offTrack && (!kids.length || (!root && !hasInserted(node)))) { result.push(node); continue; }
    for (let index = kids.length - 1; index >= 0; index--) stack.push({ node: kids[index], root: false });
  }
  return result;
}

/** „Vložit vybrané jako karty“: vybrané fragmenty v pořadí stromu, už vložené se přeskočí. */
export function selectionCandidates(roots: VaultNode[], selected: Set<string>): VaultNode[] {
  return flatten(roots).map((item) => item.node).filter((node) => selected.has(node.id) && node.kind === "brief" && !node.inserted && !node.offTrack);
}

/** Výchozí výběr MVP: co člověk potvrdil (mvp = yes) a ještě nemá kartu. */
export function defaultSelection(roots: VaultNode[]): Set<string> {
  return new Set(flatten(roots).map((item) => item.node).filter((node) => node.kind === "brief" && node.mvp === "yes" && !node.inserted && !node.offTrack).map((node) => node.id));
}

/** Tělo `POST /api/brief-vault/plan`; server výběr normalizuje (potomci vybraných předků vypadnou). */
export function planRequest(candidates: VaultNode[]): { fragmentIds: string[] } {
  return { fragmentIds: candidates.slice(0, 500).map((node) => node.id) };
}
