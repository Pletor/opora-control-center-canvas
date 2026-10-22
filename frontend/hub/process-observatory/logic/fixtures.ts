// Testovací stavebnice událostí v drátovém tvaru `opora.process-event/1` (jen pro testy této složky).
import type { OporaEvent } from "@/editor/live-strip/logic/events-client";
import { toFlowEvent, type FlowEvent, type WireProcessEvent } from "./process-event";

type Extra = Partial<WireProcessEvent> & { worker?: string };

export function wire(id: number, card: string | null, kind: string, phase: string, state: string, extra: Extra = {}): OporaEvent {
  const { worker, ...rest } = extra;
  const office = rest.source === "office";
  return {
    id, at: new Date(Date.UTC(2026, 9, 22, 10, 0, id)).toISOString(), kind, projectId: "opora", workspaceId: "main",
    nodeId: card, executionId: null, stepId: null, prNumber: null, stage: null, health: null,
    actor: office ? { kind: "agent", name: worker ?? "shot" } : { kind: "system", name: "opora" },
    data: office && worker ? { actor: { kind: "worker", id: `w-${worker}`, name: worker } } : {},
    source: "opora", phase, state, title: `${kind} ${id}`, detail: null, refs: card ? { cardId: card } : {}, tool: null,
    eventId: office ? `office:floor:${id}` : `opora:${id}`, schema: "opora.process-event/1", ...rest,
  } as OporaEvent;
}

export const flow = (...args: Parameters<typeof wire>): FlowEvent => toFlowEvent(wire(...args));
