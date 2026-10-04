/**
 * Pozná z proudu událostí, že povolený zápis asistenta na plátno doběhl (docs/asistent.md §6.2):
 * `approval` (Bash, s `approvalId`, ne automatická) → `approval_resolved` s `allow` → `tool_result`
 * s `ok: true`. Výsledek se páruje s nástrojem podle id: žádost se váže k poslednímu běžícímu
 * `tool_use` téhož nástroje; když takový není, platí první `tool_result` po povolení v témže tahu.
 * Zamítnutí, automatické zamítnutí, neúspěch i konec tahu nic nespustí. Čistá funkce bez Reactu.
 *
 * Přehrání bufferu: hlídač začíná s `since` = poslední seq známý při otevření úkolu. Události pod ním
 * se zpracují (aby čekající žádost zůstala spárovaná), ale zápis ohlásí jen výsledek se seq nad `since`.
 * Už viděné seq se zahodí, takže jeden zápis se ohlásí nejvýš jednou.
 */
import type { AssistantEvent } from "./assistant-events";

export type WriteWatch = {
  since: number;
  lastSeq: number;
  /** Běžící nástroje v pořadí `tool_use`: id → jméno. */
  running: [string, string][];
  /** Čekající žádosti: approvalId → id nástroje (null = nepárováno). */
  requested: Record<string, string | null>;
  /** Povolené zápisy čekající na výsledek. */
  armed: (string | null)[];
};

export function startWatch(since = 0): WriteWatch {
  return { since, lastSeq: 0, running: [], requested: {}, armed: [] };
}

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/** Jedna událost do hlídače; `written` je true právě u výsledku povoleného zápisu. */
export function watchEvent(watch: WriteWatch, event: AssistantEvent): { watch: WriteWatch; written: boolean } {
  const seq = typeof event.seq === "number" ? event.seq : null;
  if (seq !== null && seq <= watch.lastSeq) return { watch, written: false };
  const w = seq !== null ? { ...watch, lastSeq: seq } : watch;
  switch (event.type) {
    case "tool_use": {
      const id = str(event.id);
      return { watch: id ? { ...w, running: [...w.running, [id, str(event.name)]] } : w, written: false };
    }
    case "approval": {
      const approvalId = str(event.approvalId);
      const tool = str(event.tool);
      if (!approvalId || event.auto === true || tool !== "Bash") return { watch: w, written: false };
      const match = [...w.running].reverse().find(([, name]) => name === tool);
      return { watch: { ...w, requested: { ...w.requested, [approvalId]: match ? match[0] : null } }, written: false };
    }
    case "approval_resolved": {
      const approvalId = str(event.approvalId);
      if (!(approvalId in w.requested)) return { watch: w, written: false };
      const { [approvalId]: toolId, ...rest } = w.requested;
      const allowed = event.decision === "allow" && event.auto !== true;
      return { watch: { ...w, requested: rest, armed: allowed ? [...w.armed, toolId] : w.armed }, written: false };
    }
    case "tool_result": {
      const id = str(event.id);
      const running = w.running.filter(([rid]) => rid !== id);
      let index = id ? w.armed.indexOf(id) : -1;
      if (index < 0) index = w.armed.indexOf(null);
      if (index < 0) return { watch: { ...w, running }, written: false };
      const armed = w.armed.filter((_, i) => i !== index);
      const live = seq === null || seq > w.since;
      return { watch: { ...w, running, armed }, written: event.ok === true && live };
    }
    case "turn_end":
    case "error":
      return { watch: { ...w, running: [], requested: {}, armed: [] }, written: false };
    default:
      return { watch: w, written: false };
  }
}
