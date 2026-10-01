// Kategorie Agenti: role a model. Drop vytvoří na kartě pravidlo s rolí („Role: …“) a invarianty role.
// Volba modelu a effortu vychází z docs/predani-modelum.md.
import type { AgentItem } from "./agent-catalog";

export const agentItems: AgentItem[] = [
  {
    id: "agent-main-thread",
    category: "agents",
    label: "Hlavní vlákno: Fable 5.1 / Opus 5.5",
    purpose: "Drží celek: čte zadání, píše kontrakt, rozděluje práci a sám ověřuje výsledek.",
    kind: "agent",
    relates: ["@wf-main-delegates", "@test-done-gates", "Volba modelu a effortu: docs/predani-modelum.md."],
    invariants: [],
  },
  {
    id: "agent-explore-haiku",
    category: "agents",
    label: "Subagent Explore: haiku",
    purpose: "Levné hledání a čtení: vrací cesty a řádky, nic nemění.",
    kind: "agent",
    relates: ["@agent-main-thread"],
    invariants: [{ kind: "must_not", text: "Explore nezapisuje soubory." }],
  },
  {
    id: "agent-sonnet-feature",
    category: "agents",
    label: "Subagent Sonnet 5.5: menší feature s testy",
    purpose: "Samostatný, přesně zadaný kus práce s testy; agentní kódování začíná na effortu medium.",
    kind: "agent",
    relates: [
      "@wf-contract-first",
      "@test-done-gates",
      "Na nižším effortu se častěji zastaví nebo vynechá ověření, proto zadání žádá skutečnou kontrolu před hotovo.",
    ],
    invariants: [{ kind: "must_not", text: "Nesahá mimo soubory přidělené v zadání." }],
  },
  {
    id: "agent-opus-architecture",
    category: "agents",
    label: "Subagent Opus 5.5: feature s architekturou",
    purpose: "Větší kus s víc rozhodnutími nebo dopadem na architekturu; výchozí effort medium.",
    kind: "agent",
    relates: [
      "@wf-contract-first",
      "Před změnou se rozhlédne: node-brief, rodič, sousedé, mapa Graphify.",
    ],
    invariants: [{ kind: "must_not", text: "Nemění cizí kontrakt; rozhodnutí přes rámec zadání vrací hlavnímu vláknu." }],
  },
];
