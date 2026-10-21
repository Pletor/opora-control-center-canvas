// Kontrakt „stejná data pro UI i agenta“: každý prvek UI nese data-oh-* atribut, který odpovídá
// přesné cestě v dokumentu agent-state. Tabulka je zdrojem pravdy pro pohled i pro docs/oporahub-ui.md.
export type ContractRow = { element: string; attribute: string; jsonPath: string; source: string };

export const CONTRACT: ContractRow[] = [
  { element: "Kořen pohledu", attribute: "data-oh-view · data-oh-accepted-head · data-oh-etag", jsonPath: "heads.acceptedHead", source: "GET …/agent-state" },
  { element: "Zrcadlo dokumentu", attribute: "script#oh-agent-state (application/json)", jsonPath: "(celý dokument)", source: "GET …/agent-state" },
  { element: "Dlaždice horního pásu", attribute: "data-oh-field · data-oh-value", jsonPath: "heads.* · riskMix · decisions.length", source: "GET …/agent-state" },
  { element: "Etapa smyčky", attribute: "data-oh-stage · data-oh-health · data-oh-reason · data-oh-count", jsonPath: "stages[]", source: "GET …/agent-state" },
  { element: "Spojka etap", attribute: "data-oh-link · data-oh-link-state", jsonPath: "odvozeno ze stages[].health", source: "UI (odvozené)" },
  { element: "Rozhodnutí člověka", attribute: "data-oh-decision · data-oh-action-id", jsonPath: "decisions[].id · .actionId", source: "GET …/agent-state" },
  { element: "Řádek fronty akcí", attribute: "data-oh-action-id · data-oh-action-status · data-oh-verb · data-oh-method · data-oh-path · data-oh-target · data-oh-block-reason", jsonPath: "actions[]", source: "GET …/agent-state" },
  { element: "Fakt pro CAS", attribute: "data-oh-field · data-oh-value", jsonPath: "heads.*", source: "GET …/agent-state" },
  { element: "Mezera", attribute: "data-oh-gap · data-oh-health=\"not_connected\"", jsonPath: "gaps[].id", source: "GET …/agent-state" },
  { element: "Karta (detail)", attribute: "data-oh-view=\"card\" · data-oh-node-id", jsonPath: "actions[verb=claim].targetId", source: "GET …/agent-state + …/executions" },
  { element: "Změnová sada karty", attribute: "data-oh-changeset · data-oh-parent · data-oh-stale · data-oh-accepted", jsonPath: "—", source: "GET …/changesets" },
  { element: "Běh karty", attribute: "data-oh-execution · data-oh-epoch · data-oh-execution-state", jsonPath: "—", source: "GET …/executions" },
  { element: "PR a zápis do plánu", attribute: "data-oh-pr-link · data-oh-writeback", jsonPath: "stages[pull_request|plan_writeback].health", source: "GET …/agent-state" },
];
