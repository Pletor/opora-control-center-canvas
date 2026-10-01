// Čistá pravidla paměti role u jedné karty. Modul nic nenačítá ani neukládá: jen mapuje odpovědi
// `/api/memory/*` (docs/pamet-agentu.md) na pohled a skládá těla požadavků s přesnými klíči, které
// server vyžaduje — pole navíc i překlep končí 409, takže se payloady nikdy nestaví „skoro“.
// Dvě pravidla, která tenhle modul drží: prázdná odpověď se nikdy nevydává za „role si nic
// nepamatuje“ (stav a důvod jdou dál beze změny) a zápis do paměti nevzniká sám — `rememberPayload`
// nese `confirmed: true` jen proto, že ho člověk vědomě odeslal.

/** Stav paměti, jak ho vidí panel. `unknown` = stav se ještě nenačetl, ne „vypnuto“.
 * `needs_provisioning` = server běží, ale některé role nemají u OpenVikingu klíč. */
export type MemoryState = "unknown" | "disabled" | "unavailable" | "needs_provisioning" | "skipped" | "configured";
const STATES: MemoryState[] = ["disabled", "unavailable", "needs_provisioning", "skipped", "configured"];

export type MemoryStatus = { status: string; reason?: string; url?: string; missingRoles?: unknown };
export type MemoryRole = { id: string; label: string; description: string };
/** Položka paměti: adresa ve VikingU, text, skóre vyhledání a původ (`self`/`project`/`lent:<role>`). */
export type MemoryItem = { uri: string; text: string; score: number; origin: string };
export type MemoryRecall = { status: string; role?: string | null; items?: unknown; reason?: string; truncated?: boolean };
export type MemoryKind = "note" | "lesson" | "decision";
export type MemoryScope = { project: string; workspace: string; nodeId: string };

export const MEMORY_KINDS: MemoryKind[] = ["note", "lesson", "decision"];
export const MEMORY_KIND_LABELS: Record<MemoryKind, string> = {
  note: "Poznámka", lesson: "Poučení", decision: "Rozhodnutí",
};
/** Stropy serveru (`backend/memory/memory_service.py`); formulář je hlídá dřív, než odešle. */
export const MAX_MEMORY_TEXT = 12000;
export const MAX_MEMORY_QUERY = 2000;
export const MEMORY_MAX_TOKENS = 600;
export const NO_ROLE_LABEL = "Karta nemá roli";
/** Banner nad tlačítkem „Založit klíče rolí“; věta je pevná, mění se jen seznam rolí pod ní. */
export const NEEDS_PROVISIONING_BANNER = "Role zatím nemají klíče v OpenViking. Založ je jedním klikem.";

const text = (value: unknown): string => (typeof value === "string" ? value : "");
const record = (value: unknown): Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
const usable = (value: string): boolean => value.trim().length > 0 && !value.includes("\0");

/** Název role z knihovny; neznámé id se ukáže tak, jak přišlo, nic se nedomýšlí. */
export function roleLabel(roleId: string, roles: MemoryRole[] = []): string {
  const found = roles.find((role) => role?.id === roleId);
  return found && text(found.label) ? found.label : roleId;
}

/** Role bez klíče z `/status`; neplatný tvar se čte jako „žádná“, ne jako chyba. */
export function missingRoleIds(status: MemoryStatus | null): string[] {
  const value = status?.missingRoles;
  if (!Array.isArray(value)) return [];
  return value.filter((entry): entry is string => typeof entry === "string" && entry.length > 0);
}

/** Role bez klíče jako jména pro banner; neznámé id se ukáže tak, jak přišlo. */
export function missingRoleLabels(status: MemoryStatus | null, roles: MemoryRole[] = []): string[] {
  return missingRoleIds(status).map((id) => roleLabel(id, roles));
}

/** Skóre vyhledání na dvě desetiny s pojmenováním, aby se nečetlo jako procento jistoty. */
export function formatScore(score: unknown): string {
  const value = typeof score === "number" && Number.isFinite(score) ? score : 0;
  return `podobnost ${value.toFixed(2)}`;
}

/** Položky z odpovědi serveru; co nemá adresu, není položka paměti a tiše se zahodí. */
export function memoryItems(value: unknown): MemoryItem[] {
  if (!Array.isArray(value)) return [];
  const items: MemoryItem[] = [];
  for (const entry of value) {
    const item = record(entry);
    if (!text(item.uri)) continue;
    const score = typeof item.score === "number" && Number.isFinite(item.score) ? item.score : 0;
    items.push({ uri: text(item.uri), text: text(item.text), score, origin: text(item.origin) });
  }
  return items;
}

export type MemoryGroup = { id: string; label: string; origin: string; items: MemoryItem[] };

/**
 * Skupiny v pořadí, ve kterém se paměť čte: nejdřív co umí role sama, pak co ví o tomto projektu
 * a nakonec výslovné půjčky od jiných rolí. Půjčka se nikdy nesmí tvářit jako vlastní zkušenost.
 */
export function groupByOrigin(items: MemoryItem[], roles: MemoryRole[] = []): MemoryGroup[] {
  const buckets = new Map<string, MemoryGroup>();
  for (const item of items) {
    const origin = item.origin || "unknown";
    if (!buckets.has(origin)) buckets.set(origin, { id: origin, label: groupLabel(origin, roles), origin, items: [] });
    (buckets.get(origin) as MemoryGroup).items.push(item);
  }
  const rank = (origin: string): number =>
    origin === "self" ? 0 : origin === "project" ? 1 : origin.startsWith("lent:") ? 2 : 3;
  return [...buckets.values()].sort((left, right) =>
    rank(left.origin) - rank(right.origin) || left.origin.localeCompare(right.origin));
}

function groupLabel(origin: string, roles: MemoryRole[]): string {
  if (origin === "self") return "Vlastní zkušenost";
  if (origin === "project") return "Tento projekt";
  if (origin.startsWith("lent:")) return `Zapůjčeno od ${roleLabel(origin.slice(5), roles)}`;
  return "Neuvedený původ";
}

export type MemoryView = {
  state: MemoryState;
  /** Věta serveru, proč to takhle je; nikdy se nenahrazuje vlastním výkladem. */
  reason: string;
  role: string | null;
  groups: MemoryGroup[];
  truncated: boolean;
  empty: boolean;
};

const stateOf = (value: unknown): MemoryState => {
  const found = STATES.find((state) => state === value);
  return found ?? "unknown";
};

/**
 * Pohled panelu ze dvou odpovědí: přepínač aplikace (`/status`) říká, jestli paměť vůbec běží,
 * a vybavení (`/recall`) upřesňuje, co z toho platí pro tuhle kartu — třeba `skipped`, když
 * karta nemá roli. Dokud vybavení není, mluví jen stav.
 */
export function memoryModel(status: MemoryStatus | null, recall: MemoryRecall | null, roles: MemoryRole[] = []): MemoryView {
  const base = status ? stateOf(status.status) : "unknown";
  const recalled = recall ? stateOf(recall.status) : null;
  const state = base === "configured" && recalled ? recalled : base;
  const fromRecall = state === recalled && recall !== null;
  const reason = fromRecall ? text(recall?.reason) : text(status?.reason);
  const groups = groupByOrigin(memoryItems(recall?.items), roles);
  return {
    state,
    reason: reason || (fromRecall ? text(status?.reason) : ""),
    role: recall && typeof recall.role === "string" && recall.role ? recall.role : null,
    groups,
    truncated: recall?.truncated === true,
    empty: groups.length === 0,
  };
}

export type RoleOption = { value: string; label: string; description: string };

/** Volby pro výběr role karty; prázdná hodnota je platná volba „karta roli nemá“, ne chyba. */
export function roleOptions(roles: unknown): RoleOption[] {
  const options: RoleOption[] = [
    { value: "", label: NO_ROLE_LABEL, description: "Bez role se paměť nečte ani nezapisuje." },
  ];
  if (!Array.isArray(roles)) return options;
  for (const entry of roles) {
    const role = record(entry);
    const id = text(role.id);
    if (!id) continue;
    options.push({ value: id, label: text(role.label) || id, description: text(role.description) });
  }
  return options;
}

export type RememberDraft = { role: string | null; kind: MemoryKind; text: string };
export type LendDraft = { fromRole: string; toRole: string; query: string };

const queryOk = (query: string): boolean => usable(query) && query.length <= MAX_MEMORY_QUERY;

/** Vybavit se smí jen z běžící paměti a jen s rolí karty: bez role by server vrátil `skipped`. */
export function canRecall(role: string | null, query: string, state: MemoryState): boolean {
  return state === "configured" && !!role && queryOk(query);
}

/** Zapsat smí jen člověk u odemčené karty s rolí; prázdný ani přerostlý text se neodesílá. */
export function canRemember(draft: RememberDraft, readOnly: boolean, state: MemoryState): boolean {
  if (readOnly || state !== "configured" || !draft.role) return false;
  if (!MEMORY_KINDS.includes(draft.kind)) return false;
  return usable(draft.text) && draft.text.length <= MAX_MEMORY_TEXT;
}

/** Půjčit se dá jen od jiné role než vlastní — jinak by to bylo obyčejné vybavení. */
export function canLend(draft: LendDraft, state: MemoryState): boolean {
  return state === "configured" && !!draft.fromRole && !!draft.toRole
    && draft.fromRole !== draft.toRole && queryOk(draft.query);
}

export type RecallPayload = MemoryScope & { role: string | null; query: string; maxTokens: number };
export type RememberPayload = MemoryScope & { role: string | null; kind: MemoryKind; text: string; confirmed: true };
export type LendPayload = { fromRole: string; toRole: string; query: string; maxTokens: number };

export function recallPayload(scope: MemoryScope, role: string | null, query: string, maxTokens = MEMORY_MAX_TOKENS): RecallPayload {
  return { role: role || null, project: scope.project, workspace: scope.workspace, nodeId: scope.nodeId, query: query.trim(), maxTokens };
}

export function rememberPayload(scope: MemoryScope, draft: RememberDraft): RememberPayload {
  return {
    role: draft.role || null, project: scope.project, workspace: scope.workspace, nodeId: scope.nodeId,
    kind: draft.kind, text: draft.text, confirmed: true,
  };
}

export function lendPayload(draft: LendDraft, maxTokens = MEMORY_MAX_TOKENS): LendPayload {
  return { fromRole: draft.fromRole, toRole: draft.toRole, query: draft.query.trim(), maxTokens };
}

export type ProvisionRoleError = { role: string; reason: string };
/** Odpověď `POST /api/memory/provision`; klíče samotné v ní nikdy nejsou. */
export type ProvisionResult = {
  status: string;
  account?: string;
  provisioned?: string[];
  reused?: string[];
  errors?: ProvisionRoleError[];
};

/** Tělo rozdání klíčů rolím; server ho vyžaduje jako výslovné potvrzení člověka. */
export function provisionPayload(): { confirmed: true } {
  return { confirmed: true };
}

/** Věta pro člověka po kliknutí na „Založit klíče rolí“; ticho bez čísel, která nic neřeknou. */
export function provisionSummary(result: ProvisionResult | null, roles: MemoryRole[] = []): string {
  if (!result) return "";
  const provisioned = Array.isArray(result.provisioned) ? result.provisioned : [];
  const reused = Array.isArray(result.reused) ? result.reused : [];
  const errors = Array.isArray(result.errors) ? result.errors : [];
  const names = (ids: string[]) => ids.map((id) => roleLabel(id, roles)).join(", ");
  const parts: string[] = [];
  if (provisioned.length) parts.push(`Založeno: ${names(provisioned)}.`);
  if (reused.length) parts.push(`Beze změny, klíč už měly: ${names(reused)}.`);
  if (errors.length) {
    parts.push(`Nepodařilo se: ${errors.map((entry) => `${roleLabel(entry.role, roles)} (${entry.reason})`).join(", ")}.`);
  }
  return parts.length ? parts.join(" ") : "Rozdání klíčů rolím neudělalo žádnou změnu.";
}

/** Paměť, kterou už nese balíček karty (`context.roleMemory`); nic se kvůli ní znovu nevolá. */
export function briefRoleMemory(brief: unknown): MemoryRecall | null {
  const value = record(record(record(brief).context).roleMemory);
  if (!text(value.status)) return null;
  return {
    status: text(value.status),
    role: typeof value.role === "string" ? value.role : null,
    items: value.items,
    reason: text(value.reason),
  };
}

/** Dotaz do paměti: co člověk napsal, jinak cíl karty a teprve nakonec její identita. */
export function memoryQuery(brief: unknown, nodeId: string, typed: string): string {
  if (typed.trim()) return typed.trim();
  const card = record(brief);
  const goal = text(record(record(card.orientation).goal).goal) || text(record(card.goal).goal);
  return (goal.trim() || `karta ${nodeId}`).slice(0, MAX_MEMORY_QUERY);
}
