// Čtení záznamu činnosti pro otevřený panel: dvě nezávislé stránkované řady (Já = human, Agenti =
// agent) v rozsahu projektu, pracovního prostoru a volitelně jedné karty. Načítá jen, když je panel
// otevřený; při změně `refreshKey` (otisk plátna + revize) přiloží novou první stránku k načteným.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { activityQuery, appendOlder, mergeFresh, type ActivityPage, type Actor } from "./activity-log";

export type ActorLog = ActivityPage & { loading: boolean; error: string };
export type ActivityLogState = Record<Actor, ActorLog> & { loadOlder: (actor: Actor) => void };

const EMPTY: ActorLog = { entries: [], nextBefore: null, loading: false, error: "" };
const ACTORS: Actor[] = ["human", "agent"];

export function useActivityLog({ project, workspace, nodeId, enabled, refreshKey }: {
  project: string; workspace: string; nodeId: string | null; enabled: boolean; refreshKey: string;
}): ActivityLogState {
  const [logs, setLogs] = useState<Record<Actor, ActorLog>>({ human: EMPTY, agent: EMPTY });
  const scope = JSON.stringify([project, workspace, nodeId]);
  const current = useRef(scope);
  current.current = scope;
  const patch = useCallback((actor: Actor, change: (log: ActorLog) => ActorLog) => {
    setLogs((all) => ({ ...all, [actor]: change(all[actor]) }));
  }, []);

  // Jiný rozsah = jiný záznam: načtené se zahodí, aby se nemíchaly karty ani prostory.
  useEffect(() => { setLogs({ human: EMPTY, agent: EMPTY }); }, [scope]);

  useEffect(() => {
    if (!enabled) return;
    const owner = scope;
    for (const actor of ACTORS) {
      patch(actor, (log) => ({ ...log, loading: true }));
      api<ActivityPage>(activityQuery({ project, workspace, actor, nodeId }))
        .then((fresh) => { if (current.current === owner) patch(actor, (log) => ({ ...mergeFresh(log, fresh), loading: false, error: "" })); })
        .catch((cause) => { if (current.current === owner) patch(actor, (log) => ({ ...log, loading: false, error: cause instanceof Error ? cause.message : String(cause) })); });
    }
  }, [enabled, refreshKey, scope, project, workspace, nodeId, patch]);

  const loadOlder = useCallback((actor: Actor) => {
    const before = logs[actor].nextBefore;
    if (before === null || logs[actor].loading) return;
    const owner = scope;
    patch(actor, (log) => ({ ...log, loading: true }));
    api<ActivityPage>(activityQuery({ project, workspace, actor, nodeId, before }))
      .then((older) => { if (current.current === owner) patch(actor, (log) => ({ ...appendOlder(log, older), loading: false, error: "" })); })
      .catch((cause) => { if (current.current === owner) patch(actor, (log) => ({ ...log, loading: false, error: cause instanceof Error ? cause.message : String(cause) })); });
  }, [logs, scope, project, workspace, nodeId, patch]);

  return { ...logs, loadOlder };
}
