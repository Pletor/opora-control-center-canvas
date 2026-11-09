import type { FlowGraph } from "@/shared/flow-editor/logic/flow-types";

export type LibraryReview = {
  id: string; operation: string; status: "pending" | "accepted" | "rejected" | "applied";
  input: Record<string, string | number>; requiresHuman: boolean;
  before: { folder?: {title: string; description: string; order: number; owner: string} | null;
    source?: {id: string; name: string; owner_ref: string}; version?: {id: string; n: number; graph: FlowGraph} | null };
  author: {name: string}; createdAt: string; result?: {id?: string; title?: string} | null;
};
export const operationTitle: Record<string, string> = {
  folder_create: "Nová složka", folder_update: "Úprava složky", folder_delete: "Odstranění prázdné složky",
  flow_create: "Nové plátno", flow_adopt: "Převzetí do projektu", flow_contribute: "Publikování plátna", flow_promote: "Přesun do knihovny člověka",
};
export function selectedReview(items: readonly LibraryReview[], identifier: string) {
  return identifier ? items.find(item => item.id === identifier) ?? null : items[0] ?? null;
}
export function scopedReviewId(query: string, project: string, workspace: string) {
  const params = new URLSearchParams(query);
  return params.get("project") === project && params.get("workspace") === workspace ? params.get("libraryReview") ?? "" : "";
}
export function reviewRows(review: LibraryReview) {
  const input = review.input, folder = review.before.folder;
  const rows: {label: string; before: string; after: string}[] = [];
  if (review.operation === "folder_delete") return [{label: "Složka", before: folder?.title ?? "", after: "Bude odstraněna"}];
  for (const [key, label] of [["title", "Název"], ["description", "Popis"], ["order", "Pořadí"]]) {
    if (input[key] !== undefined) rows.push({label, before: review.operation === "folder_update" ? String(folder?.[key as "title"] ?? "") : "—", after: String(input[key])});
  }
  if (review.before.source) rows.push({label: "Zdroj", before: review.before.source.name, after: review.operation === "flow_promote" ? "Knihovna člověka" : "Nová odvozená kopie"});
  if (folder && review.operation.startsWith("flow_")) rows.push({label: "Cílová složka", before: "—", after: folder.title});
  return rows;
}
