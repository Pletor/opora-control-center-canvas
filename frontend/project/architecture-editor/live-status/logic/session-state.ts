import type { LiveSession, WorkStatus, WorktreeState } from "./live-model";
import { worktreeName } from "./worktree-label";

// Slova, ikony a souhrny stavů relací a worktree. Stav se vždy čte slovem a ikonou, barva jen doplňuje.

export const WORKTREE_STATE: Record<WorktreeState, { label: string; icon: string }> = {
  running: { label: "běží", icon: "▶" },
  waiting: { label: "čeká", icon: "⏸" },
  stopped: { label: "stojí", icon: "■" },
  none: { label: "bez relace", icon: "○" },
};

const SOURCE_LABEL: Record<LiveSession["source"], string> = { lease: "Karta" };

// Surová slova zdrojů. Jsou jen podrobností v `title`: o tom, jestli se pracuje, rozhoduje stav, který
// spočítal backend z prahů §7 (lease bez aktivity už neběží).
const RAW_STATE: Record<string, string> = { "lease:active": "převzatá", "lease:expired": "převzetí vypršelo" };

export type SessionView = { source: string; label: string; tone: WorktreeState; icon: string; title: string };

/** „Karta hlásí „převzatá“ · naposledy před 4 min“: surový stav zdroje s časem posledního signálu. */
export function sourceDetail(session: LiveSession, now = Date.now()): string {
  const raw = RAW_STATE[`${session.source}:${session.state}`] ?? (session.state || "neznámý stav");
  const seen = session.lastSeenAt ? ` · naposledy ${relativeAge(session.lastSeenAt, now)}` : "";
  return `${SOURCE_LABEL[session.source]} hlásí „${raw}“${seen}`;
}

/**
 * Relace ve worktree jako čip: hlavní slovo je stav worktree spočítaný backendem (`effective`),
 * surový stav zdroje a čas posledního signálu jsou jen v `title`.
 */
export function sessionView(session: LiveSession, effective: WorktreeState, now = Date.now()): SessionView {
  const state = WORKTREE_STATE[effective];
  return {
    source: SOURCE_LABEL[session.source], label: state.label, tone: effective, icon: state.icon,
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

/** Věta pro `aria-live`: jen worktree, které změnily stav proti minulému čtení; první čtení nehlásí nic. */
export function stateChanges(prev: WorkStatus | null, next: WorkStatus, domainId?: string): string {
  if (!prev) return "";
  const pick = (status: WorkStatus) => (domainId ? status.domains.filter((d) => d.id === domainId) : status.domains).flatMap((d) => d.worktrees);
  const before = new Map(pick(prev).map((item) => [item.id, item.state]));
  return pick(next)
    .filter((item) => before.has(item.id) && before.get(item.id) !== item.state)
    .map((item) => `Worktree ${worktreeName(item)}: ${WORKTREE_STATE[item.state].label}.`)
    .join(" ");
}


/** Žádost o otevření karty z živého panelu: App přepne prostor, je-li jiný, a kartu vybere. */
export type CardRequest = { workspace: string; nodeId: string };

/**
 * Text pro srdce z detailu worktree (docs/brain-heart-channel.md §5): o celém worktree, nebo o kartě v něm.
 * Jde callbackem nahoru do App, které ho srdci pošle a otevře panel asistenta.
 */
export function heartText(kind: "worktree" | "card", worktree: string, card?: { nodeId: string; name: string }): string {
  if (kind === "card" && card) return `Ve worktree «${worktree}» posaď pracovníka ke kartě «${card.name}» (\`${card.nodeId}\`): zadej úkol podle jejího \`node-brief\`.`;
  return `Worktree «${worktree}»: zjisti stav práce na jeho kartách a navrhni další krok.`;
}
