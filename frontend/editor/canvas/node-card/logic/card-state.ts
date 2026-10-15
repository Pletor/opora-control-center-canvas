// Stavová věta karty (docs/proces-karty.md §3): z frontier, přehledu práce, pronájmu, pipeline a návrhu uzavření
// vznikne právě jedna věta podle přednosti. Čistá data; dílek `CardState` ji jen vypíše.
import type { CardProcessView } from "./card-process";
import type { FrontierItem } from "./use-frontier";
import type { WorkRow } from "./use-work-overview";
import type { CardLease } from "./use-leases";
import { KIND_LABEL, LENS_LABEL } from "@/editor/workflow/card-pipeline/logic/pipeline-model";

export type CardStateTone = "ok" | "warn" | "fail" | "run" | "idle";
export type CardStateLine = {
  tone: CardStateTone;
  text: string;
  /** Co se právě děje, nebo proč karta stojí; vypíše se tišeji za větou. */
  detail: string;
  /** Agent navrhl uzavření: věta nese tlačítko Potvrdit. */
  confirm: boolean;
  /** Začátek práce (ISO); dobu z něj počítá až dílek, aby data karty nenesla běžící čas. */
  since?: string;
};

export type CardStateInput = {
  closed: boolean;
  doneProposed: boolean;
  process?: CardProcessView;
  frontier?: FrontierItem;
  work?: WorkRow;
  lease?: CardLease;
};

const line = (tone: CardStateTone, text: string, detail = "", confirm = false): CardStateLine => ({ tone, text, detail, confirm });

/** „12 min“ pro dobu práce; bez času jen prázdno. */
export function sinceLabel(startedAt: string | null | undefined, now: number): string {
  if (!startedAt) return "";
  const minutes = Math.max(0, Math.round((now - Date.parse(startedAt)) / 60000));
  if (!Number.isFinite(minutes)) return "";
  return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

const who = (dot: { kind: keyof typeof KIND_LABEL; lens: string; title: string }) =>
  KIND_LABEL[dot.kind] + (dot.lens ? " " + LENS_LABEL[dot.lens as keyof typeof LENS_LABEL] : "") + (dot.title ? ": " + dot.title : "");

export function cardState(input: CardStateInput): CardStateLine {
  const { process, frontier, work, lease } = input;
  if (input.closed) return line("ok", "Uzavřeno");
  const stuck = process?.dots.find((d) => d.stuck);
  if (stuck) return line("warn", "Uvízlo: " + who(stuck), "čeká na tebe" + (stuck.note ? " · " + stuck.note : ""));
  const ask = work?.waitingOnHuman[0] ?? frontier?.waitingOnHuman?.[0];
  if (ask) return line("warn", "Čeká na tebe", ask.ask);
  const blockers = work?.blockedBy.length ? work.blockedBy : frontier?.blockedBy ?? [];
  const blocked = blockers.length ? "blokuje: " + blockers.map((b) => b.name || b.id).join(", ") : "";
  // Návrh uzavření je rozhodnutí člověka, ale překážku nesmí skrýt: věta ji nese hned za návrhem.
  if (input.doneProposed) return line("warn", "Ke schválení", ["agent navrhl uzavření", blocked].filter(Boolean).join(" · "), true);
  if (blockers.length) return line("fail", "Blokuje: " + blockers.map((b) => b.name || b.id).join(", "));
  // „Pracuje“ jen s hlášenou prací (přehled práce); samotný pronájem je „Převzal“, protože činnost nedokládá.
  if (work?.status === "claimed" && work.agent) return { ...line("run", "Pracuje " + work.agent), since: work.startedAt ?? undefined };
  if (lease?.active) return line("run", "Převzal " + lease.owner, "pronájem drží, činnost nehlášena");
  const current = process?.dots.find((d) => d.current);
  if (current) return line("idle", "Na řadě: " + who(current));
  if (process && !process.routed) return line("idle", "Čeká na router", process.proposed ? process.proposed + " etap ke schválení" : "");
  if (frontier?.status === "frontier") return line("idle", "K převzetí");
  // Bez načtené frontier (nebo mimo ni) nelze „k převzetí“ slíbit; věta zůstane neutrální.
  return line("idle", "Čeká");
}
