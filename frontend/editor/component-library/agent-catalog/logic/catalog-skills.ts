// Kategorie Skills: kdy sáhnout po instalovaném skillu. `kind: "info"` — položka se na plátno netáhne,
// je to jen orientace.
import type { AgentItem } from "./agent-catalog";

export const skillItems: AgentItem[] = [
  {
    id: "skill-opora-control-center",
    category: "skills",
    label: "opora-control-center: obsluha aplikace",
    purpose: "Obsluha běžící aplikace OPORA: uzly, sektory, podklady pro agenta a mapy; ne změny jejího zdrojového kódu.",
    kind: "info",
    relates: ["Ze skillu se načítá jen reference, kterou úkol potřebuje."],
    invariants: [],
  },
  {
    id: "skill-prompt-master",
    category: "skills",
    label: "prompt-master: prompt pro konkrétní nástroj",
    purpose: "Napsání nebo úprava promptu pro pojmenovaný AI nástroj, jen na výslovnou žádost.",
    kind: "info",
    relates: [],
    invariants: [],
  },
  {
    id: "skill-graphify",
    category: "skills",
    label: "graphify: kód a dokumenty jako graf znalostí",
    purpose: "Mapa kódu jako graf znalostí; otázky na architekturu a vztahy souborů jdou nejdřív přes graphify-out/.",
    kind: "info",
    relates: ["V node-brief říká context.knowledgeGraph.available, jestli mapa existuje."],
    invariants: [],
  },
];
