// Adresa Studia: zanoření v `studioFocus=<id>` (docs/studio.md §2) a odkaz „Otevřít v Editoru stránky“ do Architektury
// projektu (`projectView=architecture&editorId=…&domainId=…&pageId=…&architectureNode=…`, čte `resolveEditorRoute`).
// Čistá logika bez Reactu; zapisuje rodič.
import { architectureEditorId } from "@/project/architecture-editor/logic/editor-model";
import type { StudioItem, StudioTree } from "./studio-tree";

export const STUDIO_FOCUS_PARAM = "studioFocus";

/** Zanoření z adresy; neznámé id (smazaný uzel, cizí projekt) = úroveň projektu, nic se nehlásí. */
export function readStudioFocus(route: URLSearchParams, tree: StudioTree): string | null {
  const id = route.get(STUDIO_FOCUS_PARAM);
  return id && tree.items.has(id) ? id : null;
}

/** Adresa po změně zanoření; ostatní parametry zůstanou. */
export function withStudioFocus(route: URLSearchParams, focus: string | null): URLSearchParams {
  const next = new URLSearchParams(route);
  if (focus) next.set(STUDIO_FOCUS_PARAM, focus); else next.delete(STUDIO_FOCUS_PARAM);
  return next;
}

/** Parametry Architektury projektu pro kartu: doména otevře mapu domény, stránka a sekce Editor stránky, komponenta
 * Editor své stránky s vybranou komponentou. Komponenta mimo stránky otevře mapu své domény. Bez domény null. */
export function editorParams(item: StudioItem, project: string, workspace: string): Record<string, string> | null {
  if (!item.domainId) return null;
  const params: Record<string, string> = { editorId: architectureEditorId(project, workspace, item.domainId), domainId: item.domainId };
  if (item.kind === "domain" || !item.pageId) return params;
  params.pageId = item.pageId;
  if (item.kind === "component") params.architectureNode = item.id;
  return params;
}

/** Popisek tlačítka podle toho, kam odkaz vede. */
export function editorLabel(item: StudioItem): string {
  return item.kind === "domain" || !item.pageId ? "Otevřít mapu domény" : "Otevřít v Editoru stránky";
}

/** Rodič zanoření (Backspace, drobečky); úroveň projektu zůstává. */
export function focusUp(tree: StudioTree, focus: string | null): string | null {
  return focus ? tree.parent.get(focus) ?? null : null;
}
