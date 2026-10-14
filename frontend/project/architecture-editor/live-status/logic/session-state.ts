import type { LiveSession, WorkStatus, WorktreeState } from "./live-model";

// Slova, ikony a souhrny stavů relací a worktree. Stav se vždy čte slovem a ikonou, barva jen doplňuje.

export const WORKTREE_STATE: Record<WorktreeState, { label: string; icon: string }> = {
  running: { label: "běží", icon: "▶" },
  waiting: { label: "čeká", icon: "⏸" },
  stopped: { label: "stojí", icon: "■" },
  none: { label: "bez relace", icon: "○" },
};

const SOURCE_LABEL: Record<LiveSession["source"], string> = { assistant: "Asistent", hook: "Hook", lease: "Karta" };

const SESSION_STATE: Record<string, { label: string; tone: WorktreeState }> = {
  "assistant:running": { label: "běží", tone: "running" },
  "assistant:waiting_approval": { label: "čeká na schválení", tone: "waiting" },
  "assistant:idle": { label: "čeká na zprávu", tone: "waiting" },
  "assistant:error": { label: "chyba", tone: "stopped" },
  "hook:active": { label: "aktivní", tone: "running" },
  "hook:paused": { label: "pozastaveno", tone: "waiting" },
  "lease:active": { label: "převzatá", tone: "waiting" },
  "lease:expired": { label: "převzetí vypršelo", tone: "stopped" },
};

export type SessionView = { source: string; label: string; tone: WorktreeState; icon: string; title: string };

/** Jedna relace jako čip: zdroj, stav slovem, tón pro barvu a `title` s časem posledního signálu. */
export function sessionView(session: LiveSession, now = Date.now()): SessionView {
  const known = SESSION_STATE[`${session.source}:${session.state}`];
  const tone = known?.tone ?? "none";
  const label = known?.label ?? (session.state || "neznámý stav");
  const seen = session.lastSeenAt ? ` · poslední signál ${relativeAge(session.lastSeenAt, now)}` : "";
  return { source: SOURCE_LABEL[session.source], label, tone, icon: WORKTREE_STATE[tone].icon, title: `${SOURCE_LABEL[session.source]}: ${label}${seen}` };
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

/** Souhrn hlavních relací pro hlavičku přehledu: „Hlavní relace: 1 běží · 1 čeká“; zavřené se nepočítají. */
export function mainSessionsSummary(sessions: LiveSession[]): string {
  const counts: Record<WorktreeState, number> = { running: 0, waiting: 0, stopped: 0, none: 0 };
  for (const item of sessions) counts[sessionView(item).tone] += 1;
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

/** Název nové relace podle toho, odkud vznikla (strop 120 znaků jako u názvu session). */
export function sessionTitle(kind: "main" | "worktree" | "card", name = ""): string {
  const title = kind === "main" ? "Hlavní relace" : kind === "worktree" ? `Worktree ${name}` : `Karta ${name}`;
  return title.trim().slice(0, 120);
}
