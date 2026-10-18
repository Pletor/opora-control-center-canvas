// Úložiště storyboardu karty: GET při mountu, koncept, revize, dirty a uložení přes POST. Při 409 (stará revize)
// se stav změní na „conflict“ a koncept zůstane; člověk ho zahodí tlačítkem Obnovit (reload). Revize se čte z ref,
// takže automatické uložení hned po předchozím (nebo po smazání) nikdy nepošle zastaralou `expected_revision`.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/shared/types/logic/types";
import { serialize, sortMoments, type Storyboard } from "./storyboard-model";

export type StoryboardStatus = "loading" | "idle" | "saving" | "conflict" | "error";
type Loaded = { storyboard: Storyboard | null; revision: number; readOnly: boolean; animations: { id: string; label: string }[] };

export function useStoryboardStore(project: string, workspace: string, nodeId: string) {
  const [draft, setDraft] = useState<Storyboard | null>(null);
  const [saved, setSaved] = useState("");
  const [revision, setRevision] = useState(0);
  const [serverReadOnly, setServerReadOnly] = useState(false);
  const [animations, setAnimations] = useState<{ id: string; label: string }[]>([]);
  const [status, setStatus] = useState<StoryboardStatus>("loading");
  const [message, setMessage] = useState("");
  /** Čas posledního úspěšného uložení v tomto okně (štítek „Uloženo HH:MM“). */
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const revisionRef = useRef(0);
  const ticket = useRef(0);
  const draftRef = useRef<Storyboard | null>(null);
  draftRef.current = draft;

  const reload = useCallback(async () => {
    const mine = ++ticket.current;
    setStatus("loading"); setMessage("");
    try {
      const value = await api<Loaded>("/api/storyboard?" + new URLSearchParams({ project, workspace, nodeId }));
      if (mine !== ticket.current) return;
      const board = value.storyboard ? sortMoments(value.storyboard) : null;
      setDraft(board);
      setSaved(board ? JSON.stringify(serialize(board)) : "");
      setRevision(value.revision); revisionRef.current = value.revision;
      setServerReadOnly(value.readOnly);
      setAnimations(value.animations);
      setStatus("idle");
    } catch (e) {
      if (mine !== ticket.current) return;
      setStatus("error"); setMessage(e instanceof Error ? e.message : String(e));
    }
  }, [project, workspace, nodeId]);
  useEffect(() => { void reload(); return () => { ticket.current++; }; }, [reload]);

  /** Uloží koncept (nebo smaže, když je `next` null). Vrací true při úspěchu. */
  const save = useCallback(async (next: Storyboard | null): Promise<boolean> => {
    setStatus("saving"); setMessage("");
    try {
      const body = next ? serialize(sortMoments(next)) : null;
      const result = await api<{ revision: number }>("/api/storyboard", { project, workspace, nodeId, expected_revision: revisionRef.current, storyboard: body });
      setRevision(result.revision); revisionRef.current = result.revision;
      setSavedAt(new Date());
      // Úpravy napsané během ukládání zůstávají (autosave je uloží hned potom); seřadí se jen právě uložený koncept.
      setDraft((current) => (!next ? null : current === next ? sortMoments(next) : current));
      setSaved(next ? JSON.stringify(serialize(sortMoments(next))) : "");
      setStatus("idle");
      if (next) {
        // Backend doplnil id momentů a podkladů a mohl vrátit `answered` na false: převezme se jeho podoba,
        // ale jen když člověk mezitím koncept nezměnil (jinak by nové úpravy zmizely).
        const sent = JSON.stringify(body);
        const canonical = await api<Loaded>("/api/storyboard?" + new URLSearchParams({ project, workspace, nodeId }));
        const current = draftRef.current;
        if (canonical.storyboard && canonical.revision === result.revision && current && JSON.stringify(serialize(sortMoments(current))) === sent) {
          const board = sortMoments(canonical.storyboard);
          setDraft(board);
          setSaved(JSON.stringify(serialize(board)));
        }
      }
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) { setStatus("conflict"); setMessage(e.message); }
      else { setStatus("error"); setMessage(e instanceof Error ? e.message : String(e)); }
      return false;
    }
  }, [project, workspace, nodeId]);

  const dirty = draft !== null && JSON.stringify(serialize(draft)) !== saved;
  return { draft, setDraft, dirty, revision, revisionRef, savedAt, serverReadOnly, animations, status, message, reload, save };
}
