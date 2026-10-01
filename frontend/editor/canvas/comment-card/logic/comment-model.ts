// Čistý model komentáře: lepicí lístek na plátně, ne karta uzlu. Bez Reactu, testuje se samostatně.
// Komentář sdílí tvar uzlu (kind "comment", name = titulek, purpose = text), ale nemá zdroj ani vazby
// a nesmí být rodičem — to hlídá Board a App, tenhle modul jen čte a staví data.
import type { CanvasNode } from "@/shared/types/logic/types";

export type CommentView = { title: string; text: string; empty: boolean };

/** Zobrazení komentáře z uzlu grafu: název je titulek, podstata je text lístku. */
export function commentView(node: Pick<CanvasNode, "name" | "purpose">): CommentView {
  return { title: node.name, text: node.purpose, empty: node.purpose.trim().length === 0 };
}

/** Nový komentář na daném místě vrstvy; jméno je vždy „Poznámka“, text začíná prázdný. */
export function newComment(parentId: string | null, x: number, y: number): CanvasNode {
  return {
    id: crypto.randomUUID(),
    parentId,
    kind: "comment",
    name: "Poznámka",
    purpose: "",
    x,
    y,
  };
}

/** Místo pro nový komentář v dané vrstvě: řadí se úhlopříčně podle počtu už existujících, ať se nepřekrývají. */
export function nextCommentSpot(nodes: Pick<CanvasNode, "parentId" | "kind">[], parentId: string | null): { x: number; y: number } {
  const count = nodes.filter((n) => n.parentId === parentId && n.kind === "comment").length;
  return { x: 120 + 40 * count, y: 120 + 40 * count };
}
