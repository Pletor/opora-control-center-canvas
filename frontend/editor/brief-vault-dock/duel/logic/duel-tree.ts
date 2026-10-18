// Duel a představa jsou ve stromu Schránky fragmenty `kind: "duel"` / `"vision"` (docs/schranka-duel.md §1, §3.3).
// Ostatní sekce (Zadání, MVP, plán, Podněty, pokrytí) s nimi počítat nesmí: kořen představy by se jinak stal cílem
// Podnětu a duel uzlem stromu zadání. Proto se strom rozdělí jednou v rodiči: sekce dostanou strom bez nich, sekce
// Duel jen duely a představy. Bez Reactu (test vedle).
import { NOT_BRIEF_KINDS, type VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import type { DuelItem } from "./duel-view";

export const DUEL_KINDS = NOT_BRIEF_KINDS;
export const isDuelKind = (kind: string): boolean => DUEL_KINDS.has(kind);

/** Výtah duelu ve stromu (`details_summary` na serveru); detail jen přes GET duel. */
export type DuelSummary = { status?: string; subject?: { kind: string; id: string }; turns?: number; scores?: number; p?: number | null; outcome?: string | null };
type MaybeDuel = VaultNode & { duel?: DuelSummary };

export type VaultSplit = { roots: VaultNode[]; duels: VaultNode[]; visions: VaultNode[] };

/** Strom bez duelů a představ (i vnořených) a zvlášť jejich plochý seznam v pořadí čtení. */
export function splitVault(roots: VaultNode[]): VaultSplit {
  const duels: VaultNode[] = [];
  const visions: VaultNode[] = [];
  const keep = (node: VaultNode): VaultNode | null => {
    const kind = node.kind as string;
    if (isDuelKind(kind)) {
      (kind === "duel" ? duels : visions).push(node);
      node.children.forEach(keep);
      return null;
    }
    const children = node.children.map(keep).filter((child): child is VaultNode => !!child);
    return children.length === node.children.length ? node : { ...node, children };
  };
  const rest = roots.map(keep).filter((node): node is VaultNode => !!node);
  return { roots: rest, duels, visions };
}

/** Řádek seznamu z uzlu stromu (stav a P z výtahu `duel`). */
export function duelItemOf(node: VaultNode): DuelItem {
  const summary = (node as MaybeDuel).duel;
  const status = summary?.status ?? "open";
  const p = typeof summary?.p === "number" ? summary.p : null;
  return { id: node.id, title: node.title || "Duel", status, p, open: status !== "decided" };
}

/** Počet otevřených duelů do vnitřního menu. */
export function openDuelCount(items: DuelItem[]): number {
  return items.filter((item) => item.open).length;
}
