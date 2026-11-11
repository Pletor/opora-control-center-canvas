import type { CanvasNode, ElementKind } from "@/shared/types/logic/types";

export const ELEMENT_GROUPS: { label: string; kinds: ElementKind[] }[] = [
  { label: "Rozhraní pro člověka", kinds: ["page", "form", "overview", "dialog"] },
  { label: "Chování systému", kinds: ["action", "service", "process"] },
  { label: "Data", kinds: ["entity", "relationship", "storage"] },
  { label: "Pravidla", kinds: ["condition", "permission", "constraint"] },
  { label: "Rozhraní mezi částmi", kinds: ["input", "output", "event", "api_contract"] },
];
export const ELEMENT_LABELS: Record<ElementKind, string> = {
  page: "Stránka", form: "Formulář", overview: "Přehled", dialog: "Dialog",
  action: "Akce", service: "Služba", process: "Proces", entity: "Entita", relationship: "Vztah",
  storage: "Úložiště", condition: "Podmínka", permission: "Oprávnění", constraint: "Omezení",
  input: "Vstup", output: "Výstup", event: "Událost", api_contract: "API kontrakt", actor: "Uživatel",
};
/** Updating a role preserves the graph identity and unrelated metadata. */
export function withElementKind(node: CanvasNode, kind: ElementKind | ""): CanvasNode {
  const { element: _element, ...rest } = node;
  return kind ? { ...rest, element: { kind } } : rest;
}
