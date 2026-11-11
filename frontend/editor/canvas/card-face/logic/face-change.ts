// Odznak pořadí podle záměru a krátký popisek „kdy“ (dnes čas, včera, letos bez roku). Čte je boční panel stopy
// práce (`editor/block-panel/logic/panel-view.ts`). Čisté funkce bez Reactu.
import { dayKey, dayLabel, timeLabel } from "@/editor/canvas/activity-log/logic/activity-log";

/** Odznak pořadí `F·PP`: `302` → `3·02`, `1205` → `12·05`; bez pořadí nic. */
export function orderBadge(order: number | null | undefined): string | null {
  if (typeof order !== "number" || !Number.isSafeInteger(order) || order < 0) return null;
  return `${Math.floor(order / 100)}·${String(order % 100).padStart(2, "0")}`;
}

/** Kdy krátce: dnes „HH:MM“, „včera“, letos „6. 10.“, jinak celé datum. */
export function changeWhen(at: string, now: Date = new Date()): string {
  const key = dayKey(at);
  if (key === "?") return "";
  if (key === dayKey(now)) return timeLabel(at);
  const label = dayLabel(key, now);
  if (label === "Včera") return "včera";
  return key.startsWith(String(now.getFullYear()) + "-") ? label.replace(/ \d{4}$/, "") : label;
}
