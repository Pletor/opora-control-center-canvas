// Porty uzlů podle params a kontrola grafu pro rozpracovaný graf plátna knihovny. Obojí se ptá serveru
// (`node-ports`, `graph-check`) chvíli po poslední úpravě, ne při každém tahu; porty se pamatují podle klíče dotazu,
// takže posun uzlu nic nenačítá. Chyba čtení nechá poslední známý stav a nic nezapisuje.
import { useEffect, useRef, useState } from "react";
import type { FlowGraph, NodeTypeSpec, PortSpec } from "@/shared/flow-editor/logic/flow-types";
import { checkGraph, nodePorts } from "./library-api";
import { portQueries } from "./node-ports";

const WAIT_MS = 350;

export function useFlowChecks(graph: FlowGraph, types: readonly NodeTypeSpec[]): { nodePorts: ReadonlyMap<string, PortSpec[]>; errors: string[] | null } {
  const cache = useRef(new Map<string, Promise<PortSpec[]>>());
  const [ports, setPorts] = useState<ReadonlyMap<string, PortSpec[]>>(new Map());
  const [errors, setErrors] = useState<string[] | null>(null);
  useEffect(() => {
    if (!types.length) return;
    let alive = true;
    const timer = setTimeout(() => {
      const queries = portQueries(graph, new Map(types.map((spec) => [spec.type, spec])));
      void Promise.all([...queries].map(async ([nodeId, query]) => {
        if (!cache.current.has(query.key)) cache.current.set(query.key, nodePorts(query.type, query.params, query.onError).catch((error) => { cache.current.delete(query.key); throw error; }));
        return [nodeId, await cache.current.get(query.key)!] as const;
      })).then((pairs) => { if (alive) setPorts(new Map(pairs)); }, () => {});
      void checkGraph(graph).then((found) => { if (alive) setErrors(found); }, () => {});
    }, WAIT_MS);
    return () => { alive = false; clearTimeout(timer); };
  }, [graph, types]);
  return { nodePorts: ports, errors };
}
