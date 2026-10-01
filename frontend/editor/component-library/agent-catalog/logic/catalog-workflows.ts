// Kategorie Workflows: postup od zadání k hotovu v pěti fázích uzlu (discover → define → build →
// verify → live, `PHASES` v backend/editor/agent_memory/desktop_v3_state.py). Drop položky vytvoří
// sektor s uzly podle fází a vazbami next — proto šablona vždy jmenuje všech pět fází (lint to hlídá).
import type { AgentItem } from "./agent-catalog";

export const workflowItems: AgentItem[] = [
  {
    id: "wf-five-phases",
    category: "workflows",
    label: "Zadání → hotovo v pěti fázích",
    hint: "Karta stojí na fázi discover → define → build → verify → live; fázi mění jen ten, kdo hlídá revizi.",
    icon: "⟳",
    kind: "workflow",
    rules: {
      must: [
        "Fáze uzlu jde jen dopředu (index ve PHASES roven nebo vyšší), nikdy zpátky bez vědomého rozhodnutí.",
        "Karta se uzavírá (done.confirmed) jen člověkem; agent smí done jen navrhnout.",
        "Definice hotovo (kritéria, blockConditions) se čte z karty, ne z paměti agenta.",
      ],
      mustNot: [
        "Neposouvat fázi bez splněných kritérií té aktuální.",
        "Neuzavírat kartu bez potvrzení člověka.",
      ],
    },
    decomposition: [
      { title: "discover", text: "Přečti node-brief, zjisti chybějící podklady." },
      { title: "define", text: "Ověř nebo doplň goal, acceptance a definitionOfDone." },
      { title: "build", text: "Proveď harness.actions/steps v pořadí, jen ve svém rozsahu." },
      { title: "verify", text: "Ověř proti stopConditions a kritériím, spusť ověřovací příkazy." },
      { title: "live", text: "Zapiš agent-output (blocks, reports, done.proposed) a handoff." },
    ],
    template: [
      "1. discover — přečti node-brief, zjisti, jaké podklady chybí; chybějící podklad je důvod zastavit.",
      "2. define — ověř nebo doplň goal, acceptance a definitionOfDone.criteria.",
      "3. build — proveď harness.actions/steps v pořadí, dotýkej se jen svého rozsahu.",
      "4. verify — spusť ověřovací příkazy a zkontroluj stopConditions.",
      "5. live — zapiš agent-output (blocks, reports, done.proposed) a handoff dalšímu agentovi.",
    ].join("\n"),
    endCriteria: "Všechna kritéria definitionOfDone jsou splněná, agent navrhl done a člověk ho potvrdil.",
    stopCondition: "Karta nemá žádný podklad (goal, acceptance, harness) — to je důvod zastavit a vyžádat si ho, ne domýšlet.",
    refs: [],
  },
  {
    id: "wf-contract-first",
    category: "workflows",
    label: "Kontrakt před kódem",
    hint: "docs/ nejdřív: rozhraní, soubory a testy zapsané, než padne první řádek kódu.",
    icon: "▤",
    kind: "workflow",
    rules: {
      must: [
        "Kontrakt (exportovaná jména, tvar dat, cesty souborů) je zapsaný v docs/ nebo v kartě dřív, než vznikne kód.",
        "Souběžní agenti pracují proti stejnému kontraktu, ne proti dohadům.",
        "Změna kontraktu za běhu se zapíše zpět do docs/, ne jen do kódu.",
      ],
      mustNot: [
        "Neměnit vyexportované jméno nebo tvar dat bez zápisu do kontraktu.",
        "Nezasahovat do složky, kterou kontrakt svěřil jinému agentovi.",
      ],
    },
    decomposition: [
      { title: "discover", text: "Najdi existující kontrakt (docs/pravidla-struktury.md, karta, brief sektoru)." },
      { title: "define", text: "Napiš nebo doplň přesné rozhraní: typy, exportované funkce, cesty souborů." },
      { title: "build", text: "Implementuj přesně proti kontraktu, nic navíc a nic mimo přidělenou složku." },
      { title: "verify", text: "Zkontroluj, že export odpovídá tomu, co kontrakt slíbil." },
      { title: "live", text: "Zapiš handoff s odkazem na kontrakt pro navazující agenty." },
    ],
    template: [
      "1. discover — najdi kontrakt v docs/ nebo v kartě; pokud chybí, je to stop podmínka.",
      "2. define — zapiš přesné rozhraní: exportovaná jména, typy, cesty souborů.",
      "3. build — implementuj přesně proti kontraktu, jen v přidělené složce.",
      "4. verify — over, že export odpovídá kontraktu (jména, tvar, cesty).",
      "5. live — zapiš handoff s odkazem na kontrakt, aby na něj navázal další agent.",
    ].join("\n"),
    endCriteria: "Kód exportuje přesně to, co kontrakt slíbil, a žádný soubor nevznikl mimo přidělenou složku.",
    stopCondition: "Kontrakt chybí nebo je nejednoznačný — zastav a vyžádej si přesné rozhraní, nedomýšlej názvy.",
    refs: [],
  },
  {
    id: "wf-main-delegates",
    category: "workflows",
    label: "Hlavní vlákno zadává, subagenti vykonávají",
    hint: "Hlavní model drží celek a ověřuje; hledání jde na levnější model, feature s testy dostane Sonnet/Opus s přesným zadáním.",
    icon: "⇉",
    kind: "workflow",
    rules: {
      must: [
        "Hlavní vlákno čte zadání, píše kontrakt a rozděluje práci na nezávislé kusy.",
        "Zadání subagentovi vždy nese kontrakt, seznam souborů, ověřovací příkazy a zákaz sahat mimo scope.",
        "Hlavní vlákno samo spouští ověření (pytest, npm test, npm run build) a nepřebírá hlášení hotovo naslepo.",
      ],
      mustNot: [
        "Nedelegovat rozhodování bez napsaného kontraktu.",
        "Nespouštět subagenta bez ověřovacích příkazů v zadání.",
      ],
    },
    decomposition: [
      { title: "discover", text: "Zjisti, co je nezávislý kus práce a jaký model se pro něj hodí." },
      { title: "define", text: "Napiš zadání: kontrakt, soubory, testy, zákaz sahat mimo scope." },
      { title: "build", text: "Spusť subagenty souběžně tam, kde jsou na sobě nezávislí." },
      { title: "verify", text: "Hlavní vlákno spustí ověřovací příkazy samo, výsledek subagenta nepřebírá naslepo." },
      { title: "live", text: "Shrň výsledek, zapiš handoff a nálezy do agent-workspace." },
    ],
    template: [
      "1. discover — rozliš nezávislé kusy práce a jejich náročnost.",
      "2. define — napiš zadání s kontraktem, soubory, ověřovacími příkazy a zákazem mimo scope.",
      "3. build — spusť subagenty (Explore/Sonnet/Opus) souběžně, kde to jde.",
      "4. verify — hlavní vlákno samo spustí uv run pytest backend, npm test, npm run build.",
      "5. live — shrň výsledek, zapiš handoff a nálezy.",
    ].join("\n"),
    endCriteria: "Výsledek subagentů prošel ověřovacími příkazy spuštěnými hlavním vláknem.",
    stopCondition: "Práci nejde rozdělit na nezávislé kusy nebo kontrakt chybí — zastav, rozděl ji jinak nebo si kontrakt vyžádej.",
    refs: [],
  },
  {
    id: "wf-bugfix-repro",
    category: "workflows",
    label: "Oprava chyby: reprodukce → test → oprava → ověření",
    hint: "Chyba se nejdřív zopakuje a zachytí padajícím testem, teprve pak se opravuje.",
    icon: "⚑",
    kind: "workflow",
    rules: {
      must: [
        "Reprodukce chyby (padající test) existuje dřív, než se sáhne na opravu.",
        "Oprava je nejmenší změna, která test zazelená, ne přepis okolí.",
        "Po opravě běží celá sada testů, ne jen ten nový.",
      ],
      mustNot: [
        "Neopravovat bez padajícího testu — jinak nejde poznat, že je to opravené.",
        "Neměnit chování mimo hlášenou chybu.",
      ],
    },
    decomposition: [
      { title: "discover", text: "Zopakuj chybu, najdi přesné kroky a místo v kódu." },
      { title: "define", text: "Napiš test, který chybu zachytí a dnes padá." },
      { title: "build", text: "Uveď nejmenší opravu, která test zazelení." },
      { title: "verify", text: "Spusť pytest backend, npm test a npm run build, zkontroluj, že nic dalšího nepadá." },
      { title: "live", text: "Zapiš chybu a opravu do agent-workspace (failures/fixes) pro dalšího agenta." },
    ],
    template: [
      "1. discover — zopakuj chybu, zapiš přesné kroky, kterými nastává.",
      "2. define — napiš test, který dnes padá a zachytí přesně tuto chybu.",
      "3. build — uveď nejmenší opravu, která test zazelení.",
      "4. verify — spusť uv run pytest backend, npm test, npm run build.",
      "5. live — zapiš do agent-workspace, co se pokazilo (failures) a čím se to opravilo (fixes).",
    ].join("\n"),
    endCriteria: "Dříve padající test je zelený, celá sada testů prochází a změna je omezená na příčinu.",
    stopCondition: "Chybu nejde zopakovat nebo chybí přístup k prostředí — zastav a vyžádej si přesné kroky reprodukce.",
    refs: [],
  },
];
