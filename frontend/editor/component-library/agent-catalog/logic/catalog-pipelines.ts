// Kategorie Pipelines: řetěz kroků, kde každý krok ukazuje na know-how z levé knihovny
// (`CATALOG_ITEMS` v library-catalog) odkazem přes `refs`, ne kopií textu. Drop položky vytvoří
// akci v bloku Akce; `refs` řekne agentovi, kterou dlaždici levého navbaru si má dotáhnout.
import type { AgentItem } from "./agent-catalog";

export const pipelineItems: AgentItem[] = [
  {
    id: "pl-feature-folder",
    category: "pipelines",
    label: "Postav feature složku",
    hint: "Rodič + dílek + logika + styl: kompletní feature složka v jednom tahu, podle levé knihovny.",
    icon: "▦",
    kind: "action",
    rules: {
      must: [
        "Rodič skládá dílky, dílek dostává data v props a hlásí callbackem.",
        "Logika bez Reactu jde do logic/<name>.ts s testem vedle.",
        "Jeden styles/<feature>.css na složku, BEM s příběhovým komentářem.",
      ],
      mustNot: [
        "Dílek nevolá API ani mutate; ukládá jen rodič.",
        "Soubor přes ~200 řádků se nedělí uvnitř — vzniká další dílek.",
      ],
    },
    decomposition: [
      { title: "Kostra", text: "Založ components/, logic/, styles/, README.md." },
      { title: "Rodič", text: "Podle fe-parent-composes: importuje dílky, drží stav a zámek zápisu." },
      { title: "Logika", text: "Podle fe-pure-model: čisté funkce, test vedle." },
      { title: "Styl", text: "Podle css-bem-block: BEM a příběhový komentář nad blokem." },
    ],
    template: [
      "1. Založ složku feature/ s components/, logic/, styles/, README.md.",
      "2. Napiš rodiče podle fe-parent-composes: importuje dílky, drží stav.",
      "3. Odvození a mutace jako čisté funkce podle fe-pure-model, test vedle.",
      "4. Jeden styles/<feature>.css podle css-bem-block: BEM a příběhový komentář.",
      "5. README.md: co feature je, tvar dat, jak přidat další dílek.",
    ].join("\n"),
    endCriteria: "Složka má components/, logic/, styles/, README, žádný soubor přes ~200 řádků, test u logiky prochází.",
    stopCondition: "Cesta pro nový soubor neodpovídá docs/pravidla-struktury.md — zastav a ověř umístění, než píšeš kód.",
    refs: ["fe-parent-composes", "fe-pure-model", "css-bem-block"],
  },
  {
    id: "pl-backend-endpoint-cas",
    category: "pipelines",
    label: "Backend endpoint s CAS",
    hint: "Tenký router, logika v modulu prostředí, zápis pod revizí; test vedle modulu.",
    icon: "⇄",
    kind: "action",
    rules: {
      must: [
        "Router jen do backend/api/<prostředí>/, logika v modulu prostředí.",
        "Zápis nese expectedRevision, kolize je 409.",
        "Test test_<modul>.py leží vedle modulu.",
      ],
      mustNot: [
        "Žádná logika v routeru.",
        "Žádný zápis bez revize.",
      ],
    },
    decomposition: [
      { title: "Router", text: "Podle be-environment-router: přijme, ověří tvar, deleguje." },
      { title: "Revize", text: "Podle be-cas-revision: expectedRevision, 409 při kolizi." },
      { title: "Validace", text: "Podle be-input-validation: tvar a meze ověří server." },
      { title: "Test", text: "Podle test-unit-beside: test_<modul>.py vedle modulu." },
    ],
    template: [
      "1. Napiš router podle be-environment-router — jen tvar vstupu a volání modulu.",
      "2. Přidej revizi podle be-cas-revision — expectedRevision, 409 při neshodě.",
      "3. Validuj vstup na serveru podle be-input-validation.",
      "4. Napiš test_<modul>.py vedle modulu podle test-unit-beside.",
      "5. Spusť uv run pytest backend.",
    ].join("\n"),
    endCriteria: "Endpoint validuje vstup, hlídá revizi (409 při kolizi) a test_<modul>.py prochází pod uv run pytest backend.",
    stopCondition: "Chybí modul prostředí, kam logika patří — zastav a rozhodni umístění podle pravidla 2 v docs/pravidla-struktury.md.",
    refs: ["be-environment-router", "be-cas-revision", "be-input-validation", "test-unit-beside"],
  },
  {
    id: "pl-verify-before-done",
    category: "pipelines",
    label: "Ověření před hotovo",
    hint: "uv run pytest backend · npm test · npm run build — výstup je součástí hlášení, ne tvrzení.",
    icon: "⌸",
    kind: "action",
    rules: {
      must: [
        "Před hlášením hotovo běží uv run pytest backend, npm test a npm run build.",
        "Výstup všech tří příkazů je součástí odpovědi.",
        "Neúspěch kterékoli brány znamená, že hotovo není.",
      ],
      mustNot: [
        "Žádné „mělo by to fungovat“ bez spuštěného příkazu.",
        "Žádné vynechání brány kvůli termínu.",
      ],
    },
    decomposition: [
      { title: "Backend", text: "uv run pytest backend — podle test-done-gates." },
      { title: "Frontend", text: "npm test (vitest, bez DOM)." },
      { title: "Sestavení", text: "npm run build (tsc --noEmit + vite build)." },
    ],
    template: [
      "1. uv run pytest backend — backend testy a lint pravidel.",
      "2. npm test — vitest bez DOM, logika a lint katalogů.",
      "3. npm run build — tsc --noEmit + vite build; sestavení musí projít.",
      "4. Vlož výstup všech tří příkazů do odpovědi jako důkaz.",
    ].join("\n"),
    endCriteria: "Všechny tři příkazy proběhly bez chyby a jejich výstup je vložený do hlášení.",
    stopCondition: "Kterýkoli příkaz selže — zastav, oprav příčinu, spusť znovu; nehlas hotovo.",
    refs: ["test-done-gates"],
  },
  {
    id: "pl-fill-card-via-api",
    category: "pipelines",
    label: "Naplnění karty přes API",
    hint: "Origin header, pořadí workspace → kritéria → uzavření; zápis pod zámkem s CAS revizí.",
    icon: "⇶",
    kind: "action",
    rules: {
      must: [
        "Zápis nese hlavičku Origin odpovídající vlastní adrese aplikace.",
        "Pořadí zápisu: nejdřív agent-workspace (log/handoff), pak kritéria (agent-output blocks), naposled uzavření (done proposed).",
        "Každý zápis nese expectedRevision přečtenou bezprostředně před ním.",
      ],
      mustNot: [
        "Žádné volání agent-output na uzavřenou kartu (done.confirmed).",
        "Žádný zápis done.confirmed:true — to dělá jen člověk.",
      ],
    },
    decomposition: [
      { title: "Origin", text: "Podle sec-same-origin-write: hlavička Origin proti vlastní adrese." },
      { title: "Workspace", text: "POST /api/desktop-v3/agent-workspace se sekcemi log/handoff/failures/fixes." },
      { title: "Kritéria", text: "POST /api/desktop-v3/agent-output s blocks[].status a reports[]." },
      { title: "Uzavření", text: "done: {proposed: true, note} — navrhne, nepotvrzuje." },
    ],
    template: [
      "1. Nastav Origin na adresu aplikace (same-origin zápis).",
      "2. GET node-brief nebo agent-workspace, zapamatuj si revision.",
      "3. POST agent-workspace se sekcemi (log, handoff, failures, fixes) a expectedRevision.",
      "4. POST agent-output s blocks (status met/unmet/blocked) a reports (log/summary/handoff/improvements/errors).",
      "5. V agent-output.done pošli jen proposed: true — člověk zápis potvrdí.",
    ].join("\n"),
    endCriteria: "Server vrátí novou revizi bez 409/403; karta nese log, kritéria a navržené done.",
    stopCondition: "Server vrátí 409 (revize se rozešla) nebo 403 (Origin) — zastav, načti aktuální stav znovu, neopakuj zápis naslepo.",
    refs: ["be-cas-revision", "sec-same-origin-write"],
  },
];
