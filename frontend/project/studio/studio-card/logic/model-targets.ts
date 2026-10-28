// Odznak „cíl z MODELu“ ve Skutečnosti (docs/studio.md §4a): karty OPORY, na které váže uzel technického modelu
// domény (`binding.nodeId`). Z modelu se berou jen id vazeb; katalog, simulace ani editor MODELu se sem nenačítají.
// Čistá logika bez Reactu.
import { normalizeStudioModel } from "../../model/logic/studio-model-api";

/** Id karet, na které váže některý uzel modelu domény `domain`; neznámý tvar nebo cizí doména = žádné. */
export function modelBindingIds(raw: unknown, domain: string): Set<string> {
  const ids = new Set<string>();
  for (const node of normalizeStudioModel(raw, domain).nodes) {
    const id = (node as { binding?: { nodeId?: unknown } } | null)?.binding?.nodeId;
    if (typeof id === "string" && id) ids.add(id);
  }
  return ids;
}
