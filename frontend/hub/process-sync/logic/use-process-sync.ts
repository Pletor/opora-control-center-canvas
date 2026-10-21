import { useEffect, useRef, useState } from "react";
import { browserProcessEnvironment, emptyProcess, watchProcess, type ProcessState } from "./process-reader";

export function useProcessSync(project: string, workspace: string) {
  const key = JSON.stringify([project, workspace]);
  const [state, setState] = useState<ProcessState & { key: string }>(() => ({ ...emptyProcess(), key }));
  const watcher = useRef<{ key: string; reader: ReturnType<typeof watchProcess> } | null>(null);
  useEffect(() => {
    const reader = watchProcess(project, workspace, next => setState({ ...next, key }), browserProcessEnvironment());
    const current = { key, reader }; watcher.current = current;
    return () => { reader.close(); if (watcher.current === current) watcher.current = null; };
  }, [key, project, workspace]);
  const shown = state.key === key ? state : emptyProcess();
  return { snapshot: shown.snapshot, busy: shown.busy, error: shown.error, refresh: () => {
    if (watcher.current?.key === key) watcher.current.reader.refresh();
  } };
}
