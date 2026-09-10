import { useState } from "react";

export type WorkspaceSelection = { sourcePath: string; references: string[]; note: string };
const memory = new Map<string, WorkspaceSelection>();
export const SOURCE_DRAG_TYPE = "application/x-opora-source-reference";
const empty = (): WorkspaceSelection => ({ sourcePath: "", references: [], note: "" });
export function allowedReference(path: string) {
  return path.length <= 2048 && !!path && !path.startsWith("/") && !/[\\:\u0000-\u001f]/.test(path)
    && path.split("/").every((part) => !!part && ![".", "..", ".git", ".data", ".venv", "node_modules", ".claude", ".hermes"].includes(part.toLowerCase())
      && !/^(\.env(?:\.|$)|credentials(?:\.|$)|id_rsa|id_ed25519)/i.test(part));
}
function read(key: string): WorkspaceSelection {
  try {
    const value = JSON.parse(sessionStorage.getItem(key) ?? "null");
    if (value && typeof value.sourcePath === "string" && typeof value.note === "string" && Array.isArray(value.references))
      return { sourcePath: value.sourcePath, note: value.note.slice(0, 16000), references: [...new Set<string>(value.references.filter((p: unknown) => typeof p === "string" && allowedReference(p)))].slice(0, 100) };
  } catch { /* Nedostupné úložiště nezruší pracovní kontext. */ }
  return memory.get(key) ?? empty();
}
export function useWorkspaceSelection(project: string, workspace: string) {
  const key = "opora.workspace-selection.v2:" + JSON.stringify([project, workspace]);
  const [states, setStates] = useState<Record<string, WorkspaceSelection>>({});
  const value = states[key] ?? read(key);
  function change(update: Partial<WorkspaceSelection>) {
    setStates((old) => {
      const next = { ...(old[key] ?? read(key)), ...update };
      memory.set(key, next);
      try { sessionStorage.setItem(key, JSON.stringify(next)); } catch { /* Zachovat alespoň paměť. */ }
      return { ...old, [key]: next };
    });
  }
  function add(path: string) {
    if (!allowedReference(path)) return false;
    const current = states[key] ?? read(key);
    if (!current.references.includes(path) && current.references.length >= 100) return false;
    change({ references: [...new Set([...current.references, path])] });
    return true;
  }
  return { value, change, add };
}
