/**
 * Přehled úkolů asistenta (každá session je jeden úkol): stav slovem, relativní čas, náhled poslední
 * odpovědi a značka „nové“. Čisté funkce bez Reactu a sítě. U aktivní session se stav a náhled berou
 * z živé konverzace, u ostatních z polledovaného seznamu (`state`, `updatedAt`) a z náhledu, který
 * panel zapamatoval, když byla session naposledy otevřená.
 */
import type { ChatItem, SessionState } from "./assistant-events";

export type TaskStatus = "working" | "waiting" | "ready" | "error";

export const STATUS_WORD: Record<TaskStatus, string> = {
  working: "pracuje",
  waiting: "čeká na vás",
  ready: "připraveno",
  error: "chyba",
};

export type TaskSource = { id: string; title: string; model: string; updatedAt: string; state: SessionState };

export type TaskView = {
  id: string;
  title: string;
  status: TaskStatus;
  statusWord: string;
  model: string;
  when: string;
  preview: string;
  isNew: boolean;
  active: boolean;
};

/** `updatedAt`, kdy uživatel úkol naposledy viděl, podle id. */
export type SeenMap = Record<string, string>;

export function taskStatus(state: SessionState): TaskStatus {
  if (state === "running") return "working";
  if (state === "waiting_approval") return "waiting";
  if (state === "error") return "error";
  return "ready";
}

export function taskTitle(title: string, index: number): string {
  return title.trim() || `Úkol ${index + 1}`;
}

/** Relativní čas česky: „právě teď“, „před 5 min“, „před 2 h“, „včera“, „před 3 dny“, pak datum. */
export function relativeTime(iso: string, now: number): string {
  const at = Date.parse(iso);
  if (!Number.isFinite(at)) return "";
  const minutes = Math.floor(Math.max(0, now - at) / 60000);
  if (minutes < 1) return "právě teď";
  if (minutes < 60) return `před ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `před ${hours} h`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "včera";
  if (days < 7) return `před ${days} ${days < 5 ? "dny" : "dní"}`;
  const date = new Date(at);
  return `${date.getDate()}. ${date.getMonth() + 1}. ${date.getFullYear()}`;
}

/** První neprázdný řádek textu bez značek Markdownu, zkrácený pro náhled v přehledu. */
export function firstLine(text: string, max = 140): string {
  const line = text
    .split("\n")
    .map((row) => row.replace(/^\s*(#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|>\s?|```.*)/, "").replace(/[*_`]/g, "").trim())
    .find((row) => row.length > 0) ?? "";
  return line.length > max ? line.slice(0, max - 1).trimEnd() + "…" : line;
}

/** Náhled z konverzace: první řádek poslední odpovědi asistenta, jinak prázdný. */
export function previewOf(items: ChatItem[]): string {
  for (let i = items.length - 1; i >= 0; i--) {
    const item = items[i];
    if (item.kind === "message" && item.role === "assistant" && item.text.trim()) return firstLine(item.text);
  }
  return "";
}

/**
 * Posune „viděno“: nově objevená session se bere jako viděná v aktuálním stavu (jinak by po
 * otevření panelu svítilo „nové“ u všeho) a aktivní session je viděná vždy.
 */
export function nextSeen(seen: SeenMap, sessions: TaskSource[], activeId: string | null): SeenMap {
  let changed = false;
  const next: SeenMap = { ...seen };
  for (const s of sessions) {
    if (next[s.id] === undefined || (s.id === activeId && next[s.id] !== s.updatedAt)) {
      next[s.id] = s.updatedAt;
      changed = true;
    }
  }
  return changed ? next : seen;
}

/** Úkol doběhl, zatímco se uživatel díval jinam: změnil se po posledním vidění a už nepracuje. */
export function isNewTask(session: TaskSource, seen: SeenMap, activeId: string | null): boolean {
  if (session.id === activeId) return false;
  if (session.state === "running" || session.state === "waiting_approval") return false;
  const at = seen[session.id];
  return at !== undefined && Date.parse(session.updatedAt) > Date.parse(at);
}

export function buildTasks(
  sessions: TaskSource[],
  view: { activeId: string | null; activeState: SessionState; activeItems: ChatItem[]; seen: SeenMap; previews: Record<string, string>; now: number },
): TaskView[] {
  return sessions.map((s, index) => {
    const active = s.id === view.activeId;
    const status = taskStatus(active ? view.activeState : s.state);
    const preview = active ? previewOf(view.activeItems) || view.previews[s.id] || "" : view.previews[s.id] || "";
    return {
      id: s.id,
      title: taskTitle(s.title, index),
      status,
      statusWord: STATUS_WORD[status],
      model: s.model,
      when: relativeTime(s.updatedAt, view.now),
      preview,
      isNew: isNewTask(s, view.seen, view.activeId),
      active,
    };
  });
}

/** Sousední úkol pro Alt+↑ / Alt+↓; na krajích seznamu zůstane, kde je. */
export function neighbourTask(ids: string[], activeId: string | null, step: -1 | 1): string | null {
  if (!ids.length) return null;
  const index = activeId ? ids.indexOf(activeId) : -1;
  if (index < 0) return ids[0];
  return ids[Math.min(ids.length - 1, Math.max(0, index + step))];
}

/** Platný název úkolu pro `POST …/title`: 1–80 znaků bez řídicích znaků, jinak null. */
export function cleanTitle(input: string): string | null {
  // eslint-disable-next-line no-control-regex
  const value = input.replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim();
  return value.length >= 1 && value.length <= 80 ? value : null;
}

export function anyWorking(tasks: { status: TaskStatus }[]): boolean {
  return tasks.some((t) => t.status === "working" || t.status === "waiting");
}

/** Čas běžícího tahu: „0:12“, „3:05“, „1:02:09“. */
export function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/** „1 úkol“, „3 úkoly“, „5 úkolů“, „0 úkolů“. */
export function tasksCount(count: number): string {
  if (count === 1) return "1 úkol";
  return `${count} ${count >= 2 && count <= 4 ? "úkoly" : "úkolů"}`;
}
