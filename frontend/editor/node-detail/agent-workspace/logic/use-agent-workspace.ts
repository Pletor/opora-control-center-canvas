// Hook nad `/api/desktop-v3/agent-workspace`: stejný fetch helper a stejný tvar chyby jako u textu
// uzlu (NodeTextEditor přes `api()` z shared/types). Ukládá jen sekce, které se skutečně změnily
// (`sections` v POST je částečný zápis), pod CAS `expectedRevision`. Server vrací 409 na neshodu
// revize i na jinak neplatný zápis (uzavřená karta, main jen ke čtení); u revize se text chyby vždy
// začíná „Konflikt“ (viz `backend/editor/agent_memory/agent_workspace.py`) — jen v tom případě hook
// prostor znovu načte a ukáže stejnou hlášku jako ostatní textové editory uzlu, aby konflikt vypadal
// v celé aplikaci stejně. Rozepsaný text drží komponenta (AgentWorkspace); tenhle hook jen mluví se
// serverem a hlídá revizi.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import {
  emptyWorkspace,
  type AgentWorkspaceRecord,
  type AgentWorkspaceSections,
} from "@/editor/node-detail/agent-workspace/logic/agent-workspace";

// Stabilní reference: `record` se v klidu (mezi načtením a uložením) nemění, i když komponenta
// znovu vykreslí — díky tomu na ni může komponenta bezpečně navěsit useEffect podle identity.
const EMPTY_RECORD = emptyWorkspace();

/** Stejná hláška jako u konfliktu textu uzlu (`NodeTextEditor`) — jeden slovník pro celou aplikaci. */
export const AGENT_WORKSPACE_CONFLICT_MESSAGE =
  "Konflikt: uložená revize se změnila. Rozepsaný text je zachovaný.";

type AgentWorkspaceResponse = { revision: number; workspace: AgentWorkspaceRecord; readOnly: boolean };

export type UseAgentWorkspace = {
  record: AgentWorkspaceRecord;
  loading: boolean;
  error: string;
  readOnly: boolean;
  save: (sections: Partial<AgentWorkspaceSections>) => Promise<void>;
};

export function useAgentWorkspace(project: string, workspace: string, nodeId: string): UseAgentWorkspace {
  const [record, setRecord] = useState<AgentWorkspaceRecord>(EMPTY_RECORD);
  const [revision, setRevision] = useState(0);
  const [readOnly, setReadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const generation = useRef(0);
  // Poslední scope, jak ho zná i probíhající async volání; `save` a `load` čtou odsud, ne z uzávěru.
  const scope = useRef({ project, workspace, nodeId });
  scope.current = { project, workspace, nodeId };
  const revisionRef = useRef(revision);
  revisionRef.current = revision;

  const load = useCallback(() => {
    const ticket = ++generation.current;
    const { project, workspace, nodeId } = scope.current;
    setLoading(true);
    api<AgentWorkspaceResponse>(
      "/api/desktop-v3/agent-workspace?" + new URLSearchParams({ project, workspace, nodeId }),
    )
      .then((value) => {
        if (ticket !== generation.current) return;
        setRecord(value.workspace);
        setRevision(value.revision);
        setReadOnly(value.readOnly);
        setLoading(false);
      })
      .catch((e) => {
        if (ticket !== generation.current) return;
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    setError("");
    load();
    // Nové ID (uzel, projekt, prostředí) je nový scope; `load` samo drží aktuální hodnoty přes `scope`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project, workspace, nodeId]);

  const save = useCallback(async (sections: Partial<AgentWorkspaceSections>) => {
    if (!Object.keys(sections).length) return;
    const ticket = generation.current;
    const { project, workspace, nodeId } = scope.current;
    try {
      const value = await api<AgentWorkspaceResponse>("/api/desktop-v3/agent-workspace", {
        project,
        workspace,
        nodeId,
        expectedRevision: revisionRef.current,
        sections,
        by: "human",
      });
      if (ticket !== generation.current) return;
      setRecord(value.workspace);
      setRevision(value.revision);
      setReadOnly(value.readOnly);
      setError("");
    } catch (e) {
      if (ticket !== generation.current) return;
      const message = e instanceof Error ? e.message : String(e);
      if (message.startsWith("Konflikt")) {
        // Revize se změnila jinde: rozepsaný text komponenta nezahazuje, jen se znovu načte, co je uloženo.
        setError(AGENT_WORKSPACE_CONFLICT_MESSAGE);
        load();
      } else {
        setError(message);
      }
    }
  }, [load]);

  return { record, loading, error, readOnly, save };
}
