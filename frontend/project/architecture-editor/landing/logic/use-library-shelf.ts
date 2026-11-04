// Složky knihovny pláten toku pro panel Komponenty: čtou se pro zvolenou část (Člověk / Agent) a znovu po vlastním
// zápisu. Založení složky a plátna jde rovnou do API knihovny (do části Člověk píše jen člověk v UI, hlídá backend);
// nové plátno se po založení otevře na plátně (`onCreated`).
import { useCallback, useEffect, useState } from "react";
import { createFlow, createFolder, loadLibrary, slugOf, type LibraryFolder, type LibraryOwner } from "@/project/library-canvas/logic/library-api";
import type { Loaded } from "./component-shelf";
import { tagsDescription } from "./library-shelf";

export type LibraryShelf = {
  folders: Loaded<LibraryFolder[]>; busy: boolean; error: string;
  addFolder: (title: string, tags: string) => Promise<void>; addFlow: (folder: string, title: string, description: string) => Promise<string | null>;
};

const reason = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

export function useLibraryShelf(owner: LibraryOwner): LibraryShelf {
  const [folders, setFolders] = useState<Loaded<LibraryFolder[]>>({ data: null, error: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    loadLibrary(owner).then((data) => { if (alive) setFolders({ data, error: "" }); }, (cause) => { if (alive) setFolders({ data: null, error: reason(cause) }); });
    return () => { alive = false; };
  }, [owner, tick]);
  const write = useCallback(async <T,>(action: () => Promise<T>): Promise<T | null> => {
    setBusy(true); setError("");
    try { const result = await action(); setTick((value) => value + 1); return result; }
    catch (cause) { setError(reason(cause)); return null; }
    finally { setBusy(false); }
  }, []);
  return {
    folders, busy, error,
    addFolder: async (title, tags) => { await write(() => createFolder(owner, slugOf(title), title.trim(), tagsDescription(tags))); },
    addFlow: async (folder, title, description) => (await write(() => createFlow(folder, slugOf(title), title.trim(), description.trim() || undefined)))?.id ?? null,
  };
}
