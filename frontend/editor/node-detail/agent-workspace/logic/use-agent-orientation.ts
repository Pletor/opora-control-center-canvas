// Read-only načtení stejného node-briefu, který nese orientaci i komunikační stránky.
// Každá odpověď je svázaná s přesným scope; starý balíček se nikdy neexportuje po přepnutí karty.
// Hook drží jen rodič (AgentWorkspace) a výsledek rozdá dílcům v props — brief se u jedné karty
// načítá právě jednou, i když ho čte přehled i orientace.
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchNodeBrief } from "@/shared/desktop-state/logic/api";
import type { NodeBrief } from "@/shared/desktop-state/logic/types";

/** To, co rodič rozdá dílcům: jednou načtený brief, jeho stav a ruční znovunačtení. */
export type AgentOrientationFeed = {
  brief: NodeBrief | null;
  loading: boolean;
  error: string;
  reload: () => void;
};

export function useAgentOrientation(project: string, workspace: string, nodeId: string): AgentOrientationFeed {
  const [brief, setBrief] = useState<NodeBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const ticket = useRef(0);
  const scope = `${project}\u0000${workspace}\u0000${nodeId}`;
  const reload = useCallback(() => setReloadKey((value) => value + 1), []);

  useEffect(() => {
    const current = ++ticket.current;
    setBrief(null); setLoading(true); setError("");
    fetchNodeBrief(project, workspace, nodeId)
      .then((value) => { if (current === ticket.current) setBrief(value); })
      .catch((reason: unknown) => {
        if (current === ticket.current) { setBrief(null); setError(reason instanceof Error ? reason.message : String(reason)); }
      })
      .finally(() => { if (current === ticket.current) setLoading(false); });
    return () => { ++ticket.current; };
  }, [scope, reloadKey, project, workspace, nodeId]);

  return { brief, loading, error, reload };
}
