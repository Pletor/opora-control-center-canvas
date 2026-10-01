// Pravidla a postupy, které platí jen pro některé projekty: multitenantní aplikace, modulární monolit
// a mikroslužby. Každá položka nese `fits` (docs/suplik-a-profil.md), takže projekt jiného profilu ji
// najde jen pod „Mimo profil“ nebo hledáním. Tvar je stejný jako u sousedů: pravidlo uzlu začíná
// „Pravidlo uzlu:“, workflow jmenuje všech pět fází uzlu.
import type { AgentItem } from "./agent-catalog";

export const architectureRuleItems: AgentItem[] = [
  {
    id: "rule-tenant-in-every-query",
    category: "rules",
    label: "Každý dotaz nese tenanta",
    hint: "Pravidlo uzlu: žádné čtení ani zápis dat zákazníka bez podmínky na tenanta.",
    icon: "◎",
    kind: "rule",
    fits: { tenancy: ["multi"] },
    rules: {
      must: [
        "Každý dotaz na data zákazníka filtruje podle tenanta z kontextu požadavku.",
        "Nový endpoint má test, že tenant A nevidí data tenanta B.",
      ],
      mustNot: [
        "Žádný dotaz na data zákazníka bez podmínky na tenanta.",
        "Žádný tenant převzatý z těla požadavku místo z přihlášení.",
      ],
    },
    decomposition: [
      { title: "Kontext", text: "Tenant přichází z požadavku, ne z parametru klienta." },
      { title: "Dotaz", text: "Podmínka na tenanta je v repozitáři, ne v každém volání zvlášť." },
      { title: "Test", text: "Dva tenanti a ověření, že data neprotečou." },
    ],
    template: [
      "1. Najdi všechny dotazy, které změna přidává nebo mění.",
      "2. Ověř, že každý filtruje podle tenanta z kontextu požadavku.",
      "3. Doplň test se dvěma tenanty a ověř, že se data nemíchají.",
    ].join("\n"),
    endCriteria: "Každý nový nebo změněný dotaz filtruje podle tenanta a test se dvěma tenanty prochází.",
    stopCondition: "Není jasné, odkud se tenant v této části bere — zastav a vyžádej si model izolace dat.",
    refs: ["tenant-request-context", "tenant-data-isolation"],
  },
  {
    id: "rule-modules-keep-data",
    category: "rules",
    label: "Moduly si nesahají do dat",
    hint: "Pravidlo uzlu: modul čte a píše jen své tabulky, cizí data bere přes veřejné API modulu.",
    icon: "▣",
    kind: "rule",
    fits: { architecture: ["modular"] },
    rules: {
      must: [
        "Modul čte a píše jen tabulky, které vlastní.",
        "Data jiného modulu se berou přes jeho veřejné funkce.",
      ],
      mustNot: [
        "Žádný import z vnitřku cizího modulu.",
        "Žádný dotaz do tabulek cizího modulu.",
      ],
    },
    decomposition: [
      { title: "Vlastník", text: "Ke každé tabulce je jasné, který modul ji vlastní." },
      { title: "Hranice", text: "Volání mezi moduly jde jen přes veřejné API." },
    ],
    template: [
      "1. Zjisti, kterému modulu patří tabulky, na které změna sahá.",
      "2. Cizí data ber přes veřejné funkce jejich modulu; chybí-li funkce, navrhni ji vlastníkovi.",
      "3. Ověř, že změna nepřidala import z vnitřku cizího modulu.",
    ].join("\n"),
    endCriteria: "Změna sahá jen na tabulky svého modulu a jinam volá jen veřejné API modulů.",
    stopCondition: "Vlastník tabulky není jasný nebo veřejná funkce chybí — zastav a vyžádej si rozhodnutí o hranici.",
    refs: ["be-module-boundary"],
  },
  {
    id: "rule-service-owns-data",
    category: "rules",
    label: "Služba vlastní svá data",
    hint: "Pravidlo uzlu: do databáze služby píše jen ona; ostatní služby jdou přes API nebo události.",
    icon: "⛁",
    kind: "rule",
    fits: { architecture: ["microservices"] },
    rules: {
      must: [
        "Služba píše jen do své databáze nebo schématu.",
        "Data jiné služby se berou přes její API nebo z jejích událostí.",
      ],
      mustNot: [
        "Žádné připojení k databázi jiné služby.",
        "Žádná sdílená tabulka mezi službami.",
      ],
    },
    decomposition: [
      { title: "Vlastnictví", text: "Každé úložiště patří jedné službě." },
      { title: "Přístup", text: "API nebo události, nikdy přímý dotaz." },
    ],
    template: [
      "1. Zjisti, které služby změna potřebuje a čí data čte.",
      "2. Cizí data ber přes API nebo z událostí; nepřidávej připojení k cizí databázi.",
      "3. Ověř, že konfigurace služby obsahuje jen její vlastní databázi.",
    ].join("\n"),
    endCriteria: "Změna nepřidala přístup k databázi jiné služby a cizí data bere přes API nebo události.",
    stopCondition: "Potřebná data nejdou získat přes API ani události — zastav a vyžádej si rozhodnutí o kontraktu služby.",
    refs: ["ms-service-database"],
  },
];

export const architectureWorkflowItems: AgentItem[] = [
  {
    id: "wf-saga-across-services",
    category: "workflows",
    label: "Saga přes služby",
    hint: "Změna přes víc služeb jako řada kroků s kompenzací, bez distribuované transakce.",
    icon: "⇶",
    kind: "workflow",
    fits: { architecture: ["microservices"] },
    rules: {
      must: [
        "Každý krok sagy má kompenzační krok, který jeho účinek vrátí.",
        "Kroky komunikují událostmi a jsou idempotentní.",
        "Stav sagy je uložený, aby šla po výpadku dokončit nebo vrátit.",
      ],
      mustNot: [
        "Žádná distribuovaná transakce přes databáze více služeb.",
        "Žádný krok bez kompenzace.",
      ],
    },
    decomposition: [
      { title: "discover", text: "Sepiš služby a kroky, kterých se změna týká." },
      { title: "define", text: "Ke každému kroku napiš událost a kompenzaci." },
      { title: "build", text: "Uveď kroky a kompenzace jako idempotentní obsluhu událostí." },
      { title: "verify", text: "Otestuj úspěch i selhání v každém kroku a návrat kompenzacemi." },
      { title: "live", text: "Zapiš průběh sagy a místa selhání do agent-workspace." },
    ],
    template: [
      "1. discover — sepiš služby a pořadí kroků, kterých se změna týká.",
      "2. define — ke každému kroku napiš událost, kterou vyšle, a kompenzaci, která ho vrátí.",
      "3. build — uveď kroky a kompenzace jako idempotentní obsluhu událostí a ulož stav sagy.",
      "4. verify — otestuj průchod bez chyby i selhání v každém kroku; kompenzace musí vrátit předchozí kroky.",
      "5. live — zapiš do agent-workspace, jak saga proběhla a kde může selhat.",
    ].join("\n"),
    endCriteria: "Každý krok má kompenzaci a testy pokrývají úspěch i selhání v každém kroku.",
    stopCondition: "Některý krok nejde vrátit ani kompenzovat — zastav a vyžádej si rozhodnutí, jak s ním naložit.",
    refs: ["ms-message-broker", "ms-service-database"],
  },
];
