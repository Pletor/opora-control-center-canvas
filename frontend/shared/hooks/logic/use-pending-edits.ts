import { useEffect, useRef } from "react";
import { hasSaveParticipant, notifySaveParticipants, trackSaveWrite } from "./save-coordinator";
import { api } from "@/shared/types/logic/types";

/**
 * Jedna evidence rozepsané editace pro bloky uzlu i deník.
 *
 * Kontrakt: text patří uživateli, dokud ho server prokazatelně nepřevzal.
 * Draft se zapisuje do sessionStorage okamžitě při psaní, přežije odpojení
 * komponenty (přepnutí uzlu/režimu) i reload karty a maže se výhradně po
 * úspěšném uložení nebo výslovným zahozením. Neúspěšné uložení draft nechává.
 */
export type PendingEdit = { text: string; revision: number };

const STORE_KEY = "opora.pending-edits.v1";
/** Záloha pro prostředí bez sessionStorage; drží alespoň přepnutí uzlu. */
const memory = new Map<string, PendingEdit>();

function store(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function readAll(): Record<string, PendingEdit> {
  const raw = store()?.getItem(STORE_KEY);
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as Record<string, PendingEdit>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeAll(all: Record<string, PendingEdit>) {
  try {
    store()?.setItem(STORE_KEY, JSON.stringify(all));
  } catch {
    // Plné nebo zakázané úložiště nesmí shodit editaci; zůstává paměťová záloha.
  }
}

/** Rozsah draftu je identita editovaného obsahu, ne komponenta. */
export function editScope(kind: string, parts: (string | undefined)[]) {
  return JSON.stringify([kind, ...parts]);
}

export function readPendingEdit(scope: string): PendingEdit | null {
  const saved = readAll()[scope] ?? memory.get(scope) ?? null;
  if (!saved || typeof saved.text !== "string" || typeof saved.revision !== "number") return null;
  return { text: saved.text, revision: saved.revision };
}

export function writePendingEdit(scope: string, edit: PendingEdit) {
  memory.set(scope, edit);
  const all = readAll();
  all[scope] = edit;
  writeAll(all);
  notifySaveParticipants();
}

export function clearPendingEdit(scope: string, expected?: PendingEdit) {
  const current = readPendingEdit(scope);
  if (expected && current && (current.text !== expected.text || current.revision !== expected.revision)) return;
  memory.delete(scope);
  const all = readAll();
  if (!(scope in all)) { notifySaveParticipants(); return; }
  delete all[scope];
  writeAll(all);
  notifySaveParticipants();
}

/** Saved drafts from unmounted editors remain visible to the central save control. */
export function pendingEditsInScope(project: string, workspace: string) {
  const all = { ...Object.fromEntries(memory), ...readAll() };
  return Object.entries(all).filter(([key]) => { try { const [, p, w] = JSON.parse(key); return p === project && w === workspace; } catch { return false; } });
}

const pendingWrites = new Map<string, Promise<unknown>>();
export const pendingEditSaving = (scope: string) => pendingWrites.has(scope);
/** The same per-content CAS writer serves visible editors and drafts whose view was closed. */
export async function persistPendingEdit<T extends { revision: number }>(scope: string): Promise<T | null> {
  while (pendingWrites.has(scope)) { await pendingWrites.get(scope); if (!readPendingEdit(scope)) return null; }
  const edit = readPendingEdit(scope); if (!edit) return null;
  const [kind, project, workspace, node, day] = JSON.parse(scope) as string[];
  const write = (async () => {
    let value: T;
    if (kind === "node-text" || kind === "node-journal") value = await api<T>(kind === "node-text" ? "/api/node-text" : "/api/node-journal", { project, workspace, node, ...(day ? { day } : {}), text: edit.text, expected_revision: edit.revision });
    else if (kind === "workspace-document") {
      const draft = JSON.parse(edit.text);
      const saved = await api<{ nodeId: string | null }>("/api/workspace/document?" + new URLSearchParams({ project, workspace, path: node }));
      value = await api<T>("/api/workspace/document", { project, workspace, path: node, nodeId: saved.nodeId, fields: draft.fields ?? draft, expectedRevision: edit.revision, ...(!node ? { expectedSettingsRevision: draft.settingsRevision ?? -1 } : {}) });
    } else throw new Error("Rozepsaný obsah vyžaduje otevření původního editoru.");
    const current = readPendingEdit(scope);
    if (current && current.text !== edit.text) writePendingEdit(scope, { ...current, revision: value.revision });
    else clearPendingEdit(scope, edit);
    return value;
  })();
  const tracked = trackSaveWrite(project, workspace, write); pendingWrites.set(scope, tracked); notifySaveParticipants();
  try { return await tracked; } finally { if (pendingWrites.get(scope) === tracked) pendingWrites.delete(scope); notifySaveParticipants(); }
}
export const orphanedPendingEdits = (project: string, workspace: string) => pendingEditsInScope(project, workspace).filter(([key]) => !hasSaveParticipant(key));
export async function flushOrphanedPendingEdits(project: string, workspace: string) { for (const [key] of orphanedPendingEdits(project, workspace)) await persistPendingEdit(key); }

/**
 * Odchod z uzlu/režimu i zavření karty se pokusí čekající uložení dopsat.
 * Draft maže až samotné uložení, takže neúspěšný flush nic neztratí.
 */
export function usePendingFlush(scope: string, flush: () => void) {
  const latest = useRef({ scope, flush });
  // Cleanup starého scope drží vlastní objekt; nový render mu nesmí vyměnit cíl zápisu.
  if (latest.current.scope !== scope) latest.current = { scope, flush };
  else latest.current.flush = flush;
  useEffect(() => {
    const owner = latest.current;
    const leave = () => owner.flush();
    window.addEventListener("pagehide", leave);
    return () => {
      window.removeEventListener("pagehide", leave);
      leave();
    };
  }, [scope]);
}
