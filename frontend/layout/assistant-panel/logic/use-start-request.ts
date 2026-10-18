// Žádost o nový úkol zvenku panelu (živý panel domény: „Nová relace“ u worktree, karty nebo hlavní
// relace). App ji předá s pořadovým číslem; panel úkol založí jednou, až je `claude` dostupný, a
// vybere ho. Zpráva se neposílá: model běží jen na zprávu člověka (docs/asistent.md).
// `nodeId` váže úkol ke kartě; hlavní relace a relace worktree ho nemají. `sectorId` ho váže k sektoru
// (Kancelář); `draft` je předvyplněná zpráva: po založení ji `onStarted` předá panelu, ten ji vloží do
// prázdného kompozéru nového úkolu (`start-draft.ts`), neposílá se.
import { useEffect, useRef } from "react";
import type { AssistantSession } from "./assistant-api";
import { pendingSelection, type SelectRequest } from "./select-request";

export type StartRequest = { seq: number; workspace: string; nodeId: string | null; sectorId: string | null; title: string; draft?: string };

export function useStartRequest(request: StartRequest | null | undefined, available: boolean,
  create: (options: { workspace?: string; title?: string; nodeId?: string; sectorId?: string }) => Promise<AssistantSession | null>,
  onStarted?: (session: AssistantSession, draft: string) => void) {
  const handled = useRef(0);
  useEffect(() => {
    if (!request || !available || request.seq === handled.current) return;
    handled.current = request.seq;
    const draft = request.draft;
    void create({ workspace: request.workspace, title: request.title, ...(request.nodeId ? { nodeId: request.nodeId } : {}), ...(request.sectorId ? { sectorId: request.sectorId } : {}) })
      .then((session) => { if (session && draft) onStarted?.(session, draft); });
  }, [request, available, create, onStarted]);
}

/** Výběr existujícího úkolu zvenku (čip relace v živém panelu); počká, až je úkol v seznamu. */
export function useSelectRequest(request: SelectRequest | null | undefined, sessions: AssistantSession[], select: (id: string) => void) {
  const handled = useRef(0);
  useEffect(() => {
    const id = pendingSelection(request, handled.current, sessions.map((session) => session.id));
    if (!id || !request) return;
    handled.current = request.seq;
    select(id);
  }, [request, sessions, select]);
}
