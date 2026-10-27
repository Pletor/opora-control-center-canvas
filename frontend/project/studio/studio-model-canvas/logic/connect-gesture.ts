// Propojení portů na plátně MODELu (prototyp `connection-gesture.mjs` a dvojklik port → port): první klik port vybere,
// klik na port opačného směru vazbu vytvoří, klik na tentýž port výběr zruší. Během výběru nebo tažení se každý port
// opačného směru označí jako kompatibilní, nebo ztlumí, podle pravidel modelu. Čistá logika bez Reactu.
import { connectionError } from "../../model/logic/model-rules";
import type { PortDirection, PortRef } from "../../model/logic/model-types";
import { componentType } from "../../model/logic/catalog";
import { policyOf, type EditModel } from "../../studio-model/logic/model-edit";

export type PendingPort = PortRef & { direction: PortDirection };
export type PortTarget = "compatible" | "invalid";
export type Link = { from: PortRef; to: PortRef };

export const portKey = (ref: PortRef) => `${ref.nodeId}\u0000${ref.portId}`;
const ref = (port: PendingPort): PortRef => ({ nodeId: port.nodeId, portId: port.portId });

/** Konce vazby podle směru: výstup je vždy začátek. Stejný směr vazbu nedává. */
export function orient(a: PendingPort, b: PendingPort): Link | null {
  if (a.direction === b.direction) return null;
  return a.direction === "output" ? { from: ref(a), to: ref(b) } : { from: ref(b), to: ref(a) };
}

/** Co udělá klik na port: vybrat ho, zrušit výběr, nebo vytvořit vazbu s vybraným portem opačného směru. */
export function portClick(pending: PendingPort | null, clicked: PendingPort): { pending: PendingPort | null; link?: Link } {
  if (!pending) return { pending: clicked };
  if (portKey(pending) === portKey(clicked)) return { pending: null };
  const link = orient(pending, clicked);
  return link ? { pending: null, link } : { pending: clicked };
}

/** Porty opačného směru než `start`: kompatibilní, nebo ztlumené s důvodem v pravidlech. Bez startu nic. */
export function portTargets(model: EditModel, start: PendingPort | null): Map<string, PortTarget> {
  const targets = new Map<string, PortTarget>();
  if (!start) return targets;
  for (const node of model.nodes)
    for (const port of componentType(node.type)?.ports ?? []) {
      if (port.direction === start.direction) continue;
      const link = orient(start, { nodeId: node.id, portId: port.id, direction: port.direction })!;
      targets.set(portKey({ nodeId: node.id, portId: port.id }), connectionError(model, link.from, link.to, undefined, policyOf(model)) ? "invalid" : "compatible");
    }
  return targets;
}
