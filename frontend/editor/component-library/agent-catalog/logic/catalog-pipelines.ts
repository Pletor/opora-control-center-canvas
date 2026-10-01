// Kategorie Pipelines: řetěz kroků do bloku Akce. Know-how nese Knihovna; pipeline na ni odkazuje
// přes `@id` v `relates`, ne kopií textu. Id pipeline jsou uložená v `actions[].pipelineId` na kartách,
// proto se nemění.
import type { AgentItem } from "./agent-catalog";

export const pipelineItems: AgentItem[] = [
  {
    id: "pl-feature-folder",
    category: "pipelines",
    label: "Postav feature složku",
    purpose: "Celá feature složka podle pravidel struktury: rodič, dílky, logika s testem, styl a README.",
    kind: "action",
    relates: ["@fe-parent-composes", "@fe-pure-model", "@css-bem-block", "@test-unit-beside"],
    invariants: [],
    steps: [
      { title: "Kostra", text: "components/, logic/, styles/, README.md." },
      { title: "Rodič a dílky", text: "Rodič skládá a ukládá, dílky dostávají props." },
      { title: "Logika", text: "Čisté funkce s testem vedle." },
      { title: "Styl", text: "Jeden BEM soubor s příběhovým komentářem." },
    ],
    done: ["Složka má components/, logic/, styles/ a README.md a npm test prochází."],
    stopCondition: "Umístění souboru neodpovídá docs/pravidla-struktury.md.",
  },
  {
    id: "pl-backend-endpoint-cas",
    category: "pipelines",
    label: "Backend endpoint s CAS",
    purpose: "Nový zápisový endpoint: tenký router, logika v modulu, validace na serveru, revize s CAS a test vedle.",
    kind: "action",
    relates: ["@be-environment-router", "@sec-server-validation", "@be-cas-revision", "@test-unit-beside"],
    invariants: [],
    steps: [
      { title: "Router", text: "Tvar vstupu a volání modulu." },
      { title: "Validace", text: "Tvar, délky a práva na serveru." },
      { title: "Revize", text: "expectedRevision, 409 při neshodě." },
      { title: "Test", text: "test_<modul>.py vedle modulu." },
    ],
    done: ["Zápis se starou revizí vrátí 409 a neplatný vstup 400.", "test_<modul>.py prochází pod uv run pytest backend."],
    stopCondition: "Není jasné, do kterého modulu prostředí logika patří.",
  },
  {
    id: "pl-verify-before-done",
    category: "pipelines",
    label: "Ověření před hotovo",
    purpose: "Spustí brány hotovo a jejich výstup přiloží k hlášení.",
    kind: "action",
    relates: ["@test-done-gates"],
    invariants: [],
    steps: [{ title: "Brány", text: "Podle prvku Brány hotovo; výstup do hlášení." }],
    done: ["Výstup bran je v hlášení a žádná nepadá."],
    stopCondition: "Některá brána selže nebo ji nejde spustit.",
  },
  {
    id: "pl-fill-card-via-api",
    category: "pipelines",
    label: "Naplnění karty přes API",
    purpose: "Agent zapíše výsledek do karty přes API: agent-workspace, agent-output a návrh done, vše s revizí a vlastním Origin.",
    kind: "action",
    relates: ["@be-cas-revision", "@sec-same-origin-write", "Kontrakt: docs/karta-pro-agenty.md (agent-workspace, agent-output)."],
    invariants: [{ kind: "must_not", text: "Agent nezapisuje done.confirmed: true; kartu uzavírá člověk." }],
    steps: [
      { title: "Čtení", text: "GET node-brief, zapamatovat revizi." },
      { title: "Pracovní prostor", text: "POST agent-workspace (log, failures, fixes, handoff)." },
      { title: "Výstup", text: "POST agent-output (bloky, zprávy na odchozích vazbách, done.proposed)." },
    ],
    done: ["Server vrátil novou revizi bez 409/403 a karta nese log, stav bloků a navržené done."],
    stopCondition: "Server opakovaně vrací 409 nebo 403.",
  },
];
