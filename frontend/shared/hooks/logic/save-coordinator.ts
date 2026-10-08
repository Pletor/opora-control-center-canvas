import { useEffect, useRef, useSyncExternalStore } from "react";

/** Coordination only: content remains in each editor's existing draft owner. */
export type SaveParticipant = {
  id: string; project: string; workspace?: string; label: string;
  dirty: boolean; pending?: boolean; blocked?: string;
  flush?: () => Promise<void>; discard?: () => void;
  retainOnUnmount?: boolean;
  isDirty?: () => boolean; isPending?: () => boolean;
};
type Owner = { current: SaveParticipant; mounted: boolean };
const owners = new Map<string, Owner>();
const writes = new Map<string, { project: string; workspace: string; promise: Promise<unknown> }>();
const writeRevisions = new Map<string, number>();
export const saveWriteRevision = (project: string, workspace: string) => (writeRevisions.get(JSON.stringify([project, workspace])) ?? 0) + (writeRevisions.get(JSON.stringify([project, "*"])) ?? 0);
const subscribers = new Set<() => void>();
let revision = 0;
export function notifySaveParticipants() { revision++; subscribers.forEach((listener) => listener()); }
const subscribe = (listener: () => void) => { subscribers.add(listener); return () => subscribers.delete(listener); };
const dirtyOf = (owner: Owner) => owner.current.isDirty?.() ?? owner.current.dirty;
const pendingOf = (owner: Owner) => owner.current.isPending?.() ?? !!owner.current.pending;
const inScope = (owner: Owner, project: string, workspace: string) => owner.current.project === project && (owner.current.workspace === undefined || owner.current.workspace === workspace);

export function useSaveParticipant(value: SaveParticipant) {
  const owner = useRef<Owner>({ current: value, mounted: true });
  if (owner.current.current.id !== value.id) owner.current = { current: value, mounted: true };
  else owner.current.current = value;
  useEffect(() => {
    const registered = owner.current; registered.mounted = true;
    owners.set(value.id, registered); notifySaveParticipants();
    return () => {
      registered.mounted = false;
      if (owners.get(value.id) === registered && (!registered.current.retainOnUnmount || (!dirtyOf(registered) && !pendingOf(registered)))) owners.delete(value.id);
      notifySaveParticipants();
    };
  }, [value.id]);
  useEffect(() => { notifySaveParticipants(); }, [value.dirty, value.pending, value.blocked]);
}

export function saveScopeEntries(project: string, workspace: string) {
  return [...[...owners.values()].filter((owner) => inScope(owner, project, workspace) && (dirtyOf(owner) || pendingOf(owner))).map((owner) => ({ id: owner.current.id, label: owner.current.label, dirty: dirtyOf(owner), pending: pendingOf(owner), blocked: owner.current.blocked })), ...[...writes.entries()].filter(([, value]) => value.project === project && (value.workspace === workspace || value.workspace === "*")).map(([id]) => ({ id, label: "Probíhající zápis", dirty: false, pending: true, blocked: undefined }))];
}
export async function trackSaveWrite<T>(project: string, workspace: string, promise: Promise<T>): Promise<T> {
  const id = crypto.randomUUID(); writes.set(id, { project, workspace, promise }); notifySaveParticipants();
  try { const result = await promise; const key = JSON.stringify([project, workspace]); writeRevisions.set(key, (writeRevisions.get(key) ?? 0) + 1); return result; } finally { writes.delete(id); notifySaveParticipants(); }
}
export async function waitForSaveWrites(project: string, workspace: string) {
  for (;;) { const pending = [...writes.values()].filter((value) => value.project === project && (value.workspace === workspace || value.workspace === "*")); if (!pending.length) return; await Promise.all(pending.map((value) => value.promise)); }
}
export function useSaveScope(project: string, workspace: string) {
  const currentRevision = useSyncExternalStore(subscribe, () => revision);
  const entries = saveScopeEntries(project, workspace);
  return { revision: currentRevision, writeRevision: saveWriteRevision(project, workspace), entries, dirty: entries.some((entry) => entry.dirty), pending: entries.some((entry) => entry.pending) };
}
export async function flushSaveScope(project: string, workspace: string) {
  await waitForSaveWrites(project, workspace);
  for (let pass = 0; pass < 12; pass++) {
    const active = [...owners.values()].filter((owner) => inScope(owner, project, workspace) && (dirtyOf(owner) || pendingOf(owner)));
    if (!active.length) return;
    for (const owner of active) if (owner.current.blocked || !owner.current.flush) throw new Error(`${owner.current.label}: ${owner.current.blocked || "dokončete nebo zahoďte rozepsanou editaci v jejím formuláři."}`);
    for (const owner of active) {
      const before = owner.current;
      try { await before.flush!(); await waitForSaveWrites(project, workspace); await new Promise<void>((resolve) => setTimeout(resolve, 0)); }
      catch (cause) { throw new Error(`${before.label}: ${cause instanceof Error ? cause.message : String(cause)}`); }
      if (!owner.mounted && !dirtyOf(owner) && !pendingOf(owner) && owners.get(before.id) === owner) owners.delete(before.id);
      notifySaveParticipants();
    }
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
  }
  throw new Error("Během ukládání přibývají další změny. Dokončete psaní a zkuste Uložit vše znovu.");
}
export const hasSaveParticipant = (id: string) => owners.has(id);
export function invalidateSavedScope(project: string, workspace: string) {
  const active = [...owners.values()].filter((owner) => inScope(owner, project, workspace));
  if (active.some((owner) => dirtyOf(owner) || pendingOf(owner))) throw new Error("Obnova nemůže zahodit rozepsané změny. Nejprve je uložte.");
  for (const owner of active) owner.current.discard?.();
  notifySaveParticipants();
}
