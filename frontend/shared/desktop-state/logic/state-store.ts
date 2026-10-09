// Sdílená logika načtení/uložení State s CAS ochranou (expectedRevision) a ochranou
// proti zastaralým async odpovědím (scoped A->B->A). Interní modul, nikoli veřejný export.
import { useEffect, useRef, useState } from "react";
import { trackSaveWrite } from "@/shared/hooks/logic/save-coordinator";
import { errorMessage, fetchState, saveState } from "@/shared/desktop-state/logic/api";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { emptyDesktopState } from "@/shared/desktop-state/logic/types";
import type { Rule, Decision, StateResponse } from "@/shared/desktop-state/logic/types";
import { api } from "@/shared/types/logic/types";

export type DesktopStateHandle = {
  mutateItem: (kind: "rule" | "decision", expected: Rule | Decision | null, item: Rule | Decision | null) => Promise<boolean>;
  state: DesktopState;
  revision: number;
  readOnly: boolean;
  loading: boolean;
  error: string;
  /**
   * Znovu načte stav ze serveru (např. po zápisu asistenta z jiného procesu, docs/asistent.md §6.2).
   * Když právě běží uložení, počká na jeho konec: rozpracovaná změna se nepřepíše ani nezahodí.
   */
  reload: () => void;
  /** Aplikuje mutaci na aktuální stav a uloží ji s CAS ochranou. */
  mutate: (fn: (current: DesktopState) => DesktopState) => Promise<boolean>;
  /** Převezme stav z odpovědi adresného zápisu (autonomie, hromadné potvrzení) a pošle ho ostatním instancím. */
  apply: (value: StateResponse) => void;
};

type Published = { state: DesktopState; revision: number; readOnly: boolean };
type Listener = (value: Published) => void;
// Více instancí hooku nad stejným scope (panel uzlu, bloky na plátně) sdílí jednu revizi:
// po úspěšném čtení či zápisu jedné instance dostanou ostatní tentýž stav, jinak by další
// zápis narazil na CAS („revize nesouhlasí“) jen proto, že ho provedlo jiné okno téže stránky.
const listeners = new Map<string, Set<Listener>>();

function publish(scope: string, value: Published, except: Listener) {
  for (const listener of listeners.get(scope) ?? []) if (listener !== except) listener(value);
}

export function useDesktopState(project: string, workspace: string): DesktopStateHandle {
  const [state, setState] = useState<DesktopState>(emptyDesktopState());
  const [revision, setRevision] = useState(0);
  const [readOnly, setReadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const scopeKey = useRef("");
  const listener = useRef<Listener>(() => {});
  listener.current = (value) => {
    setState(value.state);
    setRevision(value.revision);
    setReadOnly(value.readOnly);
  };
  const self = useRef<Listener>((value) => listener.current(value));
  const saving = useRef(0);
  const reloadQueued = useRef(false);

  useEffect(() => {
    const scope = `${project}::${workspace}`;
    const set = listeners.get(scope) ?? new Set<Listener>();
    set.add(self.current);
    listeners.set(scope, set);
    return () => {
      set.delete(self.current);
      if (set.size === 0) listeners.delete(scope);
    };
  }, [project, workspace]);

  const load = () => {
    const ticket = ++generation.current;
    const scope = `${project}::${workspace}`;
    scopeKey.current = scope;
    setLoading(true);
    setError("");
    fetchState(project, workspace)
      .then((value) => {
        if (ticket !== generation.current || scopeKey.current !== scope) return;
        setState(value.state);
        setRevision(value.revision);
        setReadOnly(value.readOnly);
        setLoading(false);
        publish(scope, value, self.current);
      })
      .catch((e) => {
        if (ticket !== generation.current || scopeKey.current !== scope) return;
        setError(errorMessage(e));
        setLoading(false);
      });
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project, workspace]);

  const mutate = async (fn: (current: DesktopState) => DesktopState): Promise<boolean> => {
    if (readOnly) {
      setError("Main je pouze pro čtení; změny nelze uložit.");
      return false;
    }
    const ticket = generation.current;
    const scope = `${project}::${workspace}`;
    const previous = state;
    const previousRevision = revision;
    const next = fn(previous);
    // Apply immediately so controls (e.g. native checkboxes) reflect the user's action without
    // waiting on the round trip; reconciled with the server's exact saved state below, or rolled
    // back on failure/staleness.
    setState(next);
    saving.current++;
    try {
      const value = await trackSaveWrite(project, workspace, saveState(project, workspace, previousRevision, next));
      if (ticket !== generation.current || scopeKey.current !== scope) return false;
      setState(value.state);
      setRevision(value.revision);
      setReadOnly(value.readOnly);
      setError("");
      publish(scope, value, self.current);
      if (value.graphChanged) window.dispatchEvent(new CustomEvent("opora:spawned", { detail: { project, workspace } }));
      return true;
    } catch (e) {
      if (ticket !== generation.current || scopeKey.current !== scope) return false;
      setState(previous);
      setError(errorMessage(e));
      return false;
    } finally {
      saving.current--;
      if (saving.current === 0 && reloadQueued.current) {
        reloadQueued.current = false;
        load();
      }
    }
  };

  const reload = () => {
    if (saving.current > 0) reloadQueued.current = true;
    else load();
  };

  const mutateItem: DesktopStateHandle["mutateItem"] = async (kind, expected, item) => {
    if (readOnly || (!expected && !item)) return false;
    const ticket = generation.current;
    const scope = `${project}::${workspace}`;
    saving.current++;
    try {
      const value = await trackSaveWrite(project, workspace, api<StateResponse>(`/api/desktop-v3/${kind}`, {
        project, workspace, id: (item ?? expected)!.id, expected, item,
        op: !expected ? "add" : !item ? "remove" : "update",
      }));
      if (ticket !== generation.current || scopeKey.current !== scope) return false;
      setState(value.state); setRevision(value.revision); setReadOnly(value.readOnly); setError("");
      publish(scope, value, self.current);
      if (value.graphChanged) window.dispatchEvent(new CustomEvent("opora:spawned", { detail: { project, workspace } }));
      return true;
    } catch (e) {
      if (ticket === generation.current && scopeKey.current === scope) setError(errorMessage(e));
      return false;
    } finally {
      saving.current--;
      if (saving.current === 0 && reloadQueued.current) { reloadQueued.current = false; load(); }
    }
  };
  const apply = (value: StateResponse) => {
    const scope = `${project}::${workspace}`;
    generation.current++;
    setState(value.state); setRevision(value.revision); setReadOnly(value.readOnly); setError("");
    publish(scope, value, self.current);
  };
  return { state, revision, readOnly, loading, error, reload, mutate, mutateItem, apply };
}
