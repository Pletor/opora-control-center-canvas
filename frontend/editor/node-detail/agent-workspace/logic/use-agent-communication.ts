// Síťový stav komunikace: načítá až po otevření, drží oddělené kurzory obou směrů a každý pozdní
// výsledek zahodí podle generation. Draft zůstává v komponentě, proto ho síťová chyba nemůže smazat.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import {
  canCreateReceipt, canSendMessage, draftFingerprint, makeMessagePayload, makeReceiptPayload, matchesMessageReadback,
  mergeMessagePage, type AgentMessage, type CommunicationScope, type MessageDraft, type ReceiptDraft,
} from "@/editor/node-detail/agent-workspace/logic/agent-communication";

type Direction = "incoming" | "outgoing";
type MessagePage = { messages: AgentMessage[]; readOnly: boolean; targets: { id: string; name: string }[]; hasMore: boolean; nextBefore: number | null };
type PostResult = { message: AgentMessage };
type ListState = { messages: AgentMessage[]; hasMore: boolean; nextBefore: number | null };
const EMPTY_LIST: ListState = { messages: [], hasMore: false, nextBefore: null };
const requestId = (): string => crypto.randomUUID();

const sameScope = (left: CommunicationScope, right: CommunicationScope): boolean =>
  left.project === right.project && left.workspace === right.workspace && left.nodeId === right.nodeId;
const messageMatchesScope = (message: AgentMessage, scope: CommunicationScope, direction: Direction): boolean =>
  message.project === scope.project && message.workspace === scope.workspace &&
  (direction === "incoming" ? message.targetNodeId === scope.nodeId : message.sourceNodeId === scope.nodeId);

export type AgentCommunicationModel = {
  incoming: ListState; outgoing: ListState; targets: { id: string; name: string }[];
  /** True až po prvním úspěšném načtení této karty: do té doby jsou prázdné seznamy nevědomost, ne nula. */
  loaded: boolean;
  loading: boolean; writing: boolean; readOnly: boolean; error: string;
  reload: () => Promise<void>; loadOlder: (direction: Direction) => Promise<void>;
  send: (draft: MessageDraft, outerReadOnly: boolean) => Promise<boolean>;
  receipt: (message: AgentMessage, draft: ReceiptDraft, outerReadOnly: boolean) => Promise<boolean>;
};

export function useAgentCommunication(scope: CommunicationScope, open: boolean): AgentCommunicationModel {
  const [incoming, setIncoming] = useState<ListState>(EMPTY_LIST);
  const [outgoing, setOutgoing] = useState<ListState>(EMPTY_LIST);
  const [targets, setTargets] = useState<{ id: string; name: string }[]>([]);
  const [serverReadOnly, setServerReadOnly] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [writing, setWriting] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const writeLock = useRef(false);
  const retry = useRef<{ fingerprint: string; key: string } | null>(null);
  const scopeRef = useRef(scope);
  scopeRef.current = scope;

  const fetchPage = useCallback((requestScope: CommunicationScope, direction: Direction, before?: number | null) => {
    const params = new URLSearchParams({ ...requestScope, direction });
    if (before !== undefined && before !== null) params.set("before", String(before));
    return api<MessagePage>("/api/desktop-v3/agent-messages?" + params);
  }, []);

  const reload = useCallback(async () => {
    const requestScope = scopeRef.current;
    const ticket = ++generation.current;
    setLoading(true);
    setError("");
    try {
      const [inPage, outPage] = await Promise.all([
        fetchPage(requestScope, "incoming"), fetchPage(requestScope, "outgoing"),
      ]);
      if (ticket !== generation.current || !sameScope(requestScope, scopeRef.current)) return;
      setIncoming({ messages: inPage.messages, hasMore: inPage.hasMore, nextBefore: inPage.nextBefore });
      setOutgoing({ messages: outPage.messages, hasMore: outPage.hasMore, nextBefore: outPage.nextBefore });
      setTargets(outPage.targets.filter((target) => target.id !== requestScope.nodeId));
      setServerReadOnly(inPage.readOnly || outPage.readOnly);
      setLoaded(true);
    } catch (e) {
      if (ticket === generation.current && sameScope(requestScope, scopeRef.current)) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (ticket === generation.current && sameScope(requestScope, scopeRef.current)) setLoading(false);
    }
  }, [fetchPage]);

  // Po přepnutí karty patří počty zase briefu: zprávy nové karty ještě nikdo nenačetl.
  useEffect(() => { setLoaded(false); }, [scope.project, scope.workspace, scope.nodeId]);

  useEffect(() => {
    if (open) void reload();
    // Cleanup ruší i odpovědi po změně scope a při unmountu, nejen při zavřeném panelu.
    return () => { ++generation.current; };
  }, [open, scope.project, scope.workspace, scope.nodeId, reload]);

  const loadOlder = useCallback(async (direction: Direction) => {
    const list = direction === "incoming" ? incoming : outgoing;
    if (!list.hasMore || list.nextBefore === null || loading) return;
    const requestScope = scopeRef.current;
    const ticket = generation.current;
    setLoading(true);
    try {
      const page = await fetchPage(requestScope, direction, list.nextBefore);
      if (ticket !== generation.current || !sameScope(requestScope, scopeRef.current)) return;
      const apply = direction === "incoming" ? setIncoming : setOutgoing;
      apply((current) => ({ messages: mergeMessagePage(current.messages, page.messages), hasMore: page.hasMore, nextBefore: page.nextBefore }));
    } catch (e) {
      if (ticket === generation.current && sameScope(requestScope, scopeRef.current)) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (ticket === generation.current && sameScope(requestScope, scopeRef.current)) setLoading(false);
    }
  }, [fetchPage, incoming, loading, outgoing]);

  const readback = useCallback(async (expected: AgentMessage, direction: Direction, expectedReceipt?: ReceiptDraft) => {
    const requestScope = scopeRef.current;
    const ticket = generation.current;
    if (!messageMatchesScope(expected, requestScope, direction)) return false;
    // Nejnovější stránky obnovují panel, omezená stránka vždy obsahuje vybranou starší zprávu.
    const [inPage, outPage, verificationPage] = await Promise.all([
      fetchPage(requestScope, "incoming"),
      fetchPage(requestScope, "outgoing"),
      fetchPage(requestScope, direction, expected.sequence + 1),
    ]);
    if (ticket !== generation.current || !sameScope(requestScope, scopeRef.current)) return false;
    const verified = verificationPage.messages.find((item) => item.id === expected.id);
    const incomingFresh = direction === "incoming" ? mergeMessagePage(inPage.messages, verificationPage.messages) : inPage.messages;
    const outgoingFresh = direction === "outgoing" ? mergeMessagePage(outPage.messages, verificationPage.messages) : outPage.messages;
    setIncoming((current) => ({
      messages: mergeMessagePage(incomingFresh, current.messages), hasMore: inPage.hasMore, nextBefore: inPage.nextBefore,
    }));
    setOutgoing((current) => ({
      messages: mergeMessagePage(outgoingFresh, current.messages), hasMore: outPage.hasMore, nextBefore: outPage.nextBefore,
    }));
    setTargets(outPage.targets.filter((target) => target.id !== requestScope.nodeId));
    setServerReadOnly(inPage.readOnly || outPage.readOnly);
    return verified !== undefined && matchesMessageReadback(verified, expected, expectedReceipt);
  }, [fetchPage]);

  const send = useCallback(async (draft: MessageDraft, outerReadOnly: boolean) => {
    const currentScope = scopeRef.current;
    if (writeLock.current || !canSendMessage(currentScope, draft, outerReadOnly || serverReadOnly)) return false;
    const fingerprint = draftFingerprint(draft);
    if (!retry.current || retry.current.fingerprint !== fingerprint) retry.current = { fingerprint, key: requestId() };
    writeLock.current = true;
    const ticket = ++generation.current;
    setWriting(true); setError("");
    try {
      const result = await api<PostResult>("/api/desktop-v3/agent-messages", makeMessagePayload(currentScope, draft, retry.current.key));
      if (ticket !== generation.current || !sameScope(currentScope, scopeRef.current)) return false;
      if (!messageMatchesScope(result.message, currentScope, "outgoing")) throw new Error("Odpověď odeslání patří do jiného scope.");
      if (!await readback(result.message, "outgoing")) throw new Error("Zpětné načtení neobsahuje přesnou odeslanou zprávu.");
      retry.current = null;
      return true;
    } catch (e) {
      if (ticket === generation.current && sameScope(currentScope, scopeRef.current)) setError(e instanceof Error ? e.message : String(e));
      return false;
    } finally {
      // Tento zámek patří konkrétnímu POSTu; generation se při zavření/reloadu mění, zámek ne.
      writeLock.current = false;
      setWriting(false);
    }
  }, [readback, serverReadOnly]);

  const receipt = useCallback(async (message: AgentMessage, draft: ReceiptDraft, outerReadOnly: boolean) => {
    const currentScope = scopeRef.current;
    if (writeLock.current || !canCreateReceipt(draft, outerReadOnly || serverReadOnly)) return false;
    if (!messageMatchesScope(message, currentScope, "incoming")) return false;
    writeLock.current = true;
    const ticket = ++generation.current;
    setWriting(true); setError("");
    try {
      const result = await api<PostResult>(
        "/api/desktop-v3/agent-message-receipt",
        makeReceiptPayload(currentScope, message.id, message.digest, draft),
      );
      if (ticket !== generation.current || !sameScope(currentScope, scopeRef.current)) return false;
      if (!messageMatchesScope(result.message, currentScope, "incoming") || result.message.id !== message.id || result.message.digest !== message.digest) {
        throw new Error("Odpověď potvrzení patří do jiného scope nebo verze zprávy.");
      }
      if (!await readback(result.message, "incoming", draft)) throw new Error("Zpětné načtení neobsahuje přesné potvrzení převzetí.");
      return true;
    } catch (e) {
      if (ticket === generation.current && sameScope(currentScope, scopeRef.current)) setError(e instanceof Error ? e.message : String(e));
      return false;
    } finally {
      writeLock.current = false;
      setWriting(false);
    }
  }, [readback, serverReadOnly]);

  return { incoming, outgoing, targets, loaded, loading, writing, readOnly: serverReadOnly, error, reload, loadOlder, send, receipt };
}
