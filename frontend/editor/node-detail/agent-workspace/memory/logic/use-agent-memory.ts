// Síťový stav paměti role u jedné karty. Přepínač a knihovna rolí se čtou jednou při připojení
// dílku; vybavení, zápis, půjčka i rozdání klíčů rolím běží **jen na výslovný pokyn člověka** —
// hook nikdy nepolluje a nikdy sám nezapisuje (docs/pamet-agentu.md: do sdílené paměti role
// zapisuje člověk). Každá odpověď je svázaná s přesným scope a pořadovým číslem, takže pozdní
// výsledek po přepnutí karty nebo po odmountování nic nepřepíše. Rozepsané texty zůstávají
// v komponentě, aby je chyba sítě nesmazala.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import {
  canLend,
  canRecall,
  canRemember,
  lendPayload,
  memoryModel,
  provisionPayload,
  recallPayload,
  rememberPayload,
  type LendDraft,
  type MemoryRecall,
  type MemoryRole,
  type MemoryScope,
  type MemoryState,
  type MemoryStatus,
  type ProvisionResult,
  type RememberDraft,
} from "@/editor/node-detail/agent-workspace/memory/logic/agent-memory";

type RolesResponse = { roles?: unknown };
type RememberResponse = { status?: string; uri?: string; reason?: string };

const sameScope = (left: MemoryScope, right: MemoryScope): boolean =>
  left.project === right.project && left.workspace === right.workspace && left.nodeId === right.nodeId;
const message = (reason: unknown): string => (reason instanceof Error ? reason.message : String(reason));

export type AgentMemoryFeed = {
  status: MemoryStatus | null;
  /** Stav přepínače aplikace; co z něj platí pro tuhle kartu, složí teprve `memoryModel`. */
  state: MemoryState;
  roles: MemoryRole[];
  /** Co se ukazuje jako paměť role: nejdřív z briefu karty, po „Vybavit“ odpověď serveru. */
  recall: MemoryRecall | null;
  /** True teprve po vlastním vybavení; do té doby je seznam z briefu a panel to má přiznat. */
  queried: boolean;
  /** Poslední půjčka zvlášť, aby se cizí zkušenost nikdy nesmíchala s vlastní. */
  lent: MemoryRecall | null;
  /** Adresa posledního potvrzeného zápisu; prázdné, dokud člověk nic nezapsal. */
  saved: string;
  loading: boolean;
  busy: boolean;
  error: string;
  /** Běží právě `POST /api/memory/provision`; tlačítko „Založit klíče rolí“ se zamkne. */
  provisioning: boolean;
  /** Poslední výsledek rozdání klíčů; null, dokud se nikdy nespustilo. */
  provisionResult: ProvisionResult | null;
  refresh: () => Promise<void>;
  recallNow: (query: string) => Promise<boolean>;
  remember: (draft: RememberDraft, readOnly: boolean) => Promise<boolean>;
  lend: (draft: LendDraft) => Promise<boolean>;
  /** Rozdá rolím klíče u OpenVikingu a hned poté přečte stav znovu (`refresh`). */
  provision: () => Promise<boolean>;
};

export function useAgentMemory(scope: MemoryScope, role: string | null, seed: MemoryRecall | null): AgentMemoryFeed {
  const [status, setStatus] = useState<MemoryStatus | null>(null);
  const [roles, setRoles] = useState<MemoryRole[]>([]);
  const [recall, setRecall] = useState<MemoryRecall | null>(seed);
  const [lent, setLent] = useState<MemoryRecall | null>(null);
  const [queried, setQueried] = useState(false);
  const [saved, setSaved] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [provisioning, setProvisioning] = useState(false);
  const [provisionResult, setProvisionResult] = useState<ProvisionResult | null>(null);
  const generation = useRef(0);
  const writeLock = useRef(false);
  const scopeRef = useRef(scope);
  const roleRef = useRef(role);
  scopeRef.current = scope;
  roleRef.current = role;
  const state = memoryModel(status, null).state;

  // Paměť z briefu je výchozí seznam, ne výsledek volání: převezme se jen dokud si člověk nic
  // nevybavil sám, jinak by pozdě dorazivší brief přepsal to, co má právě na obrazovce.
  useEffect(() => {
    if (!seed || queried) return;
    setRecall((current) => current ?? seed);
  }, [seed, queried]);

  /** Přepínač i knihovna rolí platí pro celou aplikaci, proto se čtou jednou, ne u každé karty. */
  const refresh = useCallback(async () => {
    const ticket = ++generation.current;
    setLoading(true);
    try {
      const [live, registry] = await Promise.all([
        api<MemoryStatus>("/api/memory/status"),
        api<RolesResponse>("/api/memory/roles"),
      ]);
      if (ticket !== generation.current) return;
      setStatus(live);
      setRoles(Array.isArray(registry.roles) ? (registry.roles as MemoryRole[]) : []);
      setError("");
    } catch (reason) {
      if (ticket !== generation.current) return;
      setStatus(null);
      setError(message(reason));
    } finally {
      if (ticket === generation.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    // Odmountování i přepnutí karty zneplatní všechny běžící odpovědi naráz.
    return () => { ++generation.current; };
  }, [refresh]);

  /** Rozdá klíče rolím jen na výslovný klik; nikdy samo, nikdy dvakrát najednou. */
  const provision = useCallback(async () => {
    if (provisioning) return false;
    setProvisioning(true);
    setError("");
    try {
      const value = await api<ProvisionResult>("/api/memory/provision", provisionPayload());
      setProvisionResult(value);
      await refresh();
      return true;
    } catch (reason) {
      setError(message(reason));
      return false;
    } finally {
      setProvisioning(false);
    }
  }, [provisioning, refresh]);

  /** Jediné místo, kde se čte paměť ze serveru; volá ho tlačítko „Vybavit“, nikdy efekt. */
  const recallNow = useCallback(async (query: string) => {
    const requestScope = scopeRef.current;
    const requestRole = roleRef.current;
    if (!canRecall(requestRole, query, state)) return false;
    const ticket = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const value = await api<MemoryRecall>("/api/memory/recall", recallPayload(requestScope, requestRole, query));
      if (ticket !== generation.current || !sameScope(requestScope, scopeRef.current)) return false;
      setRecall(value);
      setQueried(true);
      return true;
    } catch (reason) {
      if (ticket === generation.current && sameScope(requestScope, scopeRef.current)) setError(message(reason));
      return false;
    } finally {
      if (ticket === generation.current) setBusy(false);
    }
  }, [state]);

  /** Zápis potvrzuje člověk; zámek drží nejvýš jeden běžící POST, aby dvojí klik nezaložil dva zdroje. */
  const remember = useCallback(async (draft: RememberDraft, readOnly: boolean) => {
    const requestScope = scopeRef.current;
    if (writeLock.current || !canRemember(draft, readOnly, state)) return false;
    writeLock.current = true;
    const ticket = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const value = await api<RememberResponse>("/api/memory/remember", rememberPayload(requestScope, draft));
      if (ticket !== generation.current || !sameScope(requestScope, scopeRef.current)) return false;
      if (value.status !== "configured" || !value.uri) {
        setError(value.reason || "Zápis do paměti role se neuložil; server vrátil jiný stav než configured.");
        return false;
      }
      setSaved(value.uri);
      return true;
    } catch (reason) {
      if (ticket === generation.current && sameScope(requestScope, scopeRef.current)) setError(message(reason));
      return false;
    } finally {
      writeLock.current = false;
      if (ticket === generation.current) setBusy(false);
    }
  }, [state]);

  const lend = useCallback(async (draft: LendDraft) => {
    const requestScope = scopeRef.current;
    if (!canLend(draft, state)) return false;
    const ticket = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const value = await api<MemoryRecall>("/api/memory/lend", lendPayload(draft));
      if (ticket !== generation.current || !sameScope(requestScope, scopeRef.current)) return false;
      setLent(value);
      return true;
    } catch (reason) {
      if (ticket === generation.current && sameScope(requestScope, scopeRef.current)) setError(message(reason));
      return false;
    } finally {
      if (ticket === generation.current) setBusy(false);
    }
  }, [state]);

  return {
    status, state, roles, recall, queried, lent, saved, loading, busy, error,
    provisioning, provisionResult, refresh, recallNow, remember, lend, provision,
  };
}
