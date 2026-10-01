import { MODELS, type AssistantModel } from "./assistant-api";

/** Výchozí model je volba aplikace, ne projektu: jeden klíč pro všechny projekty. */
export const ASSISTANT_PREFS_KEY = "opora:assistant:v1";

export function readDefaultModel(): AssistantModel {
  try {
    const value = JSON.parse(localStorage.getItem(ASSISTANT_PREFS_KEY) ?? "null");
    if (value && MODELS.includes(value.model)) return value.model;
  } catch {
    /* Poškozené preference nejsou data projektu. */
  }
  return "opus";
}

export function writeDefaultModel(model: AssistantModel): void {
  try {
    localStorage.setItem(ASSISTANT_PREFS_KEY, JSON.stringify({ model }));
  } catch {
    /* Bez úložiště model platí jen do zavření stránky. */
  }
}
