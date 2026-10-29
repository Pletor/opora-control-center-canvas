import type { QueueStatus, QueueTask } from "./heart-api";

/** Skupiny fronty v pořadí, jak je člověk čte: co čeká, co se dělá, co je hotové a co ne. */
export const QUEUE_ORDER: { status: QueueStatus; label: string }[] = [
  { status: "ready", label: "Připraveno" },
  { status: "assigned", label: "Přiděleno" },
  { status: "done", label: "Hotovo" },
  { status: "failed", label: "Selhalo" },
  { status: "cancelled", label: "Zrušeno" },
];

export type QueueGroup = { status: QueueStatus; label: string; tasks: QueueTask[] };

/** Úkoly → neprázdné skupiny v pořadí `QUEUE_ORDER`; uvnitř skupiny podle `order` srdce. */
export function groupQueue(tasks: QueueTask[]): QueueGroup[] {
  return QUEUE_ORDER.map(({ status, label }) => ({
    status,
    label,
    tasks: tasks.filter((task) => task.status === status).sort((a, b) => a.order - b.order),
  })).filter((group) => group.tasks.length > 0);
}

/** Kdo úkol drží: relace pracovníka (zkrácená), jinak kdo ho založil. */
export function holderLabel(task: QueueTask): string {
  if (task.sessionId) return `relace ${task.sessionId.replace(/^gs_/, "").slice(0, 6)}`;
  if (task.createdBy === "heart") return "srdce";
  return task.createdBy === "human" ? "člověk" : task.createdBy;
}
