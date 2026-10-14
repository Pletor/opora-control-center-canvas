import type { LiveSession, WorkStatus, WorktreeState } from "./live-model";

// Slova, ikony a souhrny stavů relací a worktree. Stav se vždy čte slovem a ikonou, barva jen doplňuje.

export const WORKTREE_STATE: Record<WorktreeState, { label: string; icon: string }> = {
  running: { label: "běží", icon: "▶" },
  waiting: { label: "čeká", icon: "⏸" },
  stopped: { label: "stojí", icon: "■" },
  none: { label: "bez relace", icon: "○" },
};

const SOURCE_LABEL: Record<LiveSession["source"], string> = { assistant: "Asistent", hook: "Hook", lease: "Karta" };

// Surová slova zdrojů. Jsou jen podrobností v `title`: o tom, jestli se pracuje, rozhoduje stav, který
// spočítal backend z prahů §7 (hook `active` po 120 s ticha nebo lease bez aktivity už neběží).
const RAW_STATE: Record<string, string> = {
  "assistant:running": "běží", "assistant:waiting_approval": "čeká na schválení", "assistant:idle": "čeká na zprávu",
  "assistant:error": "chyba", "assistant:closed": "zavřená",
  "hook:active": "aktivní", "hook:paused": "pozastaveno", "lease:active": "převzatá", "lease:expired": "převzetí vypršelo",
};

/** Stav relace asistenta podle §7; jen u asistenta je surový stav sám o sobě platný (nezávisí na čase). */
export function assistantTone(state: string | null): WorktreeState {
  if (state === "running") return "running";
  if (state === "waiting_approval" || state === "idle") return "waiting";
  if (state === "error") return "stopped";
  return "none";
}

export type SessionView = { source: string; label: string; tone: WorktreeState; icon: string; title: string; openable: boolean };

/** „Hook hlásí „aktivní“ · naposledy před 4 min“: surový stav zdroje s časem posledního signálu. */
export function sourceDetail(session: LiveSession, now = Date.now()): string {
  const raw = RAW_STATE[`${session.source}:${session.state}`] ?? (session.state || "neznámý stav");
  const seen = session.lastSeenAt ? ` · naposledy ${relativeAge(session.lastSeenAt, now)}` : "";
  return `${SOURCE_LABEL[session.source]} hlásí „${raw}“${seen}`;
}

/**
 * Relace ve worktree jako čip: hlavní slovo je stav worktree spočítaný backendem (`effective`),
 * surový stav zdroje a čas posledního signálu jsou jen v `title`. Otevřít jde jen relace asistenta.
 */
export function sessionView(session: LiveSession, effective: WorktreeState, now = Date.now()): SessionView {
  const state = WORKTREE_STATE[effective];
  return {
    source: SOURCE_LABEL[session.source], label: state.label, tone: effective, icon: state.icon, openable: session.source === "assistant" && !!session.id,
    title: `${sourceDetail(session, now)} · stav worktree: ${state.label}`,
  };
}

/** „před 3 min“, „před 2 h“; neplatný čas → „neznámo kdy“. */
export function relativeAge(iso: string, now = Date.now()): string {
  const moment = Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z");
  if (Number.isNaN(moment)) return "neznámo kdy";
  const seconds = Math.max(0, Math.round((now - moment) / 1000));
  if (seconds < 60) return "před chvílí";
  if (seconds < 3600) return `před ${Math.round(seconds / 60)} min`;
  if (seconds < 86_400) return `před ${Math.round(seconds / 3600)} h`;
  return `před ${Math.round(seconds / 86_400)} d`;
}

/**
 * Souhrn hlavních relací pro hlavičku přehledu: „Hlavní relace: 1 běží · 1 čeká“; zavřené se nepočítají.
 * `null` = stav práce se ještě nenačetl, to je jiná zpráva než „žádná“.
 */
export function mainSessionsSummary(sessions: LiveSession[] | null): string {
  if (sessions === null) return "Hlavní relace: nenačteno";
  const counts: Record<WorktreeState, number> = { running: 0, waiting: 0, stopped: 0, none: 0 };
  for (const item of sessions) counts[assistantTone(item.state)] += 1;
  const parts = (["running", "waiting", "stopped"] as const).filter((tone) => counts[tone]).map((tone) => `${counts[tone]} ${WORKTREE_STATE[tone].label}`);
  return `Hlavní relace: ${parts.length ? parts.join(" · ") : "žádná"}`;
}

/** Věta pro `aria-live`: jen worktree, které změnily stav proti minulému čtení; první čtení nehlásí nic. */
export function stateChanges(prev: WorkStatus | null, next: WorkStatus, domainId?: string): string {
  if (!prev) return "";
  const pick = (status: WorkStatus) => (domainId ? status.domains.filter((d) => d.id === domainId) : status.domains).flatMap((d) => d.worktrees);
  const before = new Map(pick(prev).map((item) => [item.id, item.state]));
  return pick(next)
    .filter((item) => before.has(item.id) && before.get(item.id) !== item.state)
    .map((item) => `Worktree ${item.branch || item.id}: ${WORKTREE_STATE[item.state].label}.`)
    .join(" ");
}

/** Žádost o novou relaci asistenta; jde callbackem nahoru do App, které otevře panel Asistent. Zprávu neposílá. */
export type SessionRequest = { workspace: string; nodeId: string | null; title: string };

/** Žádost o otevření karty z živého panelu: App přepne prostor, je-li jiný, a kartu vybere. */
export type CardRequest = { workspace: string; nodeId: string };

/** Název nové relace podle toho, odkud vznikla (strop 120 znaků jako u názvu session). */
export function sessionTitle(kind: "main" | "worktree" | "card", name = ""): string {
  const title = kind === "main" ? "Hlavní relace" : kind === "worktree" ? `Worktree ${name}` : `Karta ${name}`;
  return title.trim().slice(0, 120);
}
