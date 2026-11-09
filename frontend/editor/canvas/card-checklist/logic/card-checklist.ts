// Kontrolní pás karty: deset polí ano / ne, co karta pro agenta už má a co chybí. Počítá server
// (`GET /api/desktop-v3/card-checklist`, backend/editor/agent_packet/card_checklist.py) stejně jako
// pro frontier a node-brief; tady jsou jen typy, načtení vrstvy a odvozené souhrny pro oblast a vazby.
import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { keepSame } from "@/shared/hooks/logic/same-response";
import type { CanvasNode, GraphEdge } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";

export type CheckState = "yes" | "no" | "run" | "fail";
export type CheckKey = "goal" | "done" | "text" | "blocks" | "links" | "source" | "checks" | "pipeline" | "evidence" | "handoff";
export type CheckItem = { key: CheckKey; label: string; state: CheckState; hint: string };
export type Checklists = Record<string, CheckItem[]>;

export const STATE_MARK: Record<CheckState, string> = { yes: "✓", no: "–", run: "●", fail: "!" };
export const STATE_LABEL: Record<CheckState, string> = { yes: "je", no: "chybí", run: "rozpracováno", fail: "selhalo / čeká na tebe" };

/** Pás karet jedné vrstvy; obnovuje se se stavem karet a nejpozději po 20 s. */
export function useCardChecklist(scope: { project: string; workspace: string } | undefined, parent: string | null, revision: unknown): Checklists | undefined {
  const [value, setValue] = useState<{ key: string; nodes: Checklists } | null>(null);
  const key = JSON.stringify([scope?.project, scope?.workspace, parent]);
  usePolling(async () => {
    if (!scope) return;
    try {
      const result = await api<{ nodes: Checklists }>("/api/desktop-v3/card-checklist?" + new URLSearchParams({ ...scope, layer: parent ?? "" }));
      setValue((current) => keepSame(current, { key, nodes: result.nodes }));
    } catch {
      // Pás je doplněk: bez něj karta funguje dál, jen bez souhrnu.
      setValue((current) => (current?.key === key ? null : current));
    }
  }, { intervalMs: 20000, enabled: !!scope, refreshKeys: [key], debouncedKeys: [revision] });
  return value?.key === key ? value.nodes : undefined;
}

/** Souhrn oblasti z pásů jejích karet: kolik má pipeline, důkazy, předávky a kolik čeká na člověka. */
export function areaSummary(lists: CheckItem[][]) {
  const count = (key: CheckKey) => lists.filter((items) => items.find((i) => i.key === key)?.state === "yes").length;
  return {
    total: lists.length,
    bars: [
      { key: "pipeline" as const, label: "pipeline", value: count("pipeline") },
      { key: "evidence" as const, label: "důkazy", value: count("evidence") },
      { key: "handoff" as const, label: "předávky", value: count("handoff") },
    ],
    waiting: lists.filter((items) => items.some((i) => i.state === "fail")).length,
  };
}

/** Druh uzlu podle id: plátno ho postaví jednou za graf a předá všem vazbám (`handoffMark`). */
export const nodeKinds = (nodes: Pick<CanvasNode, "id" | "kind">[]): ReadonlyMap<string, CanvasNode["kind"]> =>
  new Map(nodes.map((n) => [n.id, n.kind]));

/** Obálka předávky na vazbě: zpráva je → „sent“; zdroj je hotový (navržen / uzavřen) a zpráva chybí → „missing“;
 *  jinak se nic nekreslí, aby plánovací vazby nebyly ukřičené. Jen vazby mezi kartami (`next`, `block`).
 *  Druhy uzlů přicházejí hotové (`nodeKinds`), aby se mapa nestavěla znovu pro každou vazbu. */
export function handoffMark(edge: GraphEdge, state: DesktopState, kinds: ReadonlyMap<string, CanvasNode["kind"]>): "sent" | "missing" | null {
  const port = edge.port ?? "next";
  if (edge.relation || (port !== "next" && port !== "block")) return null;
  if (kinds.get(edge.source) !== "node" && kinds.get(edge.source) !== "sector") return null;
  if (state.edges?.[edge.id]?.handoff?.trim()) return "sent";
  const done = state.nodes[edge.source]?.done;
  return done && (done.confirmed || done.by === "agent") ? "missing" : null;
}
