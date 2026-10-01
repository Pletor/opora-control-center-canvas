// Sdílená logika načtení/uložení State s CAS ochranou (expectedRevision) a ochranou
// proti zastaralým async odpovědím (scoped A->B->A). Interní modul, nikoli veřejný export.
import { useEffect, useRef, useState } from "react";
import { errorMessage, fetchState, saveState } from "@/shared/desktop-state/logic/api";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { emptyDesktopState } from "@/shared/desktop-state/logic/types";

export type DesktopStateHandle = {
  state: DesktopState;
  revision: number;
  readOnly: boolean;
  loading: boolean;
  error: string;
  reload: () => void;
  /** Aplikuje mutaci na aktuální stav a uloží ji s CAS ochranou. */
  mutate: (fn: (current: DesktopState) => DesktopState) => Promise<boolean>;
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
    try {
      const value = await saveState(project, workspace, previousRevision, next);
      if (ticket !== generation.current || scopeKey.current !== scope) return false;
      setState(value.state);
      setRevision(value.revision);
      setReadOnly(value.readOnly);
      setError("");
      publish(scope, value, self.current);
      return true;
    } catch (e) {
      if (ticket !== generation.current || scopeKey.current !== scope) return false;
      setState(previous);
      setError(errorMessage(e));
      return false;
    }
  };

  return { state, revision, readOnly, loading, error, reload: load, mutate };
}
