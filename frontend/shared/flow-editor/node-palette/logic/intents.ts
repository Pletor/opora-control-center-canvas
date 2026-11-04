// Průvodce „Co chci udělat?“: záměr člověka → typy uzlů se štítkem `intents` z registru. Deterministicky, bez modelu;
// stejný katalog čte LLM okno. Typy jdou FE → BE → DB → Infra → AI → ostatní, uvnitř vrstvy v pořadí registru.
import type { Layer, NodeTypeSpec } from "../../logic/flow-types";
import { LAYER_ORDER } from "../../flow-lanes/logic/layers";

export const INTENTS = [
  { id: "input", label: "Přijmout vstup" }, { id: "validate", label: "Ověřit" }, { id: "compute", label: "Spočítat" },
  { id: "store", label: "Uložit" }, { id: "call-service", label: "Zavolat službu" }, { id: "show", label: "Zobrazit výsledek" },
  { id: "decide", label: "Rozhodnout" }, { id: "repeat", label: "Opakovat" }, { id: "notify", label: "Upozornit" }, { id: "ai", label: "AI" },
] as const;
export type IntentId = typeof INTENTS[number]["id"];
export type IntentOption = { type: string; layer: Layer | undefined; use: string | undefined };

export function intentOptions(types: readonly NodeTypeSpec[], intent: string): IntentOption[] {
  const rank = (layer: Layer | undefined) => layer ? LAYER_ORDER.indexOf(layer) : LAYER_ORDER.length;
  return types.filter((spec) => spec.intents?.includes(intent))
    .map((spec, index) => ({ index, option: { type: spec.type, layer: spec.layer, use: spec.use } }))
    .sort((a, b) => rank(a.option.layer) - rank(b.option.layer) || a.index - b.index).map((item) => item.option);
}
