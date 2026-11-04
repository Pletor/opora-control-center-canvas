// Vrstvy plátna procesů: pořadí pruhů, české názvy a štítky na kartě. Efektivní vrstva uzlu je jeho vlastní `layer`
// (přepis), jinak výchozí vrstva typu; typ bez vrstvy (srdce, záměr stránky) vrstvu nemá a pruh nedostane.
import { LAYERS, type FlowNode, type Layer, type NodeTypeSpec } from "../../logic/flow-types";

export const LAYER_ORDER: readonly Layer[] = LAYERS;
export const LAYER_LABEL: Record<Layer, string> = { fe: "Frontend", be: "Backend", db: "Databáze", infra: "Infrastruktura", ai: "AI", neutral: "Ostatní" };
export const LAYER_BADGE: Record<Layer, string> = { fe: "FE", be: "BE", db: "DB", infra: "INFRA", ai: "AI", neutral: "·" };

export const effectiveLayer = (node: Pick<FlowNode, "layer">, spec: Pick<NodeTypeSpec, "layer"> | undefined): Layer | undefined => node.layer ?? spec?.layer;
