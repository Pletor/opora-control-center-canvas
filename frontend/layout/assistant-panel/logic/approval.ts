/**
 * Žádost asistenta o zápis na plátno (docs/asistent.md §5.1): z události `approval` vznikne karta
 * schválení, `approval_resolved` ji uzavře. Čisté funkce bez Reactu a sítě. Backend posílá rozparsovaný
 * cíl `{route, project, workspace, node, script, payloadSummary}`; tady se z něj skládá, co uživatel čte:
 * kam zápis jde, které pole se mění a proč. Automaticky zamítnuté žádosti (Edit, jiný Bash) nesou
 * jen krátký souhrn nástroje a nikdy se na nic neptají.
 */
import type { ChatItem, Conversation } from "./assistant-events";

type ApprovalItem = Extract<ChatItem, { kind: "approval" }>;

export type ApprovalStatus = "pending" | "sending" | "allowed" | "denied";

export type ApprovalTarget = {
  route: string;
  project: string;
  workspace: string;
  node: string | null;
  script: string;
  payloadSummary: string;
};

export type Approval = {
  id: string;
  tool: string;
  /** Cíl zápisu; null u automaticky zamítnuté žádosti, která zápisem na plátno není. */
  target: ApprovalTarget | null;
  /** Souhrn nástroje u automatického zamítnutí (příkaz, cesta). */
  summary: string;
  reason: string;
  auto: boolean;
  status: ApprovalStatus;
  note: string;
  timeout: boolean;
};

export const NOTE_LIMIT = 2000;

/**
 * Jména cest, o které může asistent požádat: přesně brána `WRITE_ROUTES` v
 * `backend/claude_code/assistant/approvals.py` (shodná s `opora_write.py`). Jiné zápisy
 * (architektura projektu, worktree PATCH/archive, štíhlé `/api/desktop-v3/node` a
 * `/api/graph/positions`) brána nepustí a backend je zamítne automaticky bez cíle, proto tu jméno nemají.
 */
export const ROUTE_LABEL: Record<string, string> = {
  "/api/graph": "Plátno: karty a vazby",
  "/api/canvas-plan": "Dávka plánu: nové karty, vazby a rozhodnutí",
  "/api/canvas-layout": "Rozmístění karet v oblasti",
  "/api/canvas-versions": "Uložená verze plátna",
  "/api/node-spec": "Zadání karty (goal, non-goals, acceptance)",
  "/api/node-text": "Text karty",
  "/api/desktop-v3/state": "Celý stav plátna (pravidla, rozhodnutí, karty)",
  "/api/desktop-v3/block": "Blok karty",
  "/api/desktop-v3/agent-workspace": "Prostor agenta na kartě",
  "/api/desktop-v3/agent-output": "Výstup agenta na kartě",
  "/api/desktop-v3/lease": "Převzetí karty (lease)",
  "/api/desktop-v3/assignment-snapshot": "Snímek zadání karty",
  "/api/desktop-v3/pipeline": "Pipeline karty (etapy)",
  "/api/desktop-v3/rule": "Pravidlo projektu",
  "/api/desktop-v3/decision": "Rozhodnutí projektu",
  "/api/desktop-v3/realize-source": "Zdroj karty po merge (commit, PR)",
  "/api/brief-vault": "Schránka zadání (podklady pro kartu)",
};

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/** Čitelné jméno cíle; neznámá cesta se ukáže sama, nic se nevymýšlí. */
export function routeLabel(route: string): string {
  return ROUTE_LABEL[route] ?? route;
}

function parseTarget(input: unknown): ApprovalTarget | null {
  if (!input || typeof input !== "object") return null;
  const data = input as Record<string, unknown>;
  const route = str(data.route);
  if (!route.startsWith("/api/")) return null;
  return {
    route,
    project: str(data.project),
    workspace: str(data.workspace),
    node: str(data.node) || null,
    script: str(data.script),
    payloadSummary: str(data.payloadSummary),
  };
}

/** Událost `approval` → žádost; bez `approvalId` null. */
export function parseApproval(event: Record<string, unknown>): Approval | null {
  const id = str(event.approvalId);
  if (!id) return null;
  const auto = event.auto === true;
  const input = event.input && typeof event.input === "object" ? (event.input as Record<string, unknown>) : {};
  return {
    id,
    tool: str(event.tool) || "nástroj",
    target: auto ? null : parseTarget(input),
    summary: str(input.summary),
    reason: str(event.reason),
    auto,
    status: "pending",
    note: "",
    timeout: false,
  };
}

/** Událost `approval_resolved` uzavře žádost: povoleno, nebo zamítnuto (s poznámkou či po čase). */
export function resolveApproval(approval: Approval, event: Record<string, unknown>): Approval {
  const decision = event.decision === "allow" ? "allowed" : "denied";
  return { ...approval, status: decision, note: str(event.note) || approval.note, timeout: event.timeout === true };
}

/** Rozhodnutí odchází na server: tlačítka se uzamknou, dokud nepřijde odpověď. */
export function markSending(approval: Approval): Approval {
  return approval.status === "pending" ? { ...approval, status: "sending" } : approval;
}

/** Odeslání selhalo: žádost čeká dál, aby šla rozhodnout znovu. */
export function markPending(approval: Approval): Approval {
  return approval.status === "sending" ? { ...approval, status: "pending" } : approval;
}

export function isOpen(approval: Approval): boolean {
  return approval.status === "pending" || approval.status === "sending";
}

/** Řádky shrnutí payloadu („fields: objekt {goal, acceptance}“); backend je dělí „ · “. */
export function summaryLines(summary: string): string[] {
  return summary.split(" · ").map((part) => part.trim()).filter(Boolean);
}

/** Kam zápis jde jedním řádkem: „Zadání karty … · karta n1“. */
export function targetTitle(target: ApprovalTarget): string {
  return target.node ? `${routeLabel(target.route)} · karta ${target.node}` : routeLabel(target.route);
}

/** Projekt, workspace a přesná cesta pro kontrolu: „projekt p · workspace w · POST /api/node-spec“. */
export function targetScope(target: ApprovalTarget): string {
  return [target.project && `projekt ${target.project}`, target.workspace && `workspace ${target.workspace}`, `POST ${target.route}`]
    .filter(Boolean)
    .join(" · ");
}

/** Výsledek žádosti slovy pro uzavřenou kartu. */
export function statusWord(approval: Approval): string {
  if (approval.status === "allowed") return "Povoleno";
  if (approval.status === "sending") return "Odesílám rozhodnutí…";
  if (approval.status === "pending") return "Čeká na vaše rozhodnutí";
  if (approval.auto && approval.timeout) return "Zamítnuto: bez odpovědi do 10 min";
  if (approval.auto && !approval.target) return "Zamítnuto automaticky";
  return "Zamítnuto";
}

/** Poznámka k rozhodnutí: oříznutá, nejvýš 2000 znaků; prázdná se neposílá. */
export function cleanNote(text: string): string | undefined {
  const value = text.trim();
  return value ? value.slice(0, NOTE_LIMIT) : undefined;
}

/** `approval` do položek konverzace; žádost se stejným id se nepřidá podruhé. */
export function addApprovalItem(items: ChatItem[], event: Record<string, unknown>, replayed: boolean): ChatItem[] {
  const approval = parseApproval(event);
  if (!approval || items.some((it) => it.kind === "approval" && it.id === approval.id)) return items;
  const item: ApprovalItem = { kind: "approval", id: approval.id, approval };
  return [...items, replayed ? { ...item, replayed } : item];
}

/**
 * `approval_resolved` uzavře kartu. Při přehrání bufferu (`replayed`) obnovená žádost, o které už bylo
 * rozhodnuto dřív, z konverzace zmizí: historie z přepisu ji nemá a zůstat má jen ta, která čeká.
 */
export function resolveApprovalItem(items: ChatItem[], event: Record<string, unknown>, replayed = false): ChatItem[] {
  const id = str(event.approvalId);
  const index = items.findIndex((it) => it.kind === "approval" && it.id === id);
  if (index < 0) return items;
  const item = items[index] as ApprovalItem;
  if (replayed && item.replayed) return items.filter((_, i) => i !== index);
  const next = items.slice();
  next[index] = { ...item, approval: resolveApproval(item.approval, event) };
  return next;
}

/** Lokální změna žádosti (odesílání rozhodnutí, návrat po chybě); jiné položky zůstanou. */
export function updateApproval(conv: Conversation, id: string, change: (a: Approval) => Approval): Conversation {
  return {
    ...conv,
    items: conv.items.map((it) => (it.kind === "approval" && it.id === id ? { ...it, approval: change(it.approval) } : it)),
  };
}

/** Žádosti, které ještě čekají na rozhodnutí člověka. */
export function pendingApprovals(items: ChatItem[]): Approval[] {
  return items.flatMap((it) => (it.kind === "approval" && isOpen(it.approval) ? [it.approval] : []));
}
