// Žádost o nový úkol zvenku panelu (živý panel domény: „Nová relace“ u worktree, karty nebo hlavní
// relace). App ji předá s pořadovým číslem; panel úkol založí jednou, až je `claude` dostupný, a
// vybere ho. Zpráva se neposílá: model běží jen na zprávu člověka (docs/asistent.md).
// `nodeId` váže úkol ke kartě; hlavní relace a relace worktree ho nemají.
import { useEffect, useRef } from "react";
import type { AssistantSession } from "./assistant-api";

export type StartRequest = { seq: number; workspace: string; nodeId: string | null; title: string };

export function useStartRequest(request: StartRequest | null | undefined, available: boolean,
  create: (options: { workspace?: string; title?: string; nodeId?: string }) => Promise<AssistantSession | null>) {
  const handled = useRef(0);
  useEffect(() => {
    if (!request || !available || request.seq === handled.current) return;
    handled.current = request.seq;
    void create({ workspace: request.workspace, title: request.title, ...(request.nodeId ? { nodeId: request.nodeId } : {}) });
  }, [request, available, create]);
}
