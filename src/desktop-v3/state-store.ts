// Sdílená logika načtení/uložení State s CAS ochranou (expectedRevision) a ochranou
// proti zastaralým async odpovědím (scoped A->B->A). Interní modul, nikoli veřejný export.
import { useEffect, useRef, useState } from "react";
import { errorMessage, fetchState, saveState } from "@/desktop-v3/api";
import type { DesktopState } from "@/desktop-v3/types";
import { emptyDesktopState } from "@/desktop-v3/types";

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

export function useDesktopState(project: string, workspace: string): DesktopStateHandle {
  const [state, setState] = useState<DesktopState>(emptyDesktopState());
  const [revision, setRevision] = useState(0);
  const [readOnly, setReadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const scopeKey = useRef("");

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
