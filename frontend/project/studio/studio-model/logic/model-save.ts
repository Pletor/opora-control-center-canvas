// Před uložením modelu (docs/studio.md §4–5): obsah se porovná s poslední uloženou verzí (neuloženo / uloženo)
// a celá definice projde kontrolou S4 (katalog, vazby, limity) i S5 (parametry simulace, Deployment, plán incidentů).
// Klávesy editace MODELu. Čistá logika bez Reactu.
import { validateSimulationModel } from "../../model/simulation/logic/simulation-validate";
import type { EditModel } from "./model-edit";

const content = (model: EditModel) => JSON.stringify([model.nodes, model.edges, model.modelDefinition ?? null]);

/** Stejné komponenty, vazby a MODEL část; revize ani čas uložení se nepočítají. */
export function sameContent(a: EditModel, b: EditModel): boolean {
  return a === b || content(a) === content(b);
}

/** Proč model nejde uložit (česká zpráva z validace); null = jde. */
export function saveProblem(model: EditModel): string | null {
  try {
    validateSimulationModel(model);
    return null;
  } catch (error) {
    return error instanceof Error ? error.message : String(error);
  }
}

export type ModelKey = "undo" | "redo" | "delete" | "escape" | null;
type KeyLike = { key: string; ctrlKey: boolean; metaKey: boolean; shiftKey: boolean };

/** Klávesa plátna MODELu; v textovém poli (`editing`) patří klávesy poli, ne plátnu. */
export function modelKey(event: KeyLike, editing: boolean): ModelKey {
  if (editing) return null;
  const mod = event.ctrlKey || event.metaKey, key = event.key.toLowerCase();
  if (mod && key === "z") return event.shiftKey ? "redo" : "undo";
  if (mod && key === "y") return "redo";
  if (event.key === "Delete") return "delete";
  if (event.key === "Escape") return "escape";
  return null;
}
