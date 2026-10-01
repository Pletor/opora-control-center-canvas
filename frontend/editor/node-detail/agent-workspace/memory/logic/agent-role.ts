// Role karty (`agentRole`) jako čtení a mutace stavu Desktop v3. Nový způsob ukládání tady
// nevzniká: je to obyčejná mutace uzlu, kterou rodič pošle do `useDesktopState().mutate`, takže
// role jede stejnou cestou, CAS revizí a zámkem jako fáze, kritéria nebo bloky. Karta bez role je
// platný stav (`null`), ne chyba — paměť role se u ní jen nečte ani nezapisuje.
import { nodeWorkflowOf, type DesktopState } from "@/shared/desktop-state/logic/types";

/** Role uzlu ze stavu; starší uložený uzel i neznámé id karty se čtou jako „bez role“. */
export function agentRoleOf(state: DesktopState, nodeId: string): string | null {
  const role = state.nodes[nodeId]?.agentRole;
  return typeof role === "string" && role ? role : null;
}

/** Mutace pro `mutate`: nastaví roli jednoho uzlu a ostatních se nedotkne. Prázdná volba = `null`. */
export function setAgentRole(nodeId: string, role: string | null) {
  return (current: DesktopState): DesktopState => ({
    ...current,
    nodes: { ...current.nodes, [nodeId]: { ...nodeWorkflowOf(current, nodeId), agentRole: role || null } },
  });
}
